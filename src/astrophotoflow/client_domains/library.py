from pathlib import Path
from typing import Any

from ..backend.import_schemas import (
    AssetParametersPatch, AssetPatch, DatasetCreate, DatasetMemberParametersUpdate,
    DatasetMembersCreate, DatasetPatch, LibraryEntriesRemove, LibraryTrashDelete, LibraryTrashSelection,
)


class LibraryOperations:
    def list_assets(self, limit: int = 50, offset: int = 0, q: str | None = None, status: str = "active",
                    frame_type: str | None = None, role: str | None = None, sort_by: str = "created_at",
                    order: str = "desc") -> dict[str, Any]:
        return self.request("GET", "/library/assets", params={"limit": limit, "offset": offset, "q": q,
                            "status": status, "frame_type": frame_type, "role": role, "sort_by": sort_by, "order": order})

    def list_library_items(self, limit: int = 50, offset: int = 0, q: str | None = None,
                           frame_type: str | None = None, frame_class: str | None = None,
                           role: str | None = None, sort_by: str = "created_at", order: str = "desc") -> dict[str, Any]:
        return self.request("GET", "/library/items", params={"limit": limit, "offset": offset, "q": q,
                            "frame_type": frame_type, "frame_class": frame_class, "role": role,
                            "sort_by": sort_by, "order": order})

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        return self.request("GET", f"/library/assets/{asset_id}")

    def update_asset(self, asset_id: str, body: AssetPatch) -> dict[str, Any]:
        return self.request("PATCH", f"/library/assets/{asset_id}", json=body)

    def update_asset_parameters(self, asset_id: str, base_revision: int, parameters: AssetParametersPatch) -> dict[str, Any]:
        return self.update_asset(asset_id, AssetPatch(base_revision=base_revision, parameters=parameters))

    def list_asset_versions(self, asset_id: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        return self.request("GET", f"/library/assets/{asset_id}/versions", params={"limit": limit, "offset": offset})

    def get_asset_version(self, asset_id: str, version_id: str) -> dict[str, Any]:
        return self.request("GET", f"/library/assets/{asset_id}/versions/{version_id}")

    def create_dataset(self, body: DatasetCreate) -> dict[str, Any]:
        return self.request("POST", "/datasets", json=body)

    def list_datasets(self, limit: int = 50, offset: int = 0, q: str | None = None,
                      status: str = "active", sort_by: str = "created_at", order: str = "desc") -> dict[str, Any]:
        return self.request("GET", "/datasets", params={"limit": limit, "offset": offset, "q": q,
                            "status": status, "sort_by": sort_by, "order": order})

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        return self.request("GET", f"/datasets/{dataset_id}")

    def update_dataset(self, dataset_id: str, body: DatasetPatch) -> dict[str, Any]:
        return self.request("PATCH", f"/datasets/{dataset_id}", json=body)

    def list_dataset_versions(self, dataset_id: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        return self.request("GET", f"/datasets/{dataset_id}/versions", params={"limit": limit, "offset": offset})

    def get_dataset_version(self, dataset_id: str, version_id: str) -> dict[str, Any]:
        return self.request("GET", f"/datasets/{dataset_id}/versions/{version_id}")

    def publish_dataset_version(self, dataset_id: str, body: DatasetMembersCreate) -> dict[str, Any]:
        return self.request("POST", f"/datasets/{dataset_id}/versions", json=body)

    def update_dataset_members(self, dataset_id: str, body: DatasetMemberParametersUpdate) -> dict[str, Any]:
        return self.request("PATCH", f"/datasets/{dataset_id}/member-parameters", json=body)

    def list_calibration_targets(self, limit: int = 50, offset: int = 0,
                                 frame_type: str | None = None, q: str | None = None) -> dict[str, Any]:
        return self.request("GET", "/calibration/targets", params={"limit": limit, "offset": offset,
                            "frame_type": frame_type, "q": q})

    def remove_library_items(self, body: LibraryEntriesRemove) -> dict[str, Any]:
        return self.request("DELETE", "/library/items", json=body)

    def list_trash(self, limit: int = 50, offset: int = 0, group_id: str | None = None) -> dict[str, Any]:
        return self.request("GET", "/library/trash", params={"limit": limit, "offset": offset, "group_id": group_id})

    def restore_trash(self, body: LibraryTrashSelection) -> dict[str, Any]:
        return self.request("POST", "/library/trash/restore", json=body)

    def preview_trash_delete(self, body: LibraryTrashSelection) -> dict[str, Any]:
        return self.request("POST", "/library/trash/delete-preview", json=body)

    def delete_trash(self, body: LibraryTrashDelete) -> dict[str, Any]:
        return self.request("POST", "/library/trash/delete", json=body)

    def schedule_display_preview(self, asset_id: str, version_id: str) -> dict[str, Any]:
        return self.request("POST", f"/library/assets/{asset_id}/versions/{version_id}/previews/display")

    def get_display_preview_status(self, asset_id: str, version_id: str) -> dict[str, Any]:
        return self.request("GET", f"/library/assets/{asset_id}/versions/{version_id}/previews/display/status")

    def read_display_preview(self, asset_id: str, version_id: str) -> bytes:
        from ..client import ServiceApiError

        response = self.client.get(f"/library/assets/{asset_id}/versions/{version_id}/previews/display")
        if not response.is_success:
            self._result(response)
        if response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "image/jpeg":
            raise ServiceApiError(response.status_code, "INVALID_RESPONSE", "Preview response is not image/jpeg.",
                                  response.headers.get("X-Request-ID"))
        return response.content

    def export_display_preview(self, asset_id: str, version_id: str, output: Path) -> dict[str, Any]:
        data = self.read_display_preview(asset_id, version_id)
        output = output.expanduser().resolve()
        with output.open("xb") as stream:
            stream.write(data)
        return {"path": str(output), "byte_size": len(data)}
