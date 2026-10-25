from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from astrophotoflow.backend.import_schemas import AssetPatch, DatasetMembersCreate, ImportCreate
from astrophotoflow.client import AssetClient, ServiceApiError
from astrophotoflow.client_domains.imports import PhotoImportOptions
from astrophotoflow.cli import _parser
from astrophotoflow.cli_commands import run


@pytest.fixture
def client():
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path == "/api/v1/uploads":
            return httpx.Response(202, json={"task_id": "upload-task", "status": "queued"})
        return httpx.Response(200, json={"ok": True})

    client = AssetClient.__new__(AssetClient)
    client.client = httpx.Client(base_url="http://service/api/v1", transport=httpx.MockTransport(handle))
    with client:
        yield client, calls


def body(request):
    return json.loads(request.content)


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


def test_existing_workbench_flags_remain_available():
    args = _parser().parse_args(["init", "--workspace", "work", "--reuse-runtime", "--frontend-assets", "build/frontend", "--no-activate"])
    assert args.reuse_runtime and args.no_activate and args.frontend_assets == Path("build/frontend")
    assert _parser().parse_args(["start", "--no-activate"]).no_activate


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
    from astrophotoflow import mcp_server

    jpeg = b"\xff\xd8jpeg\xff\xd9"
    api = AssetClient.__new__(AssetClient)
    api.client = httpx.Client(base_url="http://service/api/v1", transport=httpx.MockTransport(lambda request: httpx.Response(200, content=jpeg)))
    monkeypatch.setattr(mcp_server, "AssetClient", lambda: api)
    tool = mcp_server.server._tool_manager.get_tool("read_display_preview")
    result = asyncio.run(tool.run({"asset_id": "asset", "version_id": "version"}, None, convert_result=True))
    assert result.structured_content is None and len(result.content) == 1
    assert result.content[0].type == "image" and result.content[0].mime_type == "image/jpeg"
    assert b64decode(result.content[0].data) == jpeg
