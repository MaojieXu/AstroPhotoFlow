"""Chat-oriented, type-specific registration over the shared equipment service."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from pydantic import MISSING, Field

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.common import UuidInput
from astrophotoflow.contracts.equipment import (
    FILTER_CHANNEL_PROMPT,
    CameraCreate,
    CameraOut,
    CameraPatch,
    CameraSpecs,
    EquipmentOut,
    EquipmentPage,
    FilterCreate,
    FilterOut,
    FilterPatch,
    FilterSpecs,
    MountCreate,
    MountOut,
    MountPatch,
    TelescopeCreate,
    TelescopeOut,
    TelescopePatch,
    TelescopeSpecs,
)
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.data.equipment_inputs import (
    CameraChanges,
    EquipmentName,
    EquipmentSearch,
    FilterChanges,
    MountChanges,
    TelescopeChanges,
)
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}
CREATE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}
UPDATE = {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False}


def build_server() -> FastMCP:
    mcp = tool_namespace("equipment")

    @mcp.tool(name="search", annotations=READ_ONLY, description="Find registered cameras, telescopes, filters and mounts by name/model and equipment_type. Same names may identify different physical devices; never merge automatically. 查询搜索我的设备库 相机 望远镜 滤镜 赤道仪 型号 重名。Deletion: data_equipment_management_preview_delete then data_equipment_management_delete.")
    @service_errors
    def search(query: EquipmentSearch | None = None, *, client: AssetClient = Depends(service_client)) -> EquipmentPage:
        return client.list_equipment((query or EquipmentSearch()).to_query())

    @mcp.tool(name="get", annotations=READ_ONLY, description="Read one registered device by exact equipment_id, including type, available facts and current revision. Mounts have no specs/control fields. 读取查询设备资料 相机 望远镜 滤镜 赤道仪 修订号。")
    @service_errors
    def get(equipment_id: UuidInput, *, client: AssetClient = Depends(service_client)) -> EquipmentOut:
        return client.get_equipment(str(equipment_id))

    @mcp.tool(name="register_camera", annotations=CREATE, description='Register one camera the user asked to add to their equipment library. Only name is required; omit unknown specs, do not infer sensor facts from a model suffix. Example: {"name":"My camera"}. 添加登记我的相机 设备库 型号。Create is not idempotent: after an unknown result search/reconcile, never replay blindly.')
    @service_errors
    def register_camera(name: EquipmentName, model: str | None = None, notes: str | None = None,
                        specs: CameraSpecs | MISSING = MISSING, *, client: AssetClient = Depends(service_client)) -> CameraOut:
        return client.create_equipment(CameraCreate(kind="camera", name=name, model=model, notes=notes,
                                                    specs=CameraSpecs() if specs is MISSING else specs))

    @mcp.tool(name="register_telescope", annotations=CREATE, description='Register one telescope the user asked to add. Only name is required; omit unknown focal length. Optical accessories belong inside this telescope, not separate devices. Example: {"name":"My telescope"}. 添加登记我的望远镜 焦距 光学附件 设备库。Unknown acceptance: search/reconcile without replay.')
    @service_errors
    def register_telescope(name: EquipmentName, model: str | None = None, notes: str | None = None,
                           specs: TelescopeSpecs | MISSING = MISSING, *, client: AssetClient = Depends(service_client)) -> TelescopeOut:
        return client.create_equipment(TelescopeCreate(kind="telescope", name=name, model=model, notes=notes,
                                                       specs=TelescopeSpecs() if specs is MISSING else specs))

    @mcp.tool(name="register_filter", annotations=CREATE, description='Register one physical filter; only name is required. Keep the actual name. ' + FILTER_CHANNEL_PROMPT + ' Few-shot: {"name":"Baader Ha 6.5nm","specs":{"channel":"H","bandwidth_nm":6.5}}. 添加登记我的滤镜 通道 Channel 带宽 设备库。Unknown acceptance: search/reconcile without replay.')
    @service_errors
    def register_filter(name: EquipmentName, model: str | None = None, notes: str | None = None,
                        specs: FilterSpecs | MISSING = MISSING, *, client: AssetClient = Depends(service_client)) -> FilterOut:
        return client.create_equipment(FilterCreate(kind="filter", name=name, model=model, notes=notes,
                                                    specs=FilterSpecs() if specs is MISSING else specs))

    @mcp.tool(name="update_camera", annotations=UPDATE, description="Edit or archive a registered camera using its current expected_revision. changes is sparse: omission keeps, nullable leaves clear with null, zero is valid. Never change its kind or historical snapshots; re-read/reconcile a revision conflict. 修改更新相机 名称 型号 像元 像素排列 归档。")
    @service_errors
    def update_camera(equipment_id: UuidInput, expected_revision: Annotated[int, Field(ge=1)], changes: CameraChanges,
                      *, client: AssetClient = Depends(service_client)) -> CameraOut:
        body = CameraPatch.model_validate({"kind": "camera", "base_revision": expected_revision,
                                          **changes.model_dump(mode="json", exclude_unset=True)})
        return client.update_equipment(str(equipment_id), body)

    @mcp.tool(name="update_telescope", annotations=UPDATE, description="Edit or archive a registered telescope using expected_revision and sparse changes. Omit unchanged specs; optical_accessories is a complete replacement retaining existing accessory IDs. Nullable leaf null clears, zero is not unknown. Historical snapshots stay fixed. 修改更新望远镜 焦距 光学附件 倍率 归档。")
    @service_errors
    def update_telescope(equipment_id: UuidInput, expected_revision: Annotated[int, Field(ge=1)], changes: TelescopeChanges,
                         *, client: AssetClient = Depends(service_client)) -> TelescopeOut:
        body = TelescopePatch.model_validate({"kind": "telescope", "base_revision": expected_revision,
                                             **changes.model_dump(mode="json", exclude_unset=True)})
        return client.update_equipment(str(equipment_id), body)

    @mcp.tool(name="update_filter", annotations=UPDATE, description='Edit/archive a filter at expected_revision. Sparse changes preserve omitted fields and historical snapshots. ' + FILTER_CHANNEL_PROMPT + ' Few-shot: {"equipment_id":"<queried UUID>","expected_revision":2,"changes":{"specs":{"channel":"Ir875nm"}}}. 修改更新滤镜 Channel 通道 带宽 名称 归档。')
    @service_errors
    def update_filter(equipment_id: UuidInput, expected_revision: Annotated[int, Field(ge=1)], changes: FilterChanges,
                      *, client: AssetClient = Depends(service_client)) -> FilterOut:
        body = FilterPatch.model_validate({"kind": "filter", "base_revision": expected_revision,
                                          **changes.model_dump(mode="json", exclude_unset=True)})
        return client.update_equipment(str(equipment_id), body)

    @mcp.tool(name="register_mount", annotations=CREATE, description='Register one equatorial mount; only name is required. Model and notes are optional. This manages equipment records, not hardware control. Example: {"name":"My mount","model":"AP1100 GTO"}. 添加登记赤道仪 设备库。After unknown acceptance, search/reconcile; never replay blindly.')
    @service_errors
    def register_mount(name: EquipmentName, model: str | None = None, notes: str | None = None,
                       *, client: AssetClient = Depends(service_client)) -> MountOut:
        return client.create_equipment(MountCreate(kind="mount", name=name, model=model, notes=notes))

    @mcp.tool(name="update_mount", annotations=UPDATE, description="Edit/archive a mount at its current expected_revision. Omission keeps, nullable model/notes clear with null. No specs, driver, network or capture fields. Historical snapshots remain fixed. 修改更新赤道仪 名称 型号 备注 归档。")
    @service_errors
    def update_mount(equipment_id: UuidInput, expected_revision: Annotated[int, Field(ge=1)], changes: MountChanges,
                     *, client: AssetClient = Depends(service_client)) -> MountOut:
        body = MountPatch.model_validate({"kind": "mount", "base_revision": expected_revision,
                                         **changes.model_dump(mode="json", exclude_unset=True)})
        return client.update_equipment(str(equipment_id), body)

    return mcp
