from pydantic import TypeAdapter

from astrophotoflow.contracts.assets import (
    AssetContentAccept,
    AssetContentObservation,
    AssetOut,
    AssetPage,
    AssetPatch,
    AssetQuery,
    AssetVersionOut,
    AssetVersionPage,
    LibraryFilterOptions,
    LibraryItemPage,
    LibraryQuery,
)
from astrophotoflow.contracts.calibration import CalibrationTargetPage
from astrophotoflow.contracts.datasets import (
    DatasetCreate,
    DatasetMemberPage,
    DatasetMemberParametersUpdate,
    DatasetMemberParametersUpdateOut,
    DatasetMemberQuery,
    DatasetMembersCreate,
    DatasetOut,
    DatasetPage,
    DatasetPatch,
    DatasetQuery,
    DatasetVersionOut,
    DatasetVersionPage,
)
from astrophotoflow.contracts.inputs import CanvasDataOut, CanvasDataRequest
from astrophotoflow.contracts.metadata import AssetParametersPatch
from astrophotoflow.contracts.previews import DisplayPreviewState
from astrophotoflow.contracts.trash import (
    LibraryEntriesRemove,
    LibraryEntriesRemoveOut,
    LibraryTrashDelete,
    LibraryTrashDeleteOut,
    LibraryTrashPage,
    LibraryTrashPreviewOut,
    LibraryTrashRestoreOut,
    LibraryTrashSelection,
)


class LibraryOperations:
    def get_library_filter_options(self) -> LibraryFilterOptions:
        return self.request("GET", "/library/filter-options", adapter=TypeAdapter(LibraryFilterOptions))

    def prepare_canvas_data(self, body: CanvasDataRequest) -> CanvasDataOut:
        return self.request("POST", "/library/canvas-data", json=body, adapter=TypeAdapter(CanvasDataOut))

    def list_assets(self, query: AssetQuery | None = None) -> AssetPage:
        params = query if query is not None else AssetQuery()
        return self.request('GET', '/library/assets', params=params.model_dump(mode="json"), adapter=TypeAdapter(AssetPage))

    def list_library_items(self, query: LibraryQuery | None = None) -> LibraryItemPage:
        params = query if query is not None else LibraryQuery()
        return self.request('GET', '/library/items', params=params.model_dump(mode="json"), adapter=TypeAdapter(LibraryItemPage))

    def get_asset(self, asset_id: str) -> AssetOut:
        return self.request("GET", f"/library/assets/{asset_id}", adapter=TypeAdapter(AssetOut))

    def observe_asset_content(self, asset_id: str) -> AssetContentObservation:
        return self.request("POST", f"/library/assets/{asset_id}/content-observation", adapter=TypeAdapter(AssetContentObservation))

    def accept_asset_content(self, asset_id: str, body: AssetContentAccept) -> AssetOut:
        return self.request("POST", f"/library/assets/{asset_id}/content-accept", json=body, adapter=TypeAdapter(AssetOut))

    def update_asset(self, asset_id: str, body: AssetPatch) -> AssetOut:
        return self.request("PATCH", f"/library/assets/{asset_id}", json=body, adapter=TypeAdapter(AssetOut))

    def update_asset_parameters(self, asset_id: str, base_revision: int, parameters: AssetParametersPatch) -> AssetOut:
        return self.update_asset(asset_id, AssetPatch(base_revision=base_revision, parameters=parameters))

    def list_asset_versions(self, asset_id: str, limit: int = 50, offset: int = 0) -> AssetVersionPage:
        return self.request("GET", f"/library/assets/{asset_id}/versions", params={"limit": limit, "offset": offset}, adapter=TypeAdapter(AssetVersionPage))

    def get_asset_version(self, asset_id: str, version_id: str) -> AssetVersionOut:
        return self.request("GET", f"/library/assets/{asset_id}/versions/{version_id}", adapter=TypeAdapter(AssetVersionOut))

    def create_dataset(self, body: DatasetCreate) -> DatasetOut:
        return self.request("POST", "/datasets", json=body, adapter=TypeAdapter(DatasetOut))

    def list_datasets(self, query: DatasetQuery | None = None) -> DatasetPage:
        params = query if query is not None else DatasetQuery()
        return self.request('GET', '/datasets', params=params.model_dump(mode="json"), adapter=TypeAdapter(DatasetPage))

    def get_dataset(self, dataset_id: str) -> DatasetOut:
        return self.request("GET", f"/datasets/{dataset_id}", adapter=TypeAdapter(DatasetOut))

    def update_dataset(self, dataset_id: str, body: DatasetPatch) -> DatasetOut:
        return self.request("PATCH", f"/datasets/{dataset_id}", json=body, adapter=TypeAdapter(DatasetOut))

    def list_dataset_versions(self, dataset_id: str, limit: int = 50, offset: int = 0) -> DatasetVersionPage:
        return self.request("GET", f"/datasets/{dataset_id}/versions", params={"limit": limit, "offset": offset}, adapter=TypeAdapter(DatasetVersionPage))

    def get_dataset_version(self, dataset_id: str, version_id: str) -> DatasetVersionOut:
        return self.request("GET", f"/datasets/{dataset_id}/versions/{version_id}", adapter=TypeAdapter(DatasetVersionOut))

    def list_dataset_members(self, dataset_id: str, version_id: str, query: DatasetMemberQuery) -> DatasetMemberPage:
        return self.request(
            "GET", f"/datasets/{dataset_id}/versions/{version_id}/members", params=query.model_dump(mode="json"), adapter=TypeAdapter(DatasetMemberPage))

    def publish_dataset_version(self, dataset_id: str, body: DatasetMembersCreate) -> DatasetVersionOut:
        return self.request("POST", f"/datasets/{dataset_id}/versions", json=body, adapter=TypeAdapter(DatasetVersionOut))

    def update_dataset_members(self, dataset_id: str, body: DatasetMemberParametersUpdate) -> DatasetMemberParametersUpdateOut:
        return self.request("PATCH", f"/datasets/{dataset_id}/member-parameters", json=body, adapter=TypeAdapter(DatasetMemberParametersUpdateOut))

    def list_calibration_targets(self, limit: int = 50, offset: int = 0,
                                 frame_type: str | None = None, q: str | None = None) -> CalibrationTargetPage:
        return self.request("GET", "/calibration/targets", params={"limit": limit, "offset": offset,
                            "frame_type": frame_type, "q": q}, adapter=TypeAdapter(CalibrationTargetPage))

    def remove_library_items(self, body: LibraryEntriesRemove) -> LibraryEntriesRemoveOut:
        return self.request("DELETE", "/library/items", json=body, adapter=TypeAdapter(LibraryEntriesRemoveOut))

    def list_trash(self, limit: int = 50, offset: int = 0, group_id: str | None = None) -> LibraryTrashPage:
        return self.request("GET", "/library/trash", params={"limit": limit, "offset": offset, "group_id": group_id}, adapter=TypeAdapter(LibraryTrashPage))

    def restore_trash(self, body: LibraryTrashSelection) -> LibraryTrashRestoreOut:
        return self.request("POST", "/library/trash/restore", json=body, adapter=TypeAdapter(LibraryTrashRestoreOut))

    def preview_trash_delete(self, body: LibraryTrashSelection) -> LibraryTrashPreviewOut:
        return self.request("POST", "/library/trash/delete-preview", json=body, adapter=TypeAdapter(LibraryTrashPreviewOut))

    def delete_trash(self, body: LibraryTrashDelete) -> LibraryTrashDeleteOut:
        return self.request("POST", "/library/trash/delete", json=body, adapter=TypeAdapter(LibraryTrashDeleteOut))

    def schedule_display_preview(self, asset_id: str, version_id: str) -> DisplayPreviewState:
        return self.request("POST", f"/library/assets/{asset_id}/versions/{version_id}/previews/display", adapter=TypeAdapter(DisplayPreviewState))

    def get_display_preview_status(self, asset_id: str, version_id: str) -> DisplayPreviewState:
        return self.request("GET", f"/library/assets/{asset_id}/versions/{version_id}/previews/display/status", adapter=TypeAdapter(DisplayPreviewState))

    def read_display_preview(self, asset_id: str, version_id: str) -> bytes:
        from astrophotoflow.interfaces.client.errors import ServiceApiError

        response = self.client.get(f"/library/assets/{asset_id}/versions/{version_id}/previews/display")
        if not response.is_success:
            self._result(response)
        if response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "image/jpeg":
            raise ServiceApiError(response.status_code, "INVALID_RESPONSE", "Preview response is not image/jpeg.",
                                  response.headers.get("X-Request-ID"))
        return response.content
