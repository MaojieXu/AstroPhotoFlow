"""One-time, explicit offline cleanup of the current three-kind device registry.

Stop the selected workspace and make a SQLite backup before --apply. This is
not a startup migration: historical snapshots and all other table data remain
byte-for-byte unchanged. Without --apply this command only reports a plan.
"""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from pydantic import TypeAdapter

from astrophotoflow.contracts.equipment import EquipmentCreate

DEVICE = TypeAdapter(EquipmentCreate)


def quoted(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def table_facts(connection: sqlite3.Connection) -> dict:
    """Hash every unchanged value, including original JSON text and identities."""
    facts = {}
    for (table,) in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({quoted(table)})")]
        excluded = {"specs", "serial_number"} if table == "equipment" else (
            {"inline_equipment"} if table == "equipment_setup_member" else set())
        selected = [name for name in columns if name not in excluded]
        rows = connection.execute(f"SELECT {','.join(map(quoted, selected))} FROM {quoted(table)}").fetchall()
        encoded = sorted(json.dumps(list(row), ensure_ascii=False, default=lambda value: value.hex(),
                                    separators=(",", ":")) for row in rows)
        facts[table] = {"rows": len(rows), "columns": selected,
                        "sha256": hashlib.sha256("\n".join(encoded).encode()).hexdigest()}
    return facts


def clean_specs(kind: str, source: dict) -> tuple[dict, bool]:
    specs = dict(source)
    inferred_mono = False
    if kind == "camera":
        previous_mode = specs.pop("sensor_mode", None)
        if previous_mode == "mono" and specs.get("cfa_pattern") is None:
            specs["cfa_pattern"] = "MONO"
            inferred_mono = True
    elif kind == "telescope":
        specs.pop("aperture_mm", None)
    return specs, inferred_mono


def prepare_changes(connection: sqlite3.Connection) -> tuple[list, list, int]:
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"equipment", "equipment_setup_member", "capture_preset"}.issubset(tables):
        raise ValueError("Not a current AstroPhotoFlow device database.")
    equipment_columns = {row[1] for row in connection.execute('PRAGMA table_info("equipment")')}
    member_columns = {row[1] for row in connection.execute('PRAGMA table_info("equipment_setup_member")')}
    if not {"id", "kind", "name", "specs", "revision"}.issubset(equipment_columns) or not {
        "id", "setup_id", "equipment_id", "inline_equipment", "optical_accessory_id"
    }.issubset(member_columns):
        raise ValueError("The database is not the telescope-accessory schema expected by this command.")
    equipment_changes, member_changes = [], []
    mono_count = 0
    for identity, kind, name, raw in connection.execute("SELECT id,kind,name,specs FROM equipment"):
        if kind not in {"camera", "telescope", "filter"}:
            raise ValueError(f"Unsupported device kind {kind!r}; this command does not remove devices.")
        original = json.loads(raw)
        cleaned, inferred = clean_specs(kind, original)
        DEVICE.validate_python({"kind": kind, "name": name, "specs": cleaned})
        mono_count += inferred
        if cleaned != original:
            equipment_changes.append((json.dumps(cleaned, ensure_ascii=False), identity))
    for identity, raw in connection.execute(
        "SELECT id,inline_equipment FROM equipment_setup_member WHERE inline_equipment IS NOT NULL"
    ):
        original = json.loads(raw)
        cleaned = dict(original)
        cleaned.pop("serial_number", None)
        cleaned["specs"], inferred = clean_specs(cleaned["kind"], cleaned.get("specs", {}))
        DEVICE.validate_python(cleaned)
        mono_count += inferred
        if cleaned != original:
            member_changes.append((json.dumps(cleaned, ensure_ascii=False), identity))
    return equipment_changes, member_changes, mono_count


def simplify(database: Path, *, apply: bool) -> dict:
    database = database.resolve(strict=True)
    # mode=rw refuses to create a new database on a typo; dry runs are read-only.
    mode = "rw" if apply else "ro"
    with sqlite3.connect(database.as_uri() + f"?mode={mode}", uri=True, timeout=5) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("Database integrity check failed before cleanup.")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Existing foreign-key violations must be resolved before cleanup.")
        connection.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        before = table_facts(connection)
        equipment_changes, member_changes, mono_count = prepare_changes(connection)
        drop_serial = any(row[1] == "serial_number" for row in connection.execute('PRAGMA table_info("equipment")'))
        report = {"database": str(database), "apply": apply,
                  "equipment_specs_changed": len(equipment_changes),
                  "inline_equipment_changed": len(member_changes),
                  "mono_modes_consolidated": mono_count, "drop_serial_number": drop_serial,
                  "before": before}
        if not apply:
            connection.rollback()
            report["state"] = "planned" if equipment_changes or member_changes or drop_serial else "already_simplified"
            return report
        connection.executemany("UPDATE equipment SET specs=? WHERE id=?", equipment_changes)
        connection.executemany("UPDATE equipment_setup_member SET inline_equipment=? WHERE id=?", member_changes)
        if drop_serial:
            connection.execute("ALTER TABLE equipment DROP COLUMN serial_number")
        after = table_facts(connection)
        if before != after:
            raise ValueError("Cleanup changed unrelated data or historical snapshots; transaction will roll back.")
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)] or connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall():
            raise ValueError("Integrity check failed after cleanup; transaction will roll back.")
        remaining_equipment, remaining_inline, _ = prepare_changes(connection)
        if remaining_equipment or remaining_inline:
            raise ValueError("The cleanup did not reach a stable result; transaction will roll back.")
        connection.commit()
        report.update(state="simplified" if equipment_changes or member_changes or drop_serial else "already_simplified",
                      after=after, unchanged_data_verified=True, integrity_check="ok", foreign_key_violations=0)
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Apply only after stopping the selected workspace and backing it up.")
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args()
    report = simplify(arguments.database, apply=arguments.apply)
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"before", "after"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
