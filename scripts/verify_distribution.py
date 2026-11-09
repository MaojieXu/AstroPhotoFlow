"""Verify installed wheel resources and a Node-free wheel rebuild from sdist."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import site
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def check_wheel(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        prefix = "astrophotoflow/"
        required = {
            "interfaces/http/cli.py", "core/database/alembic.ini", "core/database/alembic/env.py", "contracts/assets.py", "modules/data/public.py", "interfaces/http/data/assets.py", "interfaces/native/bootstrap.py", "core/workbench/__init__.py", "modules/data/imports/pipeline.py", "modules/data/imports/runner.py", "modules/data/formats/source.py",
            "contracts/software.py", "contracts/nodes.py", "modules/software/public.py", "modules/nodes/public.py",
            "core/database/alembic/versions/0001_baseline.py",
            "comfyui/proxy.py", "core/files.py", "web/index.html", "vendor/comfyui-source.json", "vendor/http-routes.json",
            "vendor/comfyui-0.42.0.zip", "vendor/comfyui-0.42.0-windows-py312.lock",
            "vendor/bundle-catalog.json",
            "vendor/comfyui-frontend-LICENSE",
            "web/assets/images/astrophotoflow-192.png",
            "web/assets/images/astrophotoflow-512.png",
        }
        assert any(name.endswith(".dist-info/licenses/LICENSE") for name in names)
        assert not any(name.startswith(prefix + "vendor/siril-") for name in names)
        missing_resources = sorted({prefix + name for name in required} - names)
        assert not missing_resources, f"Missing product resources in {path.name}: {missing_resources}"
        product_python = {
            prefix + source.relative_to(ROOT / "src/astrophotoflow").as_posix()
            for source in (ROOT / "src/astrophotoflow").rglob("*.py")
        }
        missing_modules = sorted(product_python - names)
        assert not missing_modules, f"Missing product Python modules in {path.name}: {missing_modules}"
        assert not any(name.startswith(("astrophotoflow_service/", "tests/", "astrophotoflow/frontend/", "astrophotoflow/backend/", "astrophotoflow/agent_tools/", "astrophotoflow/client_domains/")) for name in names)
        assert not any("node_modules/" in name or "/__pycache__/" in name for name in names)
        assert prefix + "backend/capture_profiles.py" not in names
        assert not any(name.startswith(prefix + "comfyui/extension/") for name in names)
        comfy_manifest = json.loads(archive.read(prefix + "vendor/comfyui-source.json"))
        comfy_archive_bytes = archive.read(prefix + "vendor/comfyui-0.42.0.zip")
        assert hashlib.sha256(comfy_archive_bytes).hexdigest() == comfy_manifest["sha256"]
        with zipfile.ZipFile(io.BytesIO(comfy_archive_bytes)) as engine:
            assert "ComfyUI/LICENSE" in engine.namelist()
            packaged_server = engine.read("ComfyUI/server.py")
            assert b"apf_page_id_by_client" in packaged_server and b"apf_page_token" in packaged_server
        resources = ROOT / ".artifacts/build/frontend"
        expected = {path.relative_to(resources).as_posix() for path in resources.rglob("*") if path.is_file()}
        actual = {name.removeprefix(prefix + "web/") for name in names if name.startswith(prefix + "web/")}
        assert not any(name.endswith(".map") for name in actual)
        assert not actual.intersection({
            "assets/favicon.ico",
            "assets/images/comfy-cloud-logo.svg",
            "assets/images/comfy-logo-mono.svg",
            "assets/images/comfy-logo-single.svg",
            "assets/images/comfy-logo-wordmark.svg",
            "assets/images/comfy-icon-192.png",
            "assets/images/comfy-icon-512.png",
            "assets/images/cloud-subscription.webm",
            "assets/images/og-image.png",
            "assets/images/partner-nodes-signin.webp",
            "assets/images/civitai.svg",
            "assets/images/gemini.svg",
            "assets/images/hf-logo.svg",
            "assets/images/runway.svg",
        })
        assert not any("favicon_progress_16x16/" in name for name in actual)
        manifest_path, = (name for name in actual if name.startswith("assets/manifest.astrophotoflow-"))
        manifest = json.loads(archive.read(prefix + "web/" + manifest_path))
        assert manifest["name"] == manifest["short_name"] == "AstroPhotoFlow"
        assert {icon["sizes"] for icon in manifest["icons"]} == {"192x192", "512x512"}
        assert all(icon["src"].lstrip("/") in actual for icon in manifest["icons"])
        index = archive.read(prefix + "web/index.html").decode("utf-8")
        assert manifest_path in index and "Loading AstroPhotoFlow" in index
        assert actual == expected
        for name in expected:
            assert archive.read(prefix + "web/" + name) == (resources / name).read_bytes()


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180, check=False)
    if result.returncode:
        raise SystemExit(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / ".artifacts" / "dist")
    parser.add_argument("--report", type=Path, default=ROOT / ".artifacts" / "reports" / "packaging.json")
    parser.add_argument("--rebuilt-wheel-dir", type=Path, default=ROOT / ".artifacts" / "packages" / "from-sdist")
    parser.add_argument("--temp-dir", type=Path)
    parser.add_argument("--sdist-build-python", type=Path)
    args = parser.parse_args()
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    stem = f"{project['name']}-{project['version']}"
    dist = args.dist.resolve()
    wheel = next(dist.glob(stem + "-*.whl"))
    sdist = dist / (stem + ".tar.gz")
    check_wheel(wheel)
    artifacts = ROOT / ".artifacts"
    artifacts.mkdir(exist_ok=True)
    temp_root = args.temp_dir.resolve() if args.temp_dir is not None else artifacts
    if args.temp_dir is not None and temp_root.is_relative_to(ROOT):
        raise SystemExit("--temp-dir must be outside the repository for an external installation check.")
    temp_root.mkdir(parents=True, exist_ok=True)
    report = {
        "wheel": wheel.name,
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "sdist": sdist.name,
        "sdist_sha256": hashlib.sha256(sdist.read_bytes()).hexdigest(),
        "comfyui_archive_hash_matches_manifest": "passed",
        "packaged_native_page_identity_fields": "passed",
    }
    with TemporaryDirectory(prefix="distribution-", dir=temp_root) as temporary:
        work = Path(temporary)
        report["temporary_root"] = str(temp_root)
        report["wheel_install_root"] = str(work / "venv")
        report["sdist_source_root"] = str(work / "source")
        report["repository_external_install"] = not (work / "venv").resolve().is_relative_to(ROOT)
        report["repository_external_sdist_rebuild"] = not (work / "source").resolve().is_relative_to(ROOT)
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        env["PYTHONNOUSERSITE"] = "1"
        env["UV_PROJECT_ENVIRONMENT"] = str(work / "venv")
        env.setdefault("UV_CACHE_DIR", str(artifacts / "cache" / "uv"))
        uv = [sys.executable, "-m", "uv"]
        run(uv + ["sync", "--project", str(ROOT), "--locked", "--no-install-project", "--python", sys.executable], cwd=work, env=env)
        python = work / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run(uv + ["pip", "install", "--python", str(python), "--no-deps", str(wheel)], cwd=work, env=env)

        def smoke() -> None:
            run([str(python), "-m", "astrophotoflow.cli", "--help"], cwd=work, env=env)
            script = """
import importlib.util
import hashlib
import json
from importlib.resources import files
from pathlib import Path
import sys
import astrophotoflow
from astrophotoflow.core.database.schema import SCHEMA_REVISION, upgrade_database, current_revision
from astrophotoflow.core.config import Settings
from astrophotoflow.modules.software.public import get_command_catalog
import astrophotoflow.comfyui
import astrophotoflow.interfaces.mcp.server
assert 'server' not in sys.modules
assert Path(astrophotoflow.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert importlib.util.find_spec('astrophotoflow_service') is None
assert files('astrophotoflow').joinpath('web/index.html').is_file()
assert importlib.util.find_spec('astrophotoflow.backend') is None
vendor = files('astrophotoflow').joinpath('vendor')
from astrophotoflow.contracts.bundles import BundleManifest
from astrophotoflow.contracts.nodes import NodeDefinition
from astrophotoflow.modules.software.metadata import catalog
for package_id, release in catalog().items():
    manifest = BundleManifest.model_validate(release['manifest'])
    assert package_id == manifest.package_id
    for definition in release['nodes']:
        NodeDefinition.model_validate(definition)
    if manifest.commands is not None:
        commands = get_command_catalog(package_id, manifest.software_version)
        assert len({row.command for row in commands}) == len(commands)
from astrophotoflow.modules.data.persistence import schema_metadata
metadata = schema_metadata()
assert 'capture_profile' not in metadata.tables
assert 'project_capture_profile' not in metadata.tables
assert 'capture_profile_id' not in metadata.tables['asset_version'].c
"""
            script += "\ndata = Path('database'); data.mkdir(exist_ok=True)\nsettings = Settings('127.0.0.1', 8190, data.resolve(), ('http://127.0.0.1:8188',), workspace=Path.cwd())\nupgrade_database(settings)\nassert current_revision(settings.database_path) == SCHEMA_REVISION\n"
            run([str(python), "-c", script], cwd=work, env=env)

        smoke()
        report["installed_wheel"] = "passed"
        with tarfile.open(sdist) as archive:
            members = archive.getmembers()
            artifact_files = [member.name for member in members if member.isfile() and "/.artifacts/" in member.name]
            assert artifact_files and all("/.artifacts/build/frontend/" in name for name in artifact_files)
            assert not any("/node_modules/" in member.name or Path(member.name).name in {".env", "service.token"} for member in members)
            archive.extractall(work / "source", filter="data")
        source = work / "source" / stem
        assert (source / ".artifacts/build/frontend/index.html").is_file()
        assert (source / "frontend/packages/astrophotoflow-ui/src/index.ts").is_file()
        assert (source / "frontend/packages/shared-frontend-utils/src/formatUtil.ts").is_file()
        assert (source / "frontend/packages/account-ui/package.json").is_file()
        assert (source / "frontend/LICENSE").is_file()
        assert (source / "frontend/src/assets/astrophotoflow.svg").is_file()
        assert (source / "engine/ComfyUI/LICENSE").is_file()
        assert (source / "docs/api/openapi.json").is_file()
        assert not (source / "src/astrophotoflow/backend").exists()
        assert not (source / "src/astrophotoflow/frontend").exists()
        # Only Python launchers and OS utilities remain on PATH during rebuild.
        env["PATH"] = str(Path(sys.executable).parent)
        if os.name == "nt":
            env["PATH"] += os.pathsep + str(Path(os.environ["SystemRoot"]) / "System32")
        assert shutil.which("node", path=env["PATH"]) is None
        report["node_available_during_sdist_rebuild"] = False
        output = args.rebuilt_wheel_dir.resolve()
        output.mkdir(parents=True, exist_ok=True)
        if args.sdist_build_python is None:
            sdist_build_python = Path(sys.executable)
            build_options = ["--wheel", "--installer", "uv"]
            sdist_build_env = env
            report["sdist_build_isolated"] = True
        else:
            sdist_build_python = args.sdist_build_python.resolve()
            build_options = ["--no-isolation", "--wheel"]
            sdist_build_env = env.copy()
            sdist_build_env["PYTHONPATH"] = os.pathsep.join(str(path) for path in site.getsitepackages())
            report["sdist_build_isolated"] = False
        report["sdist_build_python"] = str(sdist_build_python)
        run([str(sdist_build_python), "-m", "build", *build_options, "--outdir", str(output), str(source)], cwd=work, env=sdist_build_env)
        rebuilt = next(output.glob(stem + "-*.whl"))
        check_wheel(rebuilt)
        run(uv + ["pip", "install", "--python", str(python), "--no-deps", "--reinstall", str(rebuilt)], cwd=work, env=env)
        smoke()
        report["sdist_rebuilt_wheel"] = "passed"
        report["rebuilt_wheel_sha256"] = hashlib.sha256(rebuilt.read_bytes()).hexdigest()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
