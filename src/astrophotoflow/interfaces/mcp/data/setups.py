from typing import Annotated

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from pydantic import MISSING, Field

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.common import UuidInput
from astrophotoflow.contracts.setups import EquipmentSetupCreate, EquipmentSetupOut, EquipmentSetupPage, EquipmentSetupPatch
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.data.equipment import CREATE, READ_ONLY, UPDATE
from astrophotoflow.interfaces.mcp.data.equipment_inputs import EquipmentName, SetupChanges, SetupMember, SetupSearch, member_inputs
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("setups")

    @mcp.tool(name="search", annotations=READ_ONLY, description="Find equipment setups/rigs by text, status or component_type. 查询搜索设备组合 成像组合 rig setup 相机 望远镜 滤镜。To delete a setup: data_equipment_management_preview_delete and data_equipment_management_delete with targets.setups.")
    @service_errors
    def search(query: SetupSearch | None = None, *, client: AssetClient = Depends(service_client)) -> EquipmentSetupPage:
        return client.list_equipment_setups((query or SetupSearch()).to_query())

    @mcp.tool(name="create", annotations=CREATE, description="Create a rig from ordered registered or inline members. Prefer registered devices; inline devices remain local. At most one camera, one telescope and one mount, with multiple filters. Optical accessories belong only to telescopes. A setup is an optional shortcut for selecting equipment, not a source of capture parameters. 创建设备组合 成像组合 赤道仪 rig setup 装配。")
    @service_errors
    def create(name: EquipmentName, members: list[SetupMember] | MISSING = MISSING, notes: str | None = None,
               *, client: AssetClient = Depends(service_client)) -> EquipmentSetupOut:
        return client.create_equipment_setup(EquipmentSetupCreate.model_validate({"name": name, "notes": notes,
                                                                                 "components": member_inputs([] if members is MISSING else members)}))

    @mcp.tool(name="get", annotations=READ_ONLY, description="Read an equipment setup's current revision and ordered components. component.id is the member_id used in replacement members and image filter choices, not equipment_id. 读取设备组合 成员ID 登记引用 内嵌设备。")
    @service_errors
    def get(setup_id: UuidInput, *, client: AssetClient = Depends(service_client)) -> EquipmentSetupOut:
        return client.get_equipment_setup(str(setup_id))

    @mcp.tool(name="update", annotations=UPDATE, description="Edit/archive a setup with expected_revision and sparse changes; registered devices are not edited. members, if supplied, replaces the entire ordered list: retain existing member_id to preserve member identities. Omit members to keep them; [] clears them. 修改设备组合 增删成员 选择光学附件 倍率 归档。Delete via data_equipment_management_preview_delete/delete with targets.setups.")
    @service_errors
    def update(setup_id: UuidInput, expected_revision: Annotated[int, Field(ge=1)], changes: SetupChanges,
               *, client: AssetClient = Depends(service_client)) -> EquipmentSetupOut:
        return client.update_equipment_setup(str(setup_id), EquipmentSetupPatch.model_validate(
            {"base_revision": expected_revision, **changes.to_changes()}))

    return mcp
