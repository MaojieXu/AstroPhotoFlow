"""The new conversational device API preserves typed shared-service contracts."""

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastmcp import Client
from pydantic import TypeAdapter

from astrophotoflow.contracts.equipment import EquipmentOut, EquipmentPage
from astrophotoflow.contracts.setups import EquipmentSetupOut, EquipmentSetupPage
from astrophotoflow.contracts.trash import ManagementTrashDeleteOut, ManagementTrashPreviewOut
from astrophotoflow.interfaces.mcp import lifespan
from astrophotoflow.interfaces.mcp.server import build_tool_catalog, create_server

DEVICE = "00000000-0000-4000-8000-000000000001"
SETUP = "00000000-0000-4000-8000-000000000002"
MEMBER = "00000000-0000-4000-8000-000000000003"
NOW = datetime(2026, 11, 2, tzinfo=UTC)


class DeviceService:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def record(self, operation, body):
        self.calls.append((operation, body.model_dump(mode="json", exclude_unset=True)))

    def device(self, kind="camera", **values):
        payload = {
            "id": UUID(DEVICE), "name": "Synthetic device", "kind": kind, "model": None, "notes": None,
            "specs": {}, "status": "active", "revision": 1, "created_at": NOW, "updated_at": NOW, **values,
        }
        if kind == "mount":
            payload.pop("specs", None)
        return TypeAdapter(EquipmentOut).validate_python(payload)

    def setup(self, components=None):
        return EquipmentSetupOut(id=UUID(SETUP), name="Synthetic setup", notes=None, components=components or [],
                                 status="active", revision=1, created_at=NOW, updated_at=NOW)

    def create_equipment(self, body):
        self.record("register", body)
        return self.device(**body.model_dump())

    def update_equipment(self, equipment_id, body):
        assert equipment_id == DEVICE
        self.record("update", body)
        return self.device(body.kind)

    def list_equipment(self, query):
        self.record("search", query)
        return EquipmentPage(items=[], total=0, limit=query.limit, offset=query.offset)

    def get_equipment(self, identity):
        assert identity == DEVICE
        return self.device()

    def create_equipment_setup(self, body):
        self.record("setup_create", body)
        components = []
        for member in body.components:
            payload = member.model_dump()
            payload["id"] = UUID(MEMBER) if payload["id"] is None else payload["id"]
            components.append(payload)
        return self.setup(components)

    def update_equipment_setup(self, identity, body):
        assert identity == SETUP
        self.record("setup_update", body)
        return self.setup()

    def list_equipment_setups(self, query):
        self.record("setup_search", query)
        return EquipmentSetupPage(items=[], total=0, limit=query.limit, offset=query.offset)

    def get_equipment_setup(self, identity):
        assert identity == SETUP
        return self.setup()

    def preview_equipment_delete(self, body):
        self.record("preview_delete", body)
        return ManagementTrashPreviewOut(items=[], dependencies=[], blocked=False, preview_fingerprint="synthetic-fingerprint")

    def delete_equipment_entries(self, body):
        self.record("delete", body)
        return ManagementTrashDeleteOut(deleted_count=len(body.items), detached_material_count=0)


@pytest.fixture
def service(monkeypatch):
    service = DeviceService()
    monkeypatch.setattr(lifespan, "AssetClient", lambda: service)
    return service


@pytest.mark.asyncio
async def test_v2_catalog_replaces_old_inputs_and_has_typed_optional_non_null_fields(service):
    async with Client(build_tool_catalog()) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
    relevant = {name for name in tools if name.startswith(("data_equipment_", "data_setups_", "data_presets_"))}
    assert len(relevant) == 16
    assert {f"data_equipment_{verb}_{kind}" for kind in ("camera", "telescope", "filter", "mount")
            for verb in ("register", "update")} <= relevant
    assert not {"data_equipment_create_item", "data_equipment_list_items", "data_equipment_get_item",
                "data_equipment_update_item", "data_equipment_preview_delete", "data_equipment_delete",
                "data_setups_list", "data_presets_list"} & relevant
    for name in relevant:
        assert "client" not in tools[name].input_schema["properties"]
    for kind in ("camera", "telescope", "filter"):
        schema = tools[f"data_equipment_register_{kind}"].input_schema
        assert schema["required"] == ["name"]
        assert "body" not in schema["properties"] and "kind" not in schema["properties"]
        assert schema["properties"]["specs"]["type"] == "object"
        changes = tools[f"data_equipment_update_{kind}"].input_schema["properties"]["changes"]["properties"]
        assert changes["name"]["type"] == changes["status"]["type"] == "string"
        assert changes["specs"]["type"] == "object"
    assert tools["data_equipment_get"].annotations.read_only_hint
    assert tools["data_equipment_management_preview_delete"].annotations.read_only_hint
    assert tools["data_equipment_management_delete"].annotations.destructive_hint
    assert not tools["data_equipment_register_camera"].annotations.idempotent_hint


@pytest.mark.asyncio
async def test_mount_contract_and_channel_guidance_are_visible_in_nested_tool_schemas(service):
    async with Client(build_tool_catalog()) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
        mount = tools["data_equipment_register_mount"].input_schema
        assert mount["required"] == ["name"]
        assert "specs" not in mount["properties"]
        changes = tools["data_equipment_update_mount"].input_schema["properties"]["changes"]
        assert "specs" not in changes["properties"]
        for name in ("data_equipment_register_filter", "data_equipment_update_filter", "data_setups_create"):
            schema_text = json.dumps(tools[name].input_schema)
            assert "Ir875nm" in schema_text and "multi-band SHO" in schema_text
            assert "long-pass cutoff" in schema_text
        for name in ("data_equipment_register_filter", "data_equipment_update_filter"):
            assert "Few-shot" in tools[name].description
            assert "never inferred" not in tools[name].description
        created = await client.call_tool("data_equipment_register_mount", {"name": "My AP1100"})
        assert created.structured_content["kind"] == "mount"
        assert "specs" not in created.structured_content
        await client.call_tool("data_equipment_update_mount", {
            "equipment_id": DEVICE, "expected_revision": 2, "changes": {"notes": None},
        })
    assert service.calls[-1] == ("update", {"kind": "mount", "base_revision": 2, "notes": None})


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["camera", "telescope", "filter"])
async def test_minimal_register_needs_only_name_and_uses_exact_device_type(service, kind):
    async with Client(build_tool_catalog()) as client:
        result = await client.call_tool(f"data_equipment_register_{kind}", {"name": f"Synthetic {kind}"})
        assert result.structured_content["kind"] == kind
        assert result.structured_content["name"] == f"Synthetic {kind}"
        assert result.structured_content["id"] == DEVICE
    assert service.calls[0][1]["kind"] == kind
    assert all(value is None or value == [] for value in result.structured_content["specs"].values())


@pytest.mark.asyncio
async def test_sparse_changes_keep_omission_null_zero_and_revision_mapping(service):
    async with Client(build_tool_catalog()) as client:
        await client.call_tool("data_equipment_update_camera", {"equipment_id": DEVICE, "expected_revision": 3,
                               "changes": {"notes": None, "specs": {"cfa_pattern": "MONO", "pixel_size_um": None}}})
    assert service.calls[0] == ("update", {"kind": "camera", "base_revision": 3, "notes": None,
                                         "specs": {"cfa_pattern": "MONO", "pixel_size_um": None}})



@pytest.mark.asyncio
@pytest.mark.parametrize("name,arguments", [
    ("data_equipment_register_camera", {"name": "Camera", "specs": None}),
    ("data_equipment_register_camera", {"name": "   "}),
    ("data_equipment_register_camera", {"name": "Camera", "kind": "filter"}),
    ("data_equipment_register_camera", {"name": "Camera", "specs": {"bandwidth_nm": 7}}),
    ("data_equipment_update_camera", {"equipment_id": DEVICE, "expected_revision": 1, "changes": {"name": None}}),
    ("data_equipment_update_camera", {"equipment_id": DEVICE, "expected_revision": 1, "changes": {"status": None}}),
    ("data_equipment_update_camera", {"equipment_id": DEVICE, "expected_revision": 1, "changes": {"specs": None}}),
    ("data_equipment_update_camera", {"equipment_id": DEVICE, "expected_revision": 0, "changes": {}}),
    ("data_equipment_get", {"equipment_id": "not-a-uuid"}),
    ("data_setups_update", {"setup_id": SETUP, "expected_revision": 1, "changes": {"members": None}}),
    ("data_equipment_management_preview_delete", {"targets": {}}),
])
async def test_invalid_inputs_do_not_call_the_service(service, name, arguments):
    async with Client(build_tool_catalog()) as client:
        result = await client.call_tool(name, arguments, raise_on_error=False)
        assert result.is_error
    assert service.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("tool,arguments,path,reason", [
    ("data_equipment_register_telescope", {"name": "Bad Scope", "specs": {"native_focal_length_mm": -600}},
     "specs.native_focal_length_mm", "greater than 0"),
    ("data_equipment_register_camera", {"name": "   "}, "name", "名称不能为空"),
])
async def test_argument_validation_reports_invalid_request_with_field_path(service, tool, arguments, path, reason):
    async with Client(build_tool_catalog()) as client:
        result = await client.call_tool(tool, arguments, raise_on_error=False)
    assert result.is_error
    payload = json.loads(result.content[0].text)
    assert payload["error"]["code"] == "INVALID_REQUEST"
    assert any(field["path"] == path and reason in field["message"] for field in payload["error"]["fields"])
    assert service.calls == []


@pytest.mark.asyncio
async def test_unexpected_service_failure_remains_internal_error(service, monkeypatch):
    def fail(_body):
        raise RuntimeError("Synthetic private implementation detail")

    monkeypatch.setattr(service, "create_equipment", fail)
    async with Client(build_tool_catalog()) as client:
        result = await client.call_tool("data_equipment_register_camera", {"name": "Camera"}, raise_on_error=False)
    assert result.is_error
    payload = json.loads(result.content[0].text)
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert payload["error"]["fields"] == []
    assert "Synthetic private implementation detail" not in result.content[0].text


@pytest.mark.asyncio
async def test_setup_registered_and_inline_members_keep_ids_and_order(service):
    members = [{"source": "registered", "member_id": MEMBER, "equipment_id": DEVICE},
               {"source": "inline", "equipment": {"kind": "filter", "name": "Inline Ha"}}]
    async with Client(build_tool_catalog()) as client:
        created = await client.call_tool("data_setups_create", {"name": "Rig", "members": members})
        assert created.structured_content["components"][0]["id"] == MEMBER
        assert created.structured_content["components"][1]["equipment"]["name"] == "Inline Ha"
        await client.call_tool("data_setups_update", {"setup_id": SETUP, "expected_revision": 2,
                                                     "changes": {"members": members}})
        await client.call_tool("data_setups_update", {"setup_id": SETUP, "expected_revision": 3,
                                                     "changes": {"notes": None}})
    assert service.calls[0][1]["components"][0] == {"source": "registered", "id": MEMBER, "equipment_id": DEVICE}
    assert service.calls[1][1]["components"] == service.calls[0][1]["components"]
    assert service.calls[2][1] == {"base_revision": 3, "notes": None}


@pytest.mark.asyncio
async def test_search_and_grouped_delete_map_to_existing_typed_services(service):
    targets = {"equipment": [{"id": DEVICE, "revision": 1}], "setups": [{"id": SETUP, "revision": 2}]}
    async with Client(build_tool_catalog()) as client:
        await client.call_tool("data_equipment_search", {"query": {"text": "Camera", "equipment_type": "camera", "limit": 2}})
        await client.call_tool("data_setups_search", {"query": {"text": "Rig", "component_type": "filter"}})
        preview = await client.call_tool("data_equipment_management_preview_delete", {"targets": targets})
        await client.call_tool("data_equipment_management_delete", {"targets": targets,
                               "preview_fingerprint": preview.structured_content["preview_fingerprint"]})
    assert service.calls[0][1]["kind"] == "camera" and service.calls[0][1]["q"] == "Camera"
    assert service.calls[1][1]["component_kind"] == "filter" and service.calls[1][1]["q"] == "Rig"
    assert [item["entry_type"] for item in service.calls[2][1]["items"]] == ["equipment", "equipment_setup"]
    assert service.calls[3][1]["items"] == service.calls[2][1]["items"]
    assert service.calls[3][1]["preview_fingerprint"] == "synthetic-fingerprint"


@pytest.mark.asyncio
@pytest.mark.parametrize("query,expected", [
    ("添加登记我的相机", "data_equipment_register_camera"),
    ("添加登记我的望远镜", "data_equipment_register_telescope"),
    ("添加登记我的滤镜", "data_equipment_register_filter"),
    ("删除设备", "data_equipment_management_preview_delete"),
    ("删除设备组合", "data_equipment_management_delete"),
])
async def test_real_agent_search_discovers_conversational_tasks(service, query, expected):
    async with Client(create_server()) as client:
        assert {tool.name for tool in await client.list_tools()} == {"search_tools", "call_tool"}
        found = await client.call_tool("search_tools", {"query": query})
        definitions = json.loads(found.content[0].text)
        assert 0 < len(definitions) <= 10
        assert expected in {tool["name"] for tool in definitions}


@pytest.mark.asyncio
async def test_removed_presets_are_not_a_hidden_management_path(service):
    async with Client(build_tool_catalog()) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
        assert not any(name.startswith("data_presets_") for name in tools)
        targets = tools["data_equipment_management_preview_delete"].input_schema["properties"]["targets"]["properties"]
        assert set(targets) == {"equipment", "setups"}
        assert "preset_parameter_fields" not in tools["data_assets_apply_equipment"].input_schema["properties"]
        invalid = await client.call_tool("data_equipment_management_preview_delete", {
            "targets": {"presets": [{"id": DEVICE, "revision": 1}]},
        }, raise_on_error=False)
        assert invalid.is_error
    assert service.calls == []
