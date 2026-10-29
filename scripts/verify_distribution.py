"""Verify installed wheel resources and a Node-free wheel rebuild from sdist."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import site
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
            "interfaces/http/cli.py", "core/database/alembic.ini", "core/database/alembic/env.py", "contracts/assets.py", "modules/data/public.py", "modules/data/routes.py",
            "contracts/software.py", "contracts/nodes.py", "modules/software/public.py", "modules/nodes/public.py",
            "core/database/alembic/versions/0008_asset_equipment_snapshot.py",
            "core/database/alembic/versions/0009_remove_legacy_capture_profiles.py",
            "comfyui/proxy.py", "web/index.html", "vendor/comfyui-source.json",
            "vendor/comfyui-0.42.0.zip", "vendor/comfyui-0.42.0-windows-py312.lock",
            "vendor/siril-1.4.4-commands.json", "vendor/siril-1.4.4-manifest.json",
            "vendor/siril-1.4.4-command-assessments.json",
            "vendor/siril-1.4.4-node-definitions.json",
        }
        assert {prefix + name for name in required} <= names, f"Missing product resources in {path.name}"
        assert not any(name.startswith(("astrophotoflow_service/", "tests/", "astrophotoflow/frontend/", "astrophotoflow/backend/", "astrophotoflow/agent_tools/", "astrophotoflow/client_domains/")) for name in names)
        assert not any("node_modules/" in name or "/__pycache__/" in name for name in names)
        assert prefix + "backend/capture_profiles.py" not in names
        assert not any(name.startswith(prefix + "comfyui/extension/") for name in names)
        comfy_manifest = json.loads(archive.read(prefix + "vendor/comfyui-source.json"))
        comfy_archive_bytes = archive.read(prefix + "vendor/comfyui-0.42.0.zip")
        assert hashlib.sha256(comfy_archive_bytes).hexdigest() == comfy_manifest["sha256"]
        with zipfile.ZipFile(io.BytesIO(comfy_archive_bytes)) as engine:
            packaged_server = engine.read("ComfyUI/server.py")
            assert b"apf_page_id_by_client" in packaged_server and b"apf_page_token" in packaged_server
        resources = ROOT / ".artifacts/build/frontend"
        expected = {path.relative_to(resources).as_posix() for path in resources.rglob("*") if path.is_file()}
        actual = {name.removeprefix(prefix + "web/") for name in names if name.startswith(prefix + "web/")}
        assert actual == expected
        for name in expected:
            assert archive.read(prefix + "web/" + name) == (resources / name).read_bytes()


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
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
        env["UV_CACHE_DIR"] = str(artifacts / "cache" / "uv")
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
from astrophotoflow.modules.software.public import get_command_catalog, list_siril_commands
import astrophotoflow.comfyui
import astrophotoflow.interfaces.mcp.server
assert 'server' not in sys.modules
assert Path(astrophotoflow.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert importlib.util.find_spec('astrophotoflow_service') is None
assert files('astrophotoflow').joinpath('web/index.html').is_file()
assert importlib.util.find_spec('astrophotoflow.backend') is None
vendor = files('astrophotoflow').joinpath('vendor')
catalog_manifest = json.loads(vendor.joinpath('siril-1.4.4-manifest.json').read_text(encoding='utf-8'))
catalog_bytes = vendor.joinpath('siril-1.4.4-commands.json').read_bytes()
catalog = json.loads(catalog_bytes)
assessment_bytes = vendor.joinpath(catalog_manifest['command_assessments_file']).read_bytes()
assessments = json.loads(assessment_bytes)
assert hashlib.sha256(assessment_bytes).hexdigest().upper() == catalog_manifest['command_assessments_file_sha256'].upper()
assert assessments['package_id'] == catalog_manifest['package_id']
assert assessments['version'] == catalog_manifest['version']
assert assessments['source_commands_file_sha256'].upper() == catalog_manifest['commands_file_sha256'].upper()
assessment_names = [item['command'] for item in assessments['commands']]
assert len(assessment_names) == catalog_manifest['command_assessment_records']
assert len(assessment_names) == len(set(assessment_names))
assert set(assessment_names) == {item['command'] for item in catalog}
assessment_fields = {'parameter_details', 'structured_parameter_defaults_ranges', 'single_image_sequence_context', 'input_output_semantics', 'headless_status', 'dependencies', 'security_risk', 'semantic_review_status', 'node_definition_status', 'node_definition_reason', 'node_generation_status', 'node_generation_reason', 'registry_load_status', 'registry_load_reason', 'runtime_test_status', 'runtime_test_reason'}
assert all(set(item['assessment']) == assessment_fields and all(isinstance(value, str) and value for value in item['assessment'].values()) for item in assessments['commands'])
node_definitions = json.loads(vendor.joinpath('siril-1.4.4-node-definitions.json').read_text(encoding='utf-8'))
catalog_names = [item['command'] for item in catalog]
assert hashlib.sha256(catalog_bytes).hexdigest().upper() == catalog_manifest['commands_file_sha256'].upper()
assert len(catalog_names) == catalog_manifest['indexed_commands']
assert len(catalog_names) == len(set(catalog_names))
assert sum(item['scriptable'] is True for item in catalog) == catalog_manifest['scriptable_commands']
assert sum(item['scriptable'] is False for item in catalog) == catalog_manifest['non_scriptable_commands']
assert all(item['scriptable'] is not None for item in catalog)
assert isinstance(node_definitions, list) and node_definitions
from astrophotoflow.contracts.nodes import NodeDefinition
validated_definitions = [NodeDefinition.model_validate(item) for item in node_definitions]
assert len(validated_definitions) == len(node_definitions)
public_commands = list_siril_commands()
assert public_commands == get_command_catalog('siril', '1.4.4')
assert len(public_commands) == catalog_manifest['indexed_commands']
from astrophotoflow.modules.data.models import Base
assert 'capture_profile' not in Base.metadata.tables
assert 'project_capture_profile' not in Base.metadata.tables
assert 'capture_profile_id' not in Base.metadata.tables['asset_version'].c
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
