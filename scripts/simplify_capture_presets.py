"""Explicit offline preset cleanup; stop and back up the exact workspace first."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from sqlalchemy.dialects import sqlite
from sqlalchemy.schema import CreateIndex, CreateTable

from astrophotoflow.contracts.setups import PresetParametersPatch
from astrophotoflow.modules.data.equipment.models import CapturePresetSelection

PARAMETERS = set(PresetParametersPatch.model_fields)
RETIRED = {"classification", "notes", "optical_accessory_selection"}


def quoted(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def plan(connection: sqlite3.Connection) -> dict:
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"equipment", "equipment_setup", "equipment_setup_member", "capture_preset", "capture_preset_selection"}.issubset(tables):
        raise ValueError("Not a current AstroPhotoFlow database.")
    conflicts = []
    counts = {}
    for identity, setup_id, equipment_id, inline_raw in connection.execute(
        "SELECT id,setup_id,equipment_id,inline_equipment FROM equipment_setup_member"
    ):
        if equipment_id:
            found = connection.execute("SELECT kind FROM equipment WHERE id=?", (equipment_id,)).fetchone()
            if found is None:
                raise ValueError("A setup references missing equipment.")
            kind = found[0]
        else:
            kind = json.loads(inline_raw)["kind"]
        key = (setup_id, kind)
        counts[key] = counts.get(key, 0) + 1
    for (setup_id, kind), count in counts.items():
        if kind in {"camera", "telescope"} and count > 1:
            conflicts.append({"setup_id": setup_id, "kind": kind, "count": count, "reason": "multiple_devices"})
    for preset_id, kind, member_id in connection.execute("SELECT preset_id,kind,member_id FROM capture_preset_selection"):
        if kind != "filter":
            conflicts.append({"preset_id": preset_id, "kind": kind, "member_id": member_id, "reason": "retired_device_override"})
    columns = [row[1] for row in connection.execute('PRAGMA table_info("capture_preset")')]
    records = [dict(zip(columns, row, strict=True)) for row in connection.execute("SELECT * FROM capture_preset")]
    updates = []
    for row in records:
        for field in RETIRED & row.keys():
            raw = row[field]
            value = json.loads(raw) if field != "notes" and raw is not None else raw
            meaningful = (value is not None) if field == "optical_accessory_selection" else (any(item is not None for item in value.values()) if isinstance(value, dict) else value not in (None, ""))
            if meaningful:
                conflicts.append({"preset_id": row["id"], "field": field, "reason": "retired_preset_fact"})
        parameters = json.loads(row["parameters"])
        unknown = {key: value for key, value in parameters.items() if key not in PARAMETERS and value is not None}
        if unknown:
            conflicts.append({"preset_id": row["id"], "fields": sorted(unknown), "reason": "retired_parameters"})
        cleaned = {key: value for key, value in parameters.items() if key in PARAMETERS}
        PresetParametersPatch.model_validate(cleaned)
        if cleaned != parameters:
            updates.append((json.dumps(cleaned, ensure_ascii=False), row["id"]))
    sql = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='capture_preset_selection'").fetchone()[0]
    return {"conflicts": conflicts, "removed_columns": sorted(RETIRED & set(columns)),
            "parameter_updates": updates, "selection_rebuild": "camera" in sql or "optical_system" in sql,
            "preset_count": len(records)}


def facts(connection: sqlite3.Connection) -> dict:
    result = {}
    for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({quoted(table)})")]
        columns = [key for key in columns if table != "capture_preset" or key not in RETIRED]
        rows = []
        for row in connection.execute(f"SELECT {','.join(map(quoted, columns))} FROM {quoted(table)}"):
            record = dict(zip(columns, row, strict=True))
            if table == "capture_preset":
                record["parameters"] = {key: value for key, value in json.loads(record["parameters"]).items() if key in PARAMETERS}
            rows.append(json.dumps(record, ensure_ascii=False, sort_keys=True, default=lambda value: value.hex()))
        result[table] = {"rows": len(rows), "sha256": hashlib.sha256("\n".join(sorted(rows)).encode()).hexdigest()}
    return result


def simplify(database: Path, *, apply: bool) -> dict:
    database = database.resolve(strict=True)
    with sqlite3.connect(database.as_uri() + ("?mode=rw" if apply else "?mode=ro"), uri=True, timeout=5) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)] or connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Existing database integrity problems prevent cleanup.")
        changes = plan(connection)
        before = facts(connection)
        report = {"database": str(database), "apply": apply, **{key: value for key, value in changes.items() if key != "parameter_updates"},
                  "parameter_rows_changed": len(changes["parameter_updates"]), "before": before}
        if changes["conflicts"]:
            connection.rollback()
            return {**report, "state": "blocked"}
        if not apply:
            connection.rollback()
            return {**report, "state": "planned"}
        connection.executemany("UPDATE capture_preset SET parameters=? WHERE id=?", changes["parameter_updates"])
        for field in changes["removed_columns"]:
            connection.execute(f"ALTER TABLE capture_preset DROP COLUMN {quoted(field)}")
        if changes["selection_rebuild"]:
            table = CapturePresetSelection.__table__
            sql = str(CreateTable(table).compile(dialect=sqlite.dialect())).replace("CREATE TABLE capture_preset_selection", "CREATE TABLE capture_preset_selection_new", 1)
            connection.execute(sql)
            connection.execute("INSERT INTO capture_preset_selection_new SELECT * FROM capture_preset_selection")
            connection.execute("DROP TABLE capture_preset_selection")
            connection.execute("ALTER TABLE capture_preset_selection_new RENAME TO capture_preset_selection")
            for index in table.indexes:
                connection.execute(str(CreateIndex(index).compile(dialect=sqlite.dialect())))
        after = facts(connection)
        if before != after:
            raise ValueError("Unrelated values or historical snapshots changed; rollback.")
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)] or connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Integrity validation failed; rollback.")
        connection.commit()
        return {**report, "state": "simplified", "after": after, "unchanged_data_verified": True,
                "integrity_check": "ok", "foreign_key_violations": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    report = simplify(arguments.database, apply=arguments.apply)
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"before", "after"}}, ensure_ascii=False))
    if report["state"] == "blocked":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
