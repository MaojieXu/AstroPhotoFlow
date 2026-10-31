from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from astrophotoflow.contracts.assets import AssetPatch
from astrophotoflow.contracts.datasets import DatasetMembersCreate
from astrophotoflow.contracts.imports import ImportCreate
from astrophotoflow.client import AssetClient, ServiceApiError
from astrophotoflow.contracts.imports import PhotoImportOptions
from astrophotoflow.contracts.trash import EquipmentDelete, EquipmentDeleteSelection
from astrophotoflow.interfaces.cli.main import _parser
from astrophotoflow.interfaces.cli.commands import run
from astrophotoflow.contracts.workflows import CanvasAddRequest


@pytest.fixture
def client():
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path == "/api/v1/uploads":
            return httpx.Response(202, json={"task_id": "upload-task", "status": "queued"})
        if request.url.path.endswith("/previews/display"):
            return httpx.Response(200, content=b"jpeg", headers={"Content-Type": "image/jpeg"})
        return httpx.Response(200, json={"ok": True})

    client = AssetClient.__new__(AssetClient)
    client.client = httpx.Client(base_url="http://service/api/v1", transport=httpx.MockTransport(handle))
    with client:
        yield client, calls


def body(request):
    return json.loads(request.content)


def test_cli_absolute_local_source_does_not_require_root_id(client):
    api, calls = client
    path = str(Path.cwd() / "local-image.fits")
    request = {"sources": [{"path": path}], "storage_mode": "managed"}
    args = _parser().parse_args(["imports", "local", "--data", json.dumps(request)])
    assert run(api, args) == {"ok": True}
    assert calls[0].url.path == "/api/v1/imports"
    assert body(calls[0]) == request


def test_canvas_cli_and_client_preserve_explicit_target_and_operation_id(client):
    api, calls = client
    request = {"operation_id": str(uuid4()), "page_id": str(uuid4()), "workflow_id": str(uuid4()), "graph_id": str(uuid4()), "content_token": "current", "source": {"entry_type": "asset", "id": str(uuid4()), "version_id": str(uuid4())}}
    args = _parser().parse_args(["canvas", "add-data", "--data", json.dumps(request)])
    assert run(api, args) == {"ok": True}
    api.get_canvas_request(request["operation_id"])
    api.list_canvas_pages()
    assert [(call.method, call.url.path) for call in calls] == [
        ("POST", "/api/v1/canvas/requests"),
        ("GET", "/api/v1/canvas/requests/" + request["operation_id"]),
        ("GET", "/api/v1/canvas/pages"),
    ]
    assert body(calls[0]) == CanvasAddRequest.model_validate(request).model_dump(mode="json", exclude_unset=True)


@pytest.mark.parametrize('edit', [
    {'action': 'connect', 'source_node_id': 10, 'source_port': 'science', 'target_node_id': 11, 'target_port': 'image'},
    {'action': 'delete_node', 'node_id': 11},
])
def test_canvas_cli_edits_use_target_and_content_without_control_marker(client, edit):
    api, calls = client
    request = {key: str(uuid4()) for key in ('operation_id', 'page_id', 'workflow_id', 'graph_id')} | {
        'content_token': 'current',
        'edit': edit,
    }
    args = _parser().parse_args(['canvas', 'edit', '--data', json.dumps(request)])
    assert run(api, args) == {'ok': True}
    assert calls[0].url.path == '/api/v1/canvas/graph'
    assert body(calls[0]) == request


def test_equipment_direct_delete_passes_selection_and_current_preview(client):
    api, calls = client
    items = [{"entry_type": "equipment", "id": str(uuid4()), "revision": 2}]
    api.preview_equipment_delete(EquipmentDeleteSelection(items=items))
    api.delete_equipment_entries(EquipmentDelete(items=items, preview_fingerprint="current"))
    assert [(request.method, request.url.path) for request in calls] == [
        ("POST", "/api/v1/equipment-management/delete-preview"),
        ("POST", "/api/v1/equipment-management/delete"),
    ]
    assert body(calls[0]) == {"items": items}
    assert body(calls[1]) == {"items": items, "preview_fingerprint": "current"}


def test_bulk_upload_preserves_order_and_automatic_classification(client, tmp_path):
    api, calls = client
    photos = [tmp_path / "one.png", tmp_path / "two.png"]
    for index, photo in enumerate(photos):
        photo.write_bytes(bytes([index]) * 3)
    api.import_photos(photos)
    assert body(calls[0]) == {"files": [{"name": "one.png", "size": 3}, {"name": "two.png", "size": 3}]}
    assert [request.url.path for request in calls] == [
        "/api/v1/uploads", "/api/v1/uploads/upload-task/0", "/api/v1/uploads/upload-task/1", "/api/v1/uploads/upload-task/start",
    ]
    assert calls[1].content == bytes([0]) * 3 and calls[2].content == bytes([1]) * 3
    calls.clear()
    api.import_photo(photos[0], PhotoImportOptions(classification={"frame_type": None}, parameters={"gain": 0}))
    assert body(calls[0])["classification"] == {"frame_type": None}
    assert body(calls[0])["parameters"] == {"gain": 0}


def test_sparse_patch_and_fixed_calibration_maps(client):
    api, calls = client
    asset, member, target, group = [str(uuid4()) for _ in range(4)]
    api.update_asset(asset, AssetPatch(base_revision=3, notes=None, parameters={"gain": 0}))
    assert body(calls[-1]) == {"base_revision": 3, "notes": None, "parameters": {"gain": 0}}
    api.publish_dataset_version(group, DatasetMembersCreate(
        base_revision=4, asset_version_ids=[member], calibration_defaults={},
        member_calibration_overrides={member: {"dark": None, "flat": {"kind": "dataset_version", "id": target}}},
    ))
    assert body(calls[-1]) == {
        "base_revision": 4, "asset_version_ids": [member], "calibration_defaults": {},
        "member_calibration_overrides": {member: {"dark": None, "flat": {"kind": "dataset_version", "id": target}}},
    }
    api.import_local(ImportCreate(sources=[{"root_id": "night", "path": "2026-10-25"}], storage_mode="reference"))
    assert body(calls[-1]) == {"sources": [{"root_id": "night", "path": "2026-10-25"}], "storage_mode": "reference"}


def test_optional_query_values_are_omitted_without_dropping_zero(client):
    api, calls = client
    api.browse_import_root("night", path="", limit=10, offset=0)
    assert dict(calls[-1].url.params) == {"path": "", "limit": "10", "offset": "0"}
    api.list_import_tasks()
    assert "status" not in calls[-1].url.params


def test_service_errors_retain_request_id_and_fields(client):
    api, _ = client
    response = httpx.Response(409, json={
        "error": {"code": "REVISION_CONFLICT", "message": "changed", "fields": [{"path": "base_revision", "message": "stale"}]},
        "request_id": "request-123",
    })
    with pytest.raises(ServiceApiError) as caught:
        api._result(response)
    assert caught.value.status == 409 and caught.value.code == "REVISION_CONFLICT"
    assert caught.value.request_id == "request-123" and caught.value.fields[0]["path"] == "base_revision"


def test_software_command_catalog_client_uses_the_exact_package_version():
    calls = []
    command = {
        "command": "autostretch", "scriptable": True, "syntax": "autostretch [-linked]",
        "description": "Auto-stretches the currently loaded image.",
        "url": "https://siril.readthedocs.io/en/stable/Commands.html#autostretch",
        "assessment": next(row["assessment"] for row in json.loads((Path(__file__).resolve().parents[2] / "src/astrophotoflow/vendor/siril-1.4.4-command-assessments.json").read_text(encoding="utf-8"))["commands"] if row["command"] == "autostretch"),
    }

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json=[command])

    api = AssetClient.__new__(AssetClient)
    api.client = httpx.Client(base_url="http://service/api/v1", transport=httpx.MockTransport(handle))
    with api:
        result = api.list_software_commands("siril", "1.4.4")
    assert result[0].command == "autostretch"
    assert calls[0].method == "GET"
    assert calls[0].url.path == "/api/v1/software/packages/siril/versions/1.4.4/commands"


def test_cli_json_file_body_and_archive_use_backend_schemas(client, tmp_path):
    api, calls = client
    identity = str(uuid4())
    data = tmp_path / "patch.json"
    data.write_text(json.dumps({"base_revision": 7, "notes": None, "parameters": {"gain": 0}}), encoding="utf-8")
    args = _parser().parse_args(["assets", "patch", identity, "--data", "@" + str(data)])
    run(api, args)
    assert body(calls[-1]) == {"base_revision": 7, "notes": None, "parameters": {"gain": 0}}
    args = _parser().parse_args(["equipment", "archive", identity, "--kind", "mount", "--base-revision", "2"])
    run(api, args)
    assert body(calls[-1]) == {"kind": "mount", "base_revision": 2, "status": "archived"}
    args = _parser().parse_args(["equipment", "create", "--data", '{"kind":"telescope","name":"Scope","specs":{"aperture_mm":80}}'])
    run(api, args)
    assert body(calls[-1])["specs"] == {"aperture_mm": 80.0}
    args = _parser().parse_args(["tasks", "retry", identity, "--data", json.dumps({"item_ids": [identity]})])
    run(api, args)
    assert calls[-1].url.path.endswith("/retry") and body(calls[-1]) == {"item_ids": [identity]}


def test_cli_rejects_invalid_domain_body_before_http(client):
    api, calls = client
    args = _parser().parse_args(["presets", "create", str(uuid4()), "--data", '{"name":"night","parameters":{"invented":1}}'])
    with pytest.raises(ValueError, match="invented"):
        run(api, args)
    assert not calls


def test_init_flags_remain_and_control_commands_have_no_activation_flag():
    args = _parser().parse_args(["init", "--workspace", "work", "--reuse-runtime", "--frontend-assets", "build/frontend", "--no-activate"])
    assert args.reuse_runtime and args.no_activate and args.frontend_assets == Path("build/frontend")
    for command in ("start", "status", "stop", "restart"):
        control = _parser().parse_args([command, "--workspace", "work"])
        assert control.workspace == Path("work") and not hasattr(control, "no_activate")
    with pytest.raises(SystemExit):
        _parser().parse_args(["start", "--no-activate"])


def test_display_preview_reads_bytes_and_exports_without_scheduling(tmp_path):
    calls = []
    jpeg = b"\xff\xd8jpeg\xff\xd9"

    def handle(request):
        calls.append(request)
        if request.method == "POST":
            return httpx.Response(202, json={"status": "generating"})
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"status": "available"})
        return httpx.Response(200, content=jpeg, headers={"Content-Type": "image/jpeg"})

    api = AssetClient.__new__(AssetClient)
    api.client = httpx.Client(base_url="http://service/api/v1", transport=httpx.MockTransport(handle))
    with api:
        assert api.schedule_display_preview("asset", "version")["status"] == "generating"
        assert api.get_display_preview_status("asset", "version")["status"] == "available"
        output = tmp_path / "display.jpg"
        result = run(api, _parser().parse_args(["previews", "export", "asset", "version", str(output)]))
    assert output.read_bytes() == jpeg and result == {"path": str(output.resolve()), "byte_size": len(jpeg)}
    assert [(call.method, call.url.path.rsplit("/", 1)[-1]) for call in calls] == [("POST", "display"), ("GET", "status"), ("GET", "display")]


def test_mcp_display_image_uses_sdk_content_conversion(monkeypatch):
    import asyncio
    from base64 import b64decode
    from astrophotoflow.interfaces.mcp import server as mcp_server

    jpeg = b"\xff\xd8jpeg\xff\xd9"
    api = AssetClient.__new__(AssetClient)
    api.client = httpx.Client(base_url="http://service/api/v1", transport=httpx.MockTransport(lambda request: httpx.Response(200, content=jpeg, headers={"Content-Type": "image/jpeg"})))
    monkeypatch.setattr(mcp_server, "AssetClient", lambda: api)
    tool = mcp_server.server._tool_manager.get_tool("data_management")
    result = asyncio.run(tool.run({"operation":"previews.read", "arguments":{"asset_id": "asset", "version_id": "version"}}, None, convert_result=True))
    assert result.structured_content is None and len(result.content) == 1
    assert result.content[0].type == "image" and result.content[0].mime_type == "image/jpeg"
    assert b64decode(result.content[0].data) == jpeg


def test_preview_export_preserves_existing_destination_and_cli_fails(client, tmp_path, monkeypatch, capsys):
    from astrophotoflow.interfaces.cli import main as cli

    api, _ = client
    output = tmp_path / "original.fits"
    original = b"original scientific photo bytes"
    output.write_bytes(original)
    with pytest.raises(FileExistsError):
        api.export_display_preview("asset", "version", output)
    assert output.read_bytes() == original

    monkeypatch.setattr(cli, "AssetClient", lambda: api)
    monkeypatch.setattr("sys.argv", ["apf", "previews", "export", "asset", "version", str(output)])
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code == 1 and output.name in capsys.readouterr().err
    assert output.read_bytes() == original


def test_display_preview_rejects_successful_wrong_mime_with_request_id():
    api = AssetClient.__new__(AssetClient)
    api.client = httpx.Client(base_url="http://service/api/v1", transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"not": "a jpeg"}, headers={"X-Request-ID": "mime-request"})
    ))
    with api, pytest.raises(ServiceApiError) as caught:
        api.read_display_preview("asset", "version")
    assert caught.value.code == "INVALID_RESPONSE" and caught.value.status == 200
    assert caught.value.request_id == "mime-request" and "image/jpeg" in str(caught.value)



def test_typed_workbench_client_uses_fixed_routes_and_omits_default_when_not_requested():
    from astrophotoflow.contracts.workbench import ConfigSave, ConfigState
    values = {"host": "127.0.0.1", "service_port": 31390, "data_dir": "data",
              "allowed_origins": ["http://127.0.0.1:31388"], "import_roots": [], "file_workers": 2, "preview_workers": 1}
    state = {"config_path": "C:/isolated/config.toml", "data_dir_absolute": "C:/isolated/data", "default_workspace": None, "saved": values,
             "effective": values, "config_token": "current", "restart_required": False}
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=state)
    api = AssetClient.__new__(AssetClient)
    api.client = httpx.Client(base_url="http://service/api/v1", transport=httpx.MockTransport(handle))
    with api:
        assert isinstance(api.get_workbench_configuration(), ConfigState)
        result = api.save_workbench_configuration(ConfigSave(config_token="current", values=values))
        assert result.config_token == "current"
    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/api/v1/settings/workbench"), ("PATCH", "/api/v1/settings/workbench")]
    assert body(requests[1]) == {"config_token": "current", "values": values}


def test_workbench_directory_client_preserves_selected_path_and_cancel():
    requests = []
    def handle(request):
        requests.append(request)
        assert request.extensions["timeout"]["read"] is None
        return httpx.Response(200, json={"path": "C:/selected" if len(requests) == 1 else None})
    api = AssetClient.__new__(AssetClient)
    api.client = httpx.Client(base_url="http://service/api/v1", transport=httpx.MockTransport(handle))
    with api:
        assert api.select_workbench_directory("data").path == "C:/selected"
        assert api.select_workbench_directory("").path is None
    assert all(request.url.path == "/api/v1/settings/workbench/select-directory" for request in requests)
    assert body(requests[0]) == {"path": "data"}
