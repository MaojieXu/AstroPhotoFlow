from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image
import pytest


ROOT = Path(__file__).resolve().parents[2]
FINAL_TASK_STATUSES = {"completed", "completed_with_errors", "failed", "cancelled", "interrupted"}


def _entrypoint(name: str) -> str:
    suffix = ".exe" if os.name == "nt" else ""
    return str(Path(sys.executable).with_name(name + suffix))


def _write_png(path: Path) -> None:
    Image.new("RGB", (16, 16), color=(32, 64, 96)).save(path, format="PNG")


def _service_logs(service: dict) -> str:
    return service["log_path"].read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def service(tmp_path_factory):
    workspace = tmp_path_factory.mktemp("apf-integration")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    data_dir = workspace / "data"
    sources = workspace / "sources"
    sources.mkdir()
    config_path = workspace / "config.toml"
    config_path.write_text(
        "[server]\n"
        f'host = "127.0.0.1"\nport = {port}\n\n'
        "[storage]\n"
        f'data_dir = "{data_dir.as_posix()}"\n\n'
        "[comfyui]\n"
        'allowed_origins = ["http://127.0.0.1:8188"]\n'
        "\n[[imports.roots]]\n"
        'id = "science"\n'
        f'path = "{sources.as_posix()}"\n',
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["ASTROPHOTOFLOW_CONFIG"] = str(config_path)
    log_path = workspace / "service.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [_entrypoint("apf-service"), "serve"],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )

    service = {"sources": sources, "config_path": config_path, "data_dir": data_dir, "env": env, "log_path": log_path, "port": port, "process": process}
    try:
        deadline = time.monotonic() + 30
        token_path = data_dir / "service.token"
        while time.monotonic() < deadline and process.poll() is None:
            if token_path.is_file():
                token = token_path.read_text(encoding="utf-8").strip()
                try:
                    response = httpx.get(
                        f"http://127.0.0.1:{port}/api/v1/health",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=1,
                        trust_env=False,
                    )
                except httpx.ConnectError:
                    time.sleep(0.1)
                    continue
                if response.status_code == 200:
                    service["token"] = token
                    break
            time.sleep(0.1)
        else:
            pytest.fail(f"apf-service did not become healthy.\nService log:\n{_service_logs(service)}")
        yield service
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def _cli_json(service: dict, *args: str) -> dict:
    try:
        result = subprocess.run(
            [_entrypoint("apf"), *args],
            cwd=ROOT,
            env=service["env"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"apf {' '.join(args)} timed out: {exc}\nService log:\n{_service_logs(service)}")
    assert result.returncode == 0, f"apf {' '.join(args)} failed: {result.stderr}\nService log:\n{_service_logs(service)}"
    return json.loads(result.stdout)


def _wait_cli_task(service: dict, task_id: str) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        task = _cli_json(service, "task", task_id)
        if task["status"] in FINAL_TASK_STATUSES:
            assert task["status"] == "completed", f"Import task failed: {task}\nService log:\n{_service_logs(service)}"
            return task
        time.sleep(0.2)
    pytest.fail(f"Import task {task_id} did not finish within 30 seconds.\nService log:\n{_service_logs(service)}")


def test_apf_cli_imports_and_queries_parameters(service, tmp_path):
    help_result = subprocess.run(
        [_entrypoint("apf"), "--help"], cwd=ROOT, env=service["env"], capture_output=True, text=True, encoding="utf-8", check=False
    )
    assert help_result.returncode == 0
    assert "import-photo" in help_result.stdout

    photo = tmp_path / "cli-synthetic.png"
    _write_png(photo)
    accepted = _cli_json(service, "import-photo", str(photo))
    task = _wait_cli_task(service, accepted["task_id"])
    assert task["items"][0]["asset_id"]

    listed = _cli_json(service, "assets", "list", "--limit", "10")
    asset_id = str(task["items"][0]["asset_id"])
    assert asset_id in {str(item["id"]) for item in listed["items"]}
    asset = _cli_json(service, "assets", "get", asset_id)
    assert asset["parameters"]["exposure_seconds"] is None

    updated = _cli_json(service, "assets", "parameters", asset_id, "--base-revision", str(asset["revision"]), "--exposure-seconds", "0")
    assert updated["parameters"]["exposure_seconds"] == 0
    assert _cli_json(service, "assets", "get", asset_id)["parameters"]["exposure_seconds"] == 0


def _result_text(result) -> str:
    return "\n".join(block.text for block in result.content if hasattr(block, "text"))


def _tool_data(result, service: dict) -> dict:
    assert not result.is_error, f"MCP tool failed: {_result_text(result)}\nService log:\n{_service_logs(service)}"
    assert result.structured_content is not None, f"MCP tool omitted structured output: {_result_text(result)}"
    return result.structured_content


async def _wait_mcp_task(session: ClientSession, service: dict, task_id: str) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            result = await session.call_tool("get_import_task", {"task_id": task_id}, read_timeout_seconds=5)
        except TimeoutError as exc:
            pytest.fail(f"Reading import task {task_id} timed out: {exc}\nService log:\n{_service_logs(service)}")
        task = _tool_data(result, service)
        if task["status"] in FINAL_TASK_STATUSES:
            assert task["status"] == "completed", f"Import task failed: {task}\nService log:\n{_service_logs(service)}"
            return task
        await asyncio.sleep(0.2)
    pytest.fail(f"Import task {task_id} did not finish within 30 seconds.\nService log:\n{_service_logs(service)}")


def test_apf_mcp_stdio_tools_and_parameter_patch_protocol(service, tmp_path):
    async def exercise_protocol():
        params = StdioServerParameters(command=_entrypoint("apf"), args=["mcp"], env=service["env"], cwd=str(ROOT))
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                listed_tools = await session.list_tools()
                assert {tool.name for tool in listed_tools.tools} >= {
                    "import_photo", "get_import_task", "list_assets", "get_asset", "update_asset_parameters"
                }

                photo = tmp_path / "mcp-synthetic.png"
                _write_png(photo)
                accepted = _tool_data(await session.call_tool("import_photo", {"path": str(photo)}, read_timeout_seconds=10), service)
                task = await _wait_mcp_task(session, service, accepted["task_id"])
                asset_id = str(task["items"][0]["asset_id"])

                assets = _tool_data(await session.call_tool("list_assets", {"limit": 50, "offset": 0}, read_timeout_seconds=5), service)
                assert asset_id in {str(item["id"]) for item in assets["items"]}
                asset = _tool_data(await session.call_tool("get_asset", {"asset_id": asset_id}, read_timeout_seconds=5), service)
                assert asset["revision"] == 1

                first = _tool_data(
                    await session.call_tool(
                        "update_asset_parameters",
                        {"asset_id": asset_id, "base_revision": 1, "parameters": {"gain": 0, "exposure_seconds": 0}},
                        read_timeout_seconds=5,
                    ),
                    service,
                )
                assert first["parameters"]["gain"] == 0
                assert first["parameters"]["exposure_seconds"] == 0

                cleared = _tool_data(
                    await session.call_tool(
                        "update_asset_parameters",
                        {"asset_id": asset_id, "base_revision": 2, "parameters": {"gain": None}},
                        read_timeout_seconds=5,
                    ),
                    service,
                )
                assert cleared["parameters"]["gain"] is None
                assert cleared["parameters"]["exposure_seconds"] == 0

                stale = await session.call_tool(
                    "update_asset_parameters",
                    {"asset_id": asset_id, "base_revision": 2, "parameters": {"exposure_seconds": 12}},
                    read_timeout_seconds=5,
                )
                assert stale.is_error
                assert "REVISION_CONFLICT" in _result_text(stale)
                current = _tool_data(await session.call_tool("get_asset", {"asset_id": asset_id}, read_timeout_seconds=5), service)
                assert current["revision"] == 3
                assert current["parameters"]["exposure_seconds"] == 0

    asyncio.run(exercise_protocol())


def test_apf_mcp_business_domains_protocol(service, tmp_path):
    async def exercise_protocol():
        params = StdioServerParameters(command=_entrypoint("apf"), args=["mcp"], env=service["env"], cwd=str(ROOT))
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()

                async def call(name, **arguments):
                    return _tool_data(await session.call_tool(name, arguments, read_timeout_seconds=10), service)

                # Real discriminated equipment schemas, registered refs and inline snapshots.
                equipment = {}
                for kind in ("camera", "telescope", "filter", "mount", "accessory", "optical_system"):
                    created = await call("create_equipment", body={"kind": kind, "name": "SDK " + kind})
                    equipment[kind] = created
                    assert (await call("get_equipment", equipment_id=created["id"]))["kind"] == kind
                assert (await call("list_equipment", kind="camera", limit=1))["total"] >= 1
                setup = await call("create_equipment_setup", body={
                    "name": "SDK setup", "components": [
                        {"source": "registered", "equipment_id": equipment["camera"]["id"]},
                        {"source": "inline", "equipment": {"kind": "accessory", "name": "Inline only"}},
                    ],
                })
                assert (await call("list_equipment", q="Inline only"))["total"] == 0
                assert (await call("get_equipment_setup", setup_id=setup["id"]))["components"] == setup["components"]
                assert (await call("list_equipment_setups", q="SDK setup"))["total"] == 1
                preset = await call("create_capture_preset", setup_id=setup["id"], body={
                    "name": "SDK night", "classification": {"frame_class": "subframe", "frame_type": "light"},
                    "parameters": {"gain": 0, "exposure_seconds": 30},
                })
                assert (await call("get_capture_preset", preset_id=preset["id"]))["equipment_setup_id"] == setup["id"]
                assert (await call("list_capture_presets", equipment_setup_id=setup["id"]))["total"] == 1

                paths = [tmp_path / "night-one.png", tmp_path / "night-two.png"]
                for path in paths:
                    _write_png(path)
                accepted = await call("import_photos", paths=[str(path) for path in paths], options={
                    "capture_preset_id": preset["id"], "dataset_name": "SDK night batch",
                })
                task = await _wait_mcp_task(session, service, accepted["task_id"])
                assert len(task["items"]) == 2 and task["report"]["registration"]["completed"]
                assert (await call("get_import_task", task_id=task["id"], items_limit=1, items_offset=1))["items"][0]["id"] == task["items"][1]["id"]
                assert (await call("list_import_tasks", limit=1))["items"]
                asset_ids = [item["asset_id"] for item in task["items"]]
                version_ids = [item["asset_version_id"] for item in task["items"]]
                asset = await call("get_asset", asset_id=asset_ids[0])
                assert asset["classification"]["frame_type"] == "light"
                assert asset["parameters"]["gain"] == 0
                await call("update_capture_preset", preset_id=preset["id"], body={"base_revision": 1, "parameters": {"gain": 88}})
                assert (await call("get_asset", asset_id=asset_ids[0]))["parameters"]["gain"] == 0
                asset = await call("update_asset", asset_id=asset_ids[0], body={
                    "base_revision": asset["revision"], "notes": "temporary", "parameters": {"exposure_seconds": 0},
                })
                asset = await call("update_asset", asset_id=asset_ids[0], body={
                    "base_revision": asset["revision"], "notes": None,
                    "classification": {"frame_class": "subframe", "frame_type": "light"},
                })
                assert asset["notes"] is None and asset["parameters"]["exposure_seconds"] == 0
                assert (await call("get_asset_version", asset_id=asset_ids[0], version_id=version_ids[0]))["availability"] == "available"
                assert (await call("list_asset_versions", asset_id=asset_ids[0]))["total"] == 1
                assert (await call("list_library_items", q="SDK night batch"))["items"]

                # File headers override preset defaults; no client-side Light/subframe override.
                import numpy as np
                from astropy.io import fits
                master_path = tmp_path / "master-dark.fits"
                hdu = fits.PrimaryHDU(np.arange(256, dtype=np.float32).reshape(16, 16))
                hdu.header["IMAGETYP"] = "Master Dark"
                hdu.writeto(master_path)
                master_task = await _wait_mcp_task(session, service, (await call(
                    "import_photo", path=str(master_path), options={"capture_preset_id": preset["id"]}
                ))["task_id"])
                master = await call("get_asset", asset_id=master_task["items"][0]["asset_id"])
                assert master["classification"] == {"frame_class": "masterframe", "frame_type": "dark"}
                targets = await call("list_calibration_targets", frame_type="dark", limit=1, offset=0)
                assert targets["items"][0]["target"] == {"kind": "asset_version", "id": master["current_version_id"]}

                group = await call("create_dataset", body={"name": "SDK logical group", "asset_version_ids": version_ids})
                assert (await call("list_datasets", q=group["name"]))["total"] == 1
                bound = await call("publish_dataset_version", dataset_id=group["id"], body={
                    "base_revision": group["revision"], "asset_version_ids": version_ids,
                    "calibration_defaults": {"dark": targets["items"][0]["target"]},
                    "member_calibration_overrides": {version_ids[0]: {"dark": None}},
                })
                assert bound["calibration_defaults"]["dark"]["id"] == master["current_version_id"]
                assert bound["members"][0]["calibration_overrides"] == {"dark": None}
                assert (await call("get_dataset_version", dataset_id=group["id"], version_id=bound["id"])) == bound
                assert (await call("list_dataset_versions", dataset_id=group["id"]))["total"] == 2
                group = await call("get_dataset", dataset_id=group["id"])
                revisions = [(await call("get_asset", asset_id=identity))["revision"] for identity in asset_ids]
                edited = await call("update_dataset_members", dataset_id=group["id"], body={
                    "base_revision": group["revision"], "base_version_id": bound["id"],
                    "members": [{"asset_id": identity, "revision": revision} for identity, revision in zip(asset_ids, revisions)],
                    "parameters": {"gain": 0},
                })
                assert len(edited["assets"]) == 2 and all(item["parameters"]["gain"] == 0 for item in edited["assets"])

                project = await call("create_project", body={"name": "SDK M31", "target_name": "M31"})
                assert (await call("list_projects", q="SDK M31"))["total"] == 1
                asset_ref = await call("add_project_asset", project_id=project["id"], body={
                    "base_revision": 1, "asset_version_id": version_ids[0],
                })
                group_now = await call("get_dataset", dataset_id=group["id"])
                dataset_ref = await call("add_project_dataset", project_id=project["id"], body={
                    "base_revision": 2, "dataset_id": group["id"], "dataset_version_id": group_now["current_version_id"],
                })
                assert (await call("list_project_assets", project_id=project["id"]))["items"][0]["id"] == asset_ref["id"]
                assert (await call("get_project_asset", project_id=project["id"], reference_id=asset_ref["id"]))["asset_version_id"] == version_ids[0]
                assert (await call("list_project_datasets", project_id=project["id"]))["total"] == 1
                assert (await call("get_project_dataset", project_id=project["id"], reference_id=dataset_ref["id"]))["dataset_version_id"] == group_now["current_version_id"]
                await call("remove_project_asset", project_id=project["id"], reference_id=asset_ref["id"], body={"base_revision": 3})
                await call("remove_project_dataset", project_id=project["id"], reference_id=dataset_ref["id"], body={"base_revision": 4})
                assert (await call("get_project", project_id=project["id"]))["revision"] == 5
                assert (await call("update_project", project_id=project["id"], body={"base_revision": 5, "status": "archived"}))["status"] == "archived"

                # Reference-only folder import and selected retry preserve source and asset identity.
                night = service["sources"] / "sdk-night"
                night.mkdir()
                _write_png(night / "good.png")
                (night / "broken.fits").write_bytes(b"invalid FITS")
                assert (await call("list_import_roots"))["items"][0]["id"] == "science"
                assert (await call("browse_import_root", root_id="science", path="sdk-night"))["total"] == 2
                local = await call("import_local", body={"sources": [{"root_id": "science", "path": "sdk-night"}], "storage_mode": "reference"})
                for _ in range(100):
                    local_task = await call("get_import_task", task_id=local["task_id"])
                    if local_task["status"] in FINAL_TASK_STATUSES:
                        break
                    await asyncio.sleep(0.1)
                assert local_task["status"] == "completed_with_errors"
                broken = next(item for item in local_task["items"] if item["source_path"].endswith("broken.fits"))
                hdu.writeto(night / "broken.fits", overwrite=True)
                retry = await call("retry_import_items", task_id=local_task["id"], body={"item_ids": [broken["id"]]})
                repaired = await _wait_mcp_task(session, service, retry["task_id"])
                assert repaired["items"][0]["retry_of_item_id"] == broken["id"]
                if broken["asset_id"]:
                    assert repaired["items"][0]["asset_id"] == broken["asset_id"]
                assert (night / "good.png").is_file()
                for tool_name in ("cancel_import_task", "resume_import_task"):
                    rejected = await session.call_tool(tool_name, {"task_id": task["id"]})
                    assert rejected.is_error and "TASK_STATE_CONFLICT" in _result_text(rejected)
                    assert "request_id=" in _result_text(rejected)

                # Reversible trash, then explicit fresh preview + permanent fingerprint.
                disposable = tmp_path / "disposable.png"
                _write_png(disposable)
                disposable_task = await _wait_mcp_task(session, service, (await call("import_photo", path=str(disposable)))["task_id"])
                disposable_asset = await call("get_asset", asset_id=disposable_task["items"][0]["asset_id"])
                assert disposable_asset["classification"] == {"frame_class": None, "frame_type": None}
                remove = {"items": [{"entry_type": "asset", "id": disposable_asset["id"], "revision": disposable_asset["revision"], "current_version_id": disposable_asset["current_version_id"]}]}
                await call("remove_library_items", body=remove)
                trash = await call("list_trash")
                entry = next(item for item in trash["items"] if item["id"] == disposable_asset["id"])
                selection = {"items": [{key: entry[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id", "source_dataset_id")}]}
                await call("restore_trash", body=selection)
                await call("remove_library_items", body=remove)
                entry = next(item for item in (await call("list_trash"))["items"] if item["id"] == disposable_asset["id"])
                selection = {"items": [{key: entry[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id", "source_dataset_id")}]}
                preview = await call("preview_trash_delete", body=selection)
                assert preview["photo_count"] == 1 and preview["managed_file_count"] >= 1 and not preview["references"]
                deleted = await call("delete_trash", body={**selection, "preview_fingerprint": preview["preview_fingerprint"]})
                assert deleted["deleted_file_count"] == preview["managed_file_count"] and not deleted["failed"]
                assert disposable.is_file()

                for kind, item in equipment.items():
                    assert (await call("update_equipment", equipment_id=item["id"], body={"kind": kind, "base_revision": 1, "status": "archived"}))["status"] == "archived"
                assert (await call("update_equipment_setup", setup_id=setup["id"], body={"base_revision": 1, "status": "archived"}))["status"] == "archived"
                assert (await call("update_capture_preset", preset_id=preset["id"], body={"base_revision": 2, "status": "archived"}))["status"] == "archived"
                assert (await call("update_dataset", dataset_id=group["id"], body={"base_revision": group_now["revision"], "status": "archived"}))["status"] == "archived"

    asyncio.run(exercise_protocol())


def test_apf_cli_structured_domain_workflow(service, tmp_path):
    def command(*args):
        return _cli_json(service, *args)

    def payload(value):
        return json.dumps(value)

    camera = command("equipment", "create", "--data", payload({"kind": "camera", "name": "CLI Camera"}))
    assert command("equipment", "list", "--kind", "camera", "--q", "CLI Camera")["total"] == 1
    setup = command("setups", "create", "--data", payload({
        "name": "CLI setup", "components": [{"source": "registered", "equipment_id": camera["id"]}],
    }))
    preset = command("presets", "create", setup["id"], "--data", payload({
        "name": "CLI preset", "classification": {"frame_class": "subframe", "frame_type": "light"},
        "parameters": {"gain": 0},
    }))
    assert command("presets", "list", "--equipment-setup-id", setup["id"])["total"] == 1
    paths = [tmp_path / "cli-bulk-a.png", tmp_path / "cli-bulk-b.png"]
    for path in paths:
        _write_png(path)
    task = _wait_cli_task(service, command("import-photos", *map(str, paths), "--data", payload({
        "capture_preset_id": preset["id"], "dataset_name": "CLI batch",
    }))["task_id"])
    assert command("tasks", "get", task["id"], "--items-limit", "1", "--items-offset", "1")["items"][0]["id"] == task["items"][1]["id"]
    assert command("assets", "get", task["items"][0]["asset_id"])["parameters"]["gain"] == 0
    versions = [item["asset_version_id"] for item in task["items"]]
    group = command("datasets", "create", "--data", payload({"name": "CLI logical group", "asset_version_ids": versions}))
    publication = command("datasets", "publish", group["id"], "--data", payload({
        "base_revision": group["revision"], "asset_version_ids": versions, "calibration_defaults": {},
        "member_calibration_overrides": {versions[0]: {"dark": None}},
    }))
    assert command("datasets", "version", group["id"], publication["id"])["members"][0]["calibration_overrides"] == {"dark": None}
    project = command("projects", "create", "--data", payload({"name": "CLI project"}))
    reference = command("projects", "add-dataset", project["id"], "--data", payload({
        "base_revision": project["revision"], "dataset_id": group["id"], "dataset_version_id": publication["id"],
    }))
    assert command("projects", "datasets", project["id"])["items"][0]["id"] == reference["id"]
    command("projects", "remove-dataset", project["id"], reference["id"], "--data", payload({"base_revision": 2}))
    assert command("projects", "archive", project["id"], "--base-revision", "3")["status"] == "archived"
    assert command("presets", "archive", preset["id"], "--base-revision", "1")["status"] == "archived"
    assert command("setups", "archive", setup["id"], "--base-revision", "1")["status"] == "archived"
    assert command("equipment", "archive", camera["id"], "--kind", "camera", "--base-revision", "1")["status"] == "archived"
    rejected = subprocess.run([_entrypoint("apf"), "assets", "patch", task["items"][0]["asset_id"], "--data", '{"base_revision":0}'],
                              cwd=ROOT, env=service["env"], capture_output=True, text=True, check=False)
    assert rejected.returncode == 1 and "base_revision" in rejected.stderr
