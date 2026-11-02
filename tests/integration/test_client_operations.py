from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest

from astrophotoflow.contracts.assets import AssetPatch
from astrophotoflow.contracts.datasets import DatasetMembersCreate
from astrophotoflow.contracts.imports import ImportCreate
from astrophotoflow.client import AssetClient, ServiceApiError
from astrophotoflow.contracts.imports import PhotoImportOptions
from astrophotoflow.contracts.trash import EquipmentDelete, EquipmentDeleteSelection
from astrophotoflow.contracts.canvas import CanvasAddRequest, CanvasGraphRequest


@pytest.fixture
def client():
    calls = []

    def handle(request):
        calls.append(request)
        path=request.url.path
        identity="00000000-0000-4000-8000-000000000001"
        timestamp="2026-10-31T00:00:00Z"
        payload=json.loads(request.content) if request.content and request.method!="PUT" else {}
        if path in {"/api/v1/uploads","/api/v1/imports"} or path.endswith(("/start","/retry")):
            return httpx.Response(202,json={"task_id":identity,"status":"queued"})
        if path.startswith("/api/v1/uploads/") and request.method=="PUT":
            return httpx.Response(200,json={"received":len(request.content)})
        if path.endswith("/previews/display"):
            return httpx.Response(200,content=b"jpeg",headers={"Content-Type":"image/jpeg"})
        if path=="/api/v1/canvas/pages":return httpx.Response(200,json=[])
        if path.startswith("/api/v1/canvas/"):
            target={key:payload.get(key,identity) for key in ("operation_id","page_id","workflow_id","graph_id")}
            return httpx.Response(200,json={**target,"applied":True,"node_id":None,"error":None})
        if path.endswith("/equipment-management/delete-preview"):
            return httpx.Response(200,json={"items":[],"dependencies":[],"blocked":False,"preview_fingerprint":"current"})
        if path.endswith("/equipment-management/delete"):
            return httpx.Response(200,json={"deleted_count":1,"detached_material_count":0})
        if path.startswith("/api/v1/library/assets/"):
            return httpx.Response(200,json={"id":path.rsplit("/",1)[1],"name":"Sample","scope":"shared","owner_project_id":None,
                "role":"raw","calibration_level":None,"current_version_id":None,"current_version":None,"classification":{},
                "parameters":{},"equipment_snapshot":{},"value_sources":{},"notes":None,"status":"active","revision":8,"created_at":timestamp})
        if path.startswith("/api/v1/datasets/") and path.endswith("/versions"):
            return httpx.Response(200,json={"id":identity,"dataset_id":path.split("/")[-2],"version_number":2,
                "created_at":timestamp,"calibration_defaults":{},"members":[]})
        if path.endswith("/entries") or path=="/api/v1/asset-tasks":
            return httpx.Response(200,json={"items":[],"total":0,"limit":10,"offset":0})
        if path=="/api/v1/equipment" or path.startswith("/api/v1/equipment/"):
            return httpx.Response(200,json={"id":identity,"name":"Scope","kind":payload["kind"],"specs":payload.get("specs",{}),
                "model":None,"notes":None,"status":"active","revision":3,"created_at":timestamp,"updated_at":timestamp})
        raise AssertionError("Unexpected request: "+str(request.url))

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
    assert api.import_local(ImportCreate.model_validate(request)).status == "queued"
    assert calls[0].url.path == "/api/v1/imports"
    assert body(calls[0]) == request


def test_canvas_cli_and_client_preserve_explicit_target_and_operation_id(client):
    api, calls = client
    request = {"operation_id": str(uuid4()), "page_id": str(uuid4()), "workflow_id": str(uuid4()), "graph_id": str(uuid4()), "content_token": "current", "source": {"entry_type": "asset", "id": str(uuid4()), "version_id": str(uuid4())}}
    assert api.add_canvas_data(CanvasAddRequest.model_validate(request)).operation_id == UUID(request["operation_id"])
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
    assert api.edit_canvas(CanvasGraphRequest.model_validate(request)).operation_id == UUID(request["operation_id"])
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
        "/api/v1/uploads", "/api/v1/uploads/00000000-0000-4000-8000-000000000001/0", "/api/v1/uploads/00000000-0000-4000-8000-000000000001/1", "/api/v1/uploads/00000000-0000-4000-8000-000000000001/start",
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
        "assessment": {"fixture": True},
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


def test_client_sparse_patch_archive_create_and_retry_use_shared_schemas(client):
    from pydantic import TypeAdapter
    from astrophotoflow.contracts.equipment import EquipmentCreate,EquipmentPatch
    from astrophotoflow.contracts.imports import RetryCreate
    api,calls=client
    identity=str(uuid4())
    api.update_asset(identity,AssetPatch(base_revision=7,notes=None,parameters={'gain':0}))
    assert body(calls[-1])=={'base_revision':7,'notes':None,'parameters':{'gain':0}}
    api.update_equipment(identity,TypeAdapter(EquipmentPatch).validate_python({'kind':'telescope','base_revision':2,'status':'archived'}))
    assert body(calls[-1])=={'kind':'telescope','base_revision':2,'status':'archived'}
    api.create_equipment(TypeAdapter(EquipmentCreate).validate_python({'kind':'telescope','name':'Scope','specs':{'native_focal_length_mm':480}}))
    assert body(calls[-1])['specs']=={'native_focal_length_mm':480.0}
    api.retry_import_items(identity,RetryCreate(item_ids=[identity]))
    assert calls[-1].url.path.endswith('/retry') and body(calls[-1])=={'item_ids':[identity]}


def test_client_rejects_invalid_domain_body_before_http(client):
    from astrophotoflow.contracts.setups import CapturePresetCreate
    api,calls=client
    with pytest.raises(ValueError,match='invented'):
        api.create_capture_preset(str(uuid4()),CapturePresetCreate.model_validate({'name':'night','parameters':{'invented':1}}))
    assert not calls


def test_cyclopts_local_init_and_control_options_do_not_execute_actions():
    from astrophotoflow.interfaces.cli.main import app
    _,args,_=app.parse_args(['init','--workspace','work','--reuse-runtime','--frontend-assets','build/frontend','--no-activate'])
    assert args.arguments['reuse_runtime'] is True and args.arguments['activate'] is False
    assert args.arguments['frontend_assets']==Path('build/frontend')
    for command in ('start','status','stop','restart'):
        _,args,_=app.parse_args([command,'--workspace','work'])
        assert args.arguments['workspace']==Path('work') and 'activate' not in args.arguments


def test_display_preview_reads_bytes_and_exports_without_scheduling(tmp_path):
    calls = []
    jpeg = b"\xff\xd8jpeg\xff\xd9"

    def handle(request):
        calls.append(request)
        if request.method == "POST":
            return httpx.Response(202, json={"asset_version_id":"00000000-0000-4000-8000-000000000001","size":"display","status":"generating"})
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"asset_version_id":"00000000-0000-4000-8000-000000000001","size":"display","status":"available"})
        return httpx.Response(200, content=jpeg, headers={"Content-Type": "image/jpeg"})

    api = AssetClient.__new__(AssetClient)
    api.client = httpx.Client(base_url="http://service/api/v1", transport=httpx.MockTransport(handle))
    with api:
        assert api.schedule_display_preview("asset", "version").status == "generating"
        assert api.get_display_preview_status("asset", "version").status == "available"
        output = tmp_path / "display.jpg"
        result = api.export_display_preview("asset", "version", output)
    assert output.read_bytes() == jpeg and result == {"path": str(output.resolve()), "byte_size": len(jpeg)}
    assert [(call.method, call.url.path.rsplit("/", 1)[-1]) for call in calls] == [("POST", "display"), ("GET", "status"), ("GET", "display")]


def test_mcp_display_image_uses_framework_content_conversion(monkeypatch):
    import asyncio
    from base64 import b64decode
    from fastmcp import Client
    from astrophotoflow.interfaces.mcp import lifespan
    from astrophotoflow.interfaces.mcp.server import build_tool_catalog
    jpeg=b'\xff\xd8jpeg\xff\xd9'
    api=AssetClient.__new__(AssetClient)
    api.client=httpx.Client(base_url='http://service/api/v1',transport=httpx.MockTransport(lambda _:httpx.Response(200,content=jpeg,headers={'Content-Type':'image/jpeg'})))
    monkeypatch.setattr(lifespan,'AssetClient',lambda:api)
    async def check():
        async with Client(build_tool_catalog()) as client:
            result=await client.call_tool('data_media_read',{'asset_id':'asset','version_id':'version'})
            assert result.structured_content is None and len(result.content)==1
            assert result.content[0].type=='image' and result.content[0].mime_type=='image/jpeg'
            assert b64decode(result.content[0].data)==jpeg
    asyncio.run(check())


def test_preview_export_preserves_existing_destination_and_cli_fails(client, tmp_path, monkeypatch, capsys):
    from astrophotoflow.interfaces.cli import main as cli

    api, _ = client
    output = tmp_path / "original.fits"
    original = b"original scientific photo bytes"
    output.write_bytes(original)
    with pytest.raises(FileExistsError):
        api.export_display_preview("asset", "version", output)
    assert output.read_bytes() == original

    from astrophotoflow.interfaces.cli import generated
    from astrophotoflow.interfaces.mcp import lifespan
    from astrophotoflow.interfaces.mcp.server import build_tool_catalog
    monkeypatch.setattr(lifespan,'AssetClient',lambda:api)
    monkeypatch.setattr(generated,'CLIENT_SPEC',build_tool_catalog())
    monkeypatch.setattr('sys.argv',['apf','call-tool','data_media_export','--asset-id','asset','--version-id','version','--output',str(output)])
    with pytest.raises(SystemExit) as caught:
        cli.main()
    captured=capsys.readouterr()
    assert caught.value.code == 1 and output.name in captured.out+captured.err
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
