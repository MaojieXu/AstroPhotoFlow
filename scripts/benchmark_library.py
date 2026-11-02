"""Reproducible metadata-only library benchmarks in fresh isolated artifact databases."""

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from sqlalchemy import event, insert, update

from astrophotoflow.contracts.assets import LibraryQuery
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import upgrade_database
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion
from astrophotoflow.modules.data.library.queries import search_library


def seed(database: Database, count: int):
    assets = [str(uuid4()) for _ in range(count)]
    versions = [str(uuid4()) for _ in range(count)]
    created = datetime(2026, 1, 1, tzinfo=UTC)
    with database.write_session() as session:
        for start in range(0, count, 5000):
            indexes = range(start, min(start + 5000, count))
            session.execute(insert(Asset), [{"id": assets[i], "name": f"frame-{i:06d}", "scope": "shared", "role": "raw",
                "frame_class": "subframe", "frame_type": "light", "parameter_mode": "gain", "gain": i % 50, "offset": 0,
                "exposure_seconds": i % 501, "binning_x": 1, "binning_y": 1, "cfa_pattern": "MONO",
                "sensor_temperature_c": -10 + (i % 5) * 0.1, "created_at": created + timedelta(seconds=i)} for i in indexes])
            session.execute(insert(AssetVersion), [{"id": versions[i], "asset_id": assets[i], "version_number": 1,
                "storage_mode": "managed", "storage_location": f"synthetic/{i}.fits", "availability": "available",
                "content_hash": "b3:" + "a" * 64, "byte_size": 100, "scientific_metadata": {"format": "fits"}} for i in indexes])
            session.execute(update(Asset), [{"id": assets[i], "current_version_id": versions[i]} for i in indexes])
        grouped = count * 3 // 4
        groups = [(0, count // 2)] + [(i, min(i + 50, grouped)) for i in range(count // 2, grouped, 50)]
        for index, (start, stop) in enumerate(groups):
            identity, fixed = str(uuid4()), str(uuid4())
            session.execute(insert(Dataset), [{"id": identity, "name": f"large-{count}" if index == 0 else f"set-{index:06d}"}])
            session.execute(insert(DatasetVersion), [{"id": fixed, "dataset_id": identity, "version_number": 1}])
            session.execute(update(Dataset).where(Dataset.id == identity).values(current_version_id=fixed))
            for offset in range(start, stop, 5000):
                session.execute(insert(DatasetMember), [{"id": str(uuid4()), "dataset_version_id": fixed,
                    "asset_version_id": versions[i], "position": i - start} for i in range(offset, min(offset + 5000, stop))])
    return {"assets": count, "large_group_members": count // 2, "groups": len(groups), "standalone": count - grouped}


def measure(database: Database, query: LibraryQuery):
    statements, loaded = [], []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append((statement, parameters))

    event.listen(database.engine, "before_cursor_execute", capture)
    try:
        with database.read_session() as session:
            event.listen(session, "loaded_as_persistent", lambda session, instance: loaded.append(type(instance).__name__))
            start = perf_counter()
            page = search_library(session, query)
            elapsed = perf_counter() - start
        payload = page.model_dump_json().encode("utf-8")
    finally:
        event.remove(database.engine, "before_cursor_execute", capture)
    plans = []
    with database.engine.connect() as connection:
        for statement, parameters in statements:
            plans.append({"sql": statement, "plan": [list(row) for row in connection.exec_driver_sql("EXPLAIN QUERY PLAN " + statement, parameters)]})
    assert not loaded, loaded
    assert len(page.items) <= query.limit
    return {"query": query.model_dump(mode="json"), "seconds": elapsed, "response_bytes": len(payload),
            "total": page.total, "page_items": len(page.items), "orm_objects": len(loaded), "sql_count": len(statements), "plans": plans}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sizes", nargs="+", type=int, default=[1000, 10000, 100000])
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if not output.is_relative_to(repository / ".artifacts") or any(size < 4 for size in args.sizes):
        parser.error("Use a fresh directory below this worktree's .artifacts and sizes >= 4")
    output.mkdir(parents=True, exist_ok=False)
    report = {"kind": "synthetic metadata only; no image files or scientific processing", "python": sys.version,
              "sqlite": sqlite3.sqlite_version, "scales": []}
    for size in args.sizes:
        fixture = output / str(size)
        fixture.mkdir()
        settings = Settings("127.0.0.1", 8190, fixture, (), workspace=fixture)
        upgrade_database(settings)
        database = Database(settings.database_path)
        try:
            start = perf_counter()
            shape = seed(database, size)
            scale = {"shape": shape, "seed_seconds": perf_counter() - start, "workloads": {}}
            workloads = {"name": LibraryQuery(sort_by="name", order="asc"),
                         "exposure": LibraryQuery(sort_by="exposure_seconds", order="desc"),
                         "gain_filter": LibraryQuery(sort_by="parameter_mode", gain_min=0, gain_max=10),
                         "large_group": LibraryQuery(q=f"large-{size}", sort_by="name", order="asc")}
            for name, query in workloads.items():
                result = measure(database, query)
                scale["workloads"][name] = result
                print(json.dumps({"assets": size, "workload": name, **{key: result[key] for key in ["seconds", "response_bytes", "page_items", "orm_objects", "sql_count"]}}), flush=True)
            report["scales"].append(scale)
            (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        finally:
            database.close()


if __name__ == "__main__":
    main()
