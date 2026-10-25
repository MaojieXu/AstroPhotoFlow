"""Verify installed wheel resources and a Node-free wheel rebuild from sdist."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def check_wheel(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        prefix = "astrophotoflow/"
        required = {
            "backend/cli.py", "backend/alembic.ini", "backend/alembic/env.py",
            "backend/alembic/versions/0008_asset_equipment_snapshot.py",
            "backend/alembic/versions/0009_remove_legacy_capture_profiles.py",
            "comfyui/extension/__init__.py", "comfyui/extension/assets/astrophotoflow.js",
            "comfyui/extension/assets/astrophotoflow.css", "vendor/comfyui-source.json",
            "vendor/comfyui-0.42.0.zip", "vendor/comfyui-0.42.0-windows-py312.lock",
        }
        assert {prefix + name for name in required} <= names, f"Missing product resources in {path.name}"
        assert not any(name.startswith(("astrophotoflow_service/", "tests/", "astrophotoflow/frontend/")) for name in names)
        assert not any("node_modules/" in name or "/__pycache__/" in name for name in names)
        assert prefix + "backend/capture_profiles.py" not in names
        for extension in ("js", "css"):
            bundled = archive.read(f"{prefix}comfyui/extension/assets/astrophotoflow.{extension}")
            assert bundled == (ROOT / "build" / "frontend" / f"astrophotoflow.{extension}").read_bytes()


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    if result.returncode:
        raise SystemExit(result.stdout)


def main() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    stem = f"{project['name']}-{project['version']}"
    wheel = next((ROOT / "dist").glob(stem + "-*.whl"))
    sdist = ROOT / "dist" / (stem + ".tar.gz")
    check_wheel(wheel)
    artifacts = ROOT / ".artifacts"
    artifacts.mkdir(exist_ok=True)
    report = {"wheel": wheel.name, "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()}
    with TemporaryDirectory(prefix="distribution-", dir=artifacts) as temporary:
        work = Path(temporary)
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        env["PYTHONNOUSERSITE"] = "1"
        env["UV_PROJECT_ENVIRONMENT"] = str(work / "venv")
        env["UV_CACHE_DIR"] = str(artifacts / "cache" / "uv")
        uv = [sys.executable, "-m", "uv"]
        run(uv + ["sync", "--project", str(ROOT), "--locked", "--no-install-project", "--python", sys.executable], cwd=work, env=env)
        python = work / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run(uv + ["pip", "install", "--python", str(python), "--no-deps", str(wheel)], cwd=work, env=env)

        def smoke() -> None:
            run([str(python), "-m", "astrophotoflow.cli", "--help"], cwd=work, env=env)
            script = """
import importlib.util
from importlib.resources import files
from pathlib import Path
import sys
import astrophotoflow
from astrophotoflow.backend.schema import SCHEMA_REVISION, upgrade_database, current_revision
from astrophotoflow.config import Settings
import astrophotoflow.comfyui
import astrophotoflow.mcp_server
assert 'server' not in sys.modules
assert Path(astrophotoflow.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert importlib.util.find_spec('astrophotoflow_service') is None
plugin = files('astrophotoflow.comfyui').joinpath('extension')
assert plugin.joinpath('assets/astrophotoflow.js').is_file()
assert importlib.util.find_spec('astrophotoflow.backend.capture_profiles') is None
from astrophotoflow.backend.models import Base
assert 'capture_profile' not in Base.metadata.tables
assert 'project_capture_profile' not in Base.metadata.tables
assert 'capture_profile_id' not in Base.metadata.tables['asset_version'].c
"""
            script += "\ndata = Path('database'); data.mkdir(exist_ok=True)\nsettings = Settings('127.0.0.1', 8190, data.resolve(), ('http://127.0.0.1:8188',))\nupgrade_database(settings)\nassert current_revision(settings.database_path) == SCHEMA_REVISION\n"
            run([str(python), "-c", script], cwd=work, env=env)

        smoke()
        report["installed_wheel"] = "passed"
        with tarfile.open(sdist) as archive:
            archive.extractall(work / "source", filter="data")
        source = work / "source" / stem
        assert (source / "build/frontend/astrophotoflow.js").is_file()
        # Only Python launchers and OS utilities remain on PATH during rebuild.
        env["PATH"] = str(Path(sys.executable).parent)
        if os.name == "nt":
            env["PATH"] += os.pathsep + str(Path(os.environ["SystemRoot"]) / "System32")
        assert shutil.which("node", path=env["PATH"]) is None
        report["node_available_during_sdist_rebuild"] = False
        output = artifacts / "packages" / "from-sdist"
        output.mkdir(parents=True, exist_ok=True)
        run([sys.executable, "-m", "build", "--wheel", "--installer", "uv", "--outdir", str(output), str(source)], cwd=work, env=env)
        rebuilt = next(output.glob(stem + "-*.whl"))
        check_wheel(rebuilt)
        run(uv + ["pip", "install", "--python", str(python), "--no-deps", "--reinstall", str(rebuilt)], cwd=work, env=env)
        smoke()
        report["sdist_rebuilt_wheel"] = "passed"
        report["rebuilt_wheel_sha256"] = hashlib.sha256(rebuilt.read_bytes()).hexdigest()
    reports = artifacts / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "packaging.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
