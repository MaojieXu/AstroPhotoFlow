"""Reproducible import phase benchmark; run from a worktree with its own Python.

Fixture generation happens in the parent only. Every measured trial uses a fresh
child process, the same files, and source pinned to the requested Git commit.
Phase wall/CPU sums overlap and must not be added to derive elapsed wall time.
"""
from __future__ import annotations

import ast

import argparse
import cProfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import gc
import hashlib
import importlib
from io import StringIO
import json
from pathlib import Path
import pstats
import subprocess
import sys
import threading
import time
import types
from uuid import uuid4

import numpy as np
import psutil
from astropy.io import fits

ROOT = Path.cwd()
ARTIFACTS = ROOT / ".artifacts" / "import-phase-benchmark"
TOKEN = "phase-benchmark-only"


def relocate_historical_imports(source):
    owners = {}
    for contract in (ROOT / "src/astrophotoflow/contracts").glob("*.py"):
        for node in ast.parse(contract.read_text(encoding="utf-8")).body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                owners[node.name] = "astrophotoflow.contracts." + contract.stem
            elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                owners[node.targets[0].id] = "astrophotoflow.contracts." + contract.stem
    lines = source.splitlines(keepends=True)
    edits = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ImportFrom) or not node.level:
            continue
        if node.module is None:
            statements = []
            for alias in node.names:
                module = "astrophotoflow.core" if alias.name == "dependencies" else "astrophotoflow.modules.data"
                name = "http" if alias.name == "dependencies" else alias.name
                statements.append("from " + module + " import " + name + (" as " + (alias.asname or alias.name) if name != (alias.asname or alias.name) else ""))
        elif node.module in {"schemas", "import_schemas", "setup_schemas"}:
            statements = ["from " + owners[alias.name] + " import " + alias.name + (" as " + alias.asname if alias.asname else "") for alias in node.names]
        else:
            target = {"db": "astrophotoflow.core.database.db", "dependencies": "astrophotoflow.core.http", "errors": "astrophotoflow.core.errors", "config": "astrophotoflow.core.config"}.get(node.module)
            if target is None:
                continue
            names = [alias.name + (" as " + alias.asname if alias.asname else "") for alias in node.names]
            statements = ["from " + target + " import " + ", ".join(names)]
        indent = " " * node.col_offset
        edits.append((node.lineno - 1, node.end_lineno, indent + ("\n" + indent).join(statements) + "\n"))
    for start, end, statement in sorted(edits, reverse=True):
        lines[start:end] = [statement]
    return "".join(lines)


def load_modules(revision):
    import astrophotoflow
    import astrophotoflow.modules.data as backend
    assert Path(astrophotoflow.__file__).is_relative_to(ROOT), astrophotoflow.__file__
    modules = {}
    for name in ("fits_preview", "ingestion", "imports"):
        full_name = f"astrophotoflow.modules.data.{name}"
        if revision == "working":
            module = importlib.import_module(full_name)
        else:
            relative = f"src/astrophotoflow/backend/{name}.py"
            source = subprocess.check_output(["git", "-c", "safe.directory=" + str(ROOT), "show", f"{revision}:{relative}"], text=True, encoding="utf-8")
            module = types.ModuleType(full_name)
            module.__file__ = f"git:{revision}/{relative}"
            sys.modules[full_name] = module
            setattr(backend, name, module)
            exec(compile(relocate_historical_imports(source), module.__file__, "exec"), module.__dict__)
        modules[name] = module
    return modules


class Measurements:
    def __init__(self):
        self.phases = {}
        self.lock = threading.Lock()
        self.profiles = []

    @contextmanager
    def phase(self, name):
        start, cpu = time.perf_counter(), time.thread_time()
        try:
            yield
        finally:
            wall, cpu = time.perf_counter() - start, time.thread_time() - cpu
            with self.lock:
                record = self.phases.setdefault(name, {"calls": 0, "wall_seconds_sum": 0, "thread_cpu_seconds_sum": 0})
                record["calls"] += 1
                record["wall_seconds_sum"] += wall
                record["thread_cpu_seconds_sum"] += cpu

    def wrap(self, name, function):
        def measured(*args, **kwargs):
            with self.phase(name):
                return function(*args, **kwargs)
        return measured

    def profile_text(self):
        if not self.profiles:
            return None
        output = StringIO()
        stats = pstats.Stats(self.profiles[0], stream=output)
        for profile in self.profiles[1:]:
            stats.add(profile)
        stats.strip_dirs().sort_stats("cumulative").print_stats(18)
        return output.getvalue()


def instrument(modules, measurements):
    from astrophotoflow.core.database.db import Database
    ingestion = modules["ingestion"]
    for name, phase in (
        ("_read_hash_and_copy", "hash_copy"),
        ("inspect_fits", "parsing"),
        ("_xisf_layout", "parsing"),
        ("_inspect_xisf", "parsing"),
        ("_fit_preview_rows", "preview"),
        ("_save_preview", "preview"),
        ("_xisf_image", "preview"),
        ("_ordinary_image", "preview"),
        ("_raw_image", "preview"),
        ("first_video_frame", "preview"),
        ("create_preview", "preview_decode"),
    ):
        if hasattr(ingestion, name):
            setattr(ingestion, name, measurements.wrap(phase, getattr(ingestion, name)))
    for method, phase in (("read_session", "database_read"), ("write_session", "database_write")):
        original = getattr(Database, method)
        def context(self, original=original, phase=phase):
            @contextmanager
            def measured():
                if threading.current_thread().name == "benchmark-monitor":
                    with original(self) as session:
                        yield session
                else:
                    with measurements.phase(phase), original(self) as session:
                        yield session
            return measured()
        setattr(Database, method, context)
    original_replace = ingestion.os.replace
    def replace(source, destination):
        if "objects" in Path(destination).parts:
            name = "atomic_upload_relocation" if "upload-staging" in Path(source).parts else "atomic_managed_relocation"
            with measurements.phase(name):
                return original_replace(source, destination)
        return original_replace(source, destination)
    ingestion.os.replace = replace
    original_open = Path.open
    class TimedWriter:
        def __init__(self, stream, phase):
            self.stream, self.phase = stream, phase
        def __enter__(self):
            self.stream.__enter__()
            return self
        def __exit__(self, *args):
            return self.stream.__exit__(*args)
        def __getattr__(self, name):
            return getattr(self.stream, name)
        def write(self, data):
            with measurements.phase(self.phase):
                written = self.stream.write(data)
            with measurements.lock:
                record = measurements.phases[self.phase]
                record["bytes"] = record.get("bytes", 0) + written
            return written
    def open_file(path, mode="r", *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        if mode == "xb" and "upload-staging" in path.parts:
            return TimedWriter(stream, "upload_write")
        if mode == "xb" and "staging" in path.parts:
            return TimedWriter(stream, "copy_write")
        return stream
    Path.open = open_file


def worker(args):
    modules = load_modules(args.revision)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import func, select
    from astrophotoflow.core.database.db import Database
    from astrophotoflow.modules.data.models import AssetTask, AssetTaskItem, AssetVersion
    from astrophotoflow.core.database.schema import database_lock, upgrade_database
    from astrophotoflow.core.config import ImportRoot, Settings

    paths = [Path(path) for path in args.source]
    # Real samples are one direct source, never a corpus directory traversal.
    data = ARTIFACTS / "runs" / str(uuid4())
    settings = Settings("127.0.0.1", 8190, data, ("http://127.0.0.1:8188",),
                        tuple(ImportRoot(str(index), path.parent) for index, path in enumerate(paths)))
    with database_lock(settings):
        upgrade_database(settings)
    database = Database(settings.database_path)
    direct_xisf = modules["ingestion"]._xisf_image
    metrics = Measurements()
    instrument(modules, metrics)
    app = FastAPI()
    app.state.database, app.state.settings, app.state.token = database, settings, TOKEN
    app.include_router(modules["imports"].router)
    task_id = None
    background_start = None
    registration = visibility = None
    process = psutil.Process()
    before_io = process.io_counters()
    peak = process.memory_info().rss
    stop = threading.Event()
    def monitor():
        nonlocal registration, visibility, peak
        while not stop.is_set():
            peak = max(peak, process.memory_info().rss)
            if task_id and background_start is not None:
                with database.read_session() as session:
                    row = session.get(AssetTask, task_id)
                    count = session.scalar(select(func.count()).select_from(AssetTaskItem).where(
                        AssetTaskItem.task_id == task_id, AssetTaskItem.asset_version_id.is_not(None)))
                    if count == len(paths) and registration is None:
                        registration = time.perf_counter() - background_start
                    if row.dataset_id and visibility is None:
                        visibility = time.perf_counter() - background_start
            stop.wait(.005)
    monitor_thread = threading.Thread(target=monitor, name="benchmark-monitor")
    monitor_thread.start()
    total_start = time.perf_counter()
    upload_wall = 0
    try:
        # Both revisions get identical lazy executor setup. Baseline does not use
        # these pools; candidate HTTP entrypoints share the two service pools.
        with ThreadPoolExecutor(max_workers=settings.file_workers) as files, ThreadPoolExecutor(max_workers=settings.preview_workers) as previews, TestClient(app) as client:
            app.state.import_workers = files, previews
            auth = {"Authorization": "Bearer " + TOKEN}
            if args.mode == "upload":
                upload_start = time.perf_counter()
                response = client.post("/api/v1/uploads", headers=auth, json={
                    "files": [{"name": path.name, "size": path.stat().st_size} for path in paths],
                    "classification": {"frame_class": "subframe", "frame_type": "light"}, "create_dataset": True})
                assert response.status_code == 202, response.text
                task_id = response.json()["task_id"]
                for index, path in enumerate(paths):
                    payload = path.read_bytes()
                    with metrics.phase("upload_request"):
                        response = client.put(f"/api/v1/uploads/{task_id}/{index}", headers=auth, content=payload)
                    assert response.status_code == 200, response.text
                    del payload
                gc.collect()
                upload_wall = time.perf_counter() - upload_start
                background_start = time.perf_counter()
                response = client.post(f"/api/v1/uploads/{task_id}/start", headers=auth, json={})
                assert response.status_code == 202, response.text
            else:
                task_id = str(uuid4())
                with database.write_session() as session:
                    session.add(AssetTask(id=task_id, status="queued", sources=[
                        {"root_id": str(index), "path": path.name, "kind": "file", "enumeration_completed": False}
                        for index, path in enumerate(paths)], storage_mode=args.mode,
                        classification={"frame_class": "subframe", "frame_type": "light"}, parameters={}, notes=None,
                        dataset_name="phase benchmark", target_dataset_id=str(uuid4()), dataset_base_revision=None,
                        dataset_id=None, enumeration_completed=False, retry_of_task_id=None, report={}, error=None))
                background_start = time.perf_counter()
                if args.revision == "working":
                    modules["ingestion"].process_task(database, settings, task_id, app.state.import_workers)
                else:
                    modules["ingestion"].process_task(database, settings, task_id)
        background_wall = time.perf_counter() - background_start
        total_wall = time.perf_counter() - total_start
    finally:
        stop.set()
        monitor_thread.join()
    after_io = process.io_counters()
    with database.read_session() as session:
        row = session.get(AssetTask, task_id)
        assert row.status == "completed", (row.status, row.error)
        versions = session.scalars(select(AssetVersion)).all()
        assert len(versions) == len(paths)
        assert all(version.availability == "available" and version.content_hash for version in versions)
    database.close()
    profiles = []
    if args.profile:
        # Profile decode separately with the monitor/executors stopped. Profiling
        # overhead and allocations do not contaminate the timed pipeline phases.
        for path in paths:
            profiler = cProfile.Profile()
            if modules["ingestion"].format_for_path(path) == "fits":
                inspected = modules["fits_preview"].inspect_fits(path)
                selected = next(row for row in inspected["hdus"] if row["is_selected"])
                function = modules["fits_preview"].create_preview
                arguments = (path, selected["hdu_index"], selected["supported_kind"], inspected["parsed_parameters"], 100)
            else:
                function, arguments = direct_xisf, (path,)
            profiler.enable()
            image, _ = function(*arguments)
            image.thumbnail((100, 100))
            profiler.disable()
            profiles.append(profiler)
        metrics.profiles = profiles
    return {"revision": args.revision, "mode": args.mode, "files": len(paths),
            "source_bytes": sum(path.stat().st_size for path in paths), "upload_wall_seconds": upload_wall,
            "registration_seconds": registration or background_wall, "dataset_visible_seconds": visibility or background_wall,
            "background_wall_seconds": background_wall, "total_wall_seconds": total_wall,
            "phases": metrics.phases, "read_bytes": after_io.read_bytes - before_io.read_bytes,
            "write_bytes": after_io.write_bytes - before_io.write_bytes, "peak_rss_mib": peak / 1024**2,
            "preview_profile": metrics.profile_text()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="3f72b71")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--files", type=int, default=8)
    parser.add_argument("--edge", type=int, default=2048)
    parser.add_argument("--output", type=Path, default=ARTIFACTS / "results.json")
    parser.add_argument("--real-source", action="append", default=[])
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--revision", default="working", help=argparse.SUPPRESS)
    parser.add_argument("--source", action="append", default=[], help=argparse.SUPPRESS)
    parser.add_argument("--mode", choices=["managed", "upload", "reference"], default="managed", help=argparse.SUPPRESS)
    parser.add_argument("--profile", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args)))
        return
    source = ARTIFACTS / f"source-{args.files}-{args.edge}"
    source.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(args.files):
        path = source / f"{index:02}.fits"
        if not path.exists():
            hdu = fits.PrimaryHDU(np.arange(args.edge**2, dtype=np.float32).reshape(args.edge, args.edge) + index * 100)
            hdu.header["IMAGETYP"] = "Light Frame"
            hdu.writeto(path)
            del hdu
        paths.append(path)
    gc.collect()
    # Warm both revisions' source input equally before fresh measured children.
    for path in paths:
        with path.open("rb") as stream:
            while stream.read(8 * 1024**2):
                pass
    results = []
    cases = [(mode, paths, False) for mode in ("managed", "upload")]
    cases.extend(("reference", [Path(path).resolve()], True) for path in args.real_source)
    for trial in range(args.trials):
        for mode, sources, profile in cases:
            for revision in (args.baseline, "working"):
                command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--revision", revision, "--mode", mode]
                for path in sources:
                    command.extend(["--source", str(path)])
                if profile:
                    command.append("--profile")
                result = json.loads(subprocess.check_output(command, cwd=ROOT, text=True, encoding="utf-8"))
                result.update(trial=trial, sources=[str(path) for path in sources])
                results.append(result)
                print(f"trial={trial} revision={revision} mode={mode} files={len(sources)} registration={result['registration_seconds']:.4f}s background={result['background_wall_seconds']:.4f}s", flush=True)
    report = {"baseline_revision": args.baseline, "candidate_revision": subprocess.check_output(
        ["git", "-c", "safe.directory=" + str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
        "candidate_source_sha256": {name: hashlib.sha256((ROOT / "src" / "astrophotoflow" / "backend" / f"{name}.py").read_bytes()).hexdigest()
                                    for name in ("fits_preview", "ingestion", "imports")},
        "fixture_generation": "parent process only; fresh measured subprocess per trial; reused warm input; no arrays generated in children",
        "phase_units": "wall_seconds_sum and thread_cpu_seconds_sum; nested/concurrent sums overlap and are not elapsed wall time",
        "synthetic_shape": [args.edge, args.edge], "trials": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
