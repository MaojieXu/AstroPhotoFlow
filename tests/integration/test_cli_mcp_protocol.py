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
    config_path = workspace / "config.toml"
    config_path.write_text(
        "[server]\n"
        f'host = "127.0.0.1"\nport = {port}\n\n'
        "[storage]\n"
        f'data_dir = "{data_dir.as_posix()}"\n\n'
        "[comfyui]\n"
        'allowed_origins = ["http://127.0.0.1:8188"]\n',
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

    service = {"config_path": config_path, "data_dir": data_dir, "env": env, "log_path": log_path, "port": port, "process": process}
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
                assert {tool.name for tool in listed_tools.tools} == {
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
