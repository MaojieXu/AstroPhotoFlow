from base64 import b64encode
from typing import Any

from mcp.types import ImageContent

from astrophotoflow.contracts.assets import AssetParametersPatch, AssetPatch
from astrophotoflow.contracts.datasets import DatasetCreate, DatasetMemberParametersUpdate, DatasetMembersCreate, DatasetPatch
from astrophotoflow.contracts.trash import LibraryEntriesRemove, LibraryTrashDelete, LibraryTrashSelection
from astrophotoflow.contracts.inputs import CanvasDataRequest



def register(server, call):
    @server.tool()
    def prepare_canvas_data(body: CanvasDataRequest) -> dict[str, Any]:
        """Prepare a fixed scientific reference for a single asset or ordered group; this does not apply it to a canvas."""
        return call(lambda client: client.prepare_canvas_data(body))

    @server.tool()
    def list_assets(limit: int = 50, offset: int = 0, q: str | None = None, status: str = "active", frame_type: str | None = None, role: str | None = None, sort_by: str = "created_at", order: str = "desc") -> dict[str, Any]:
        """Page through shared assets, optionally filtering names, status, role or frame use."""
        return call(lambda client: client.list_assets(limit, offset, q, status, frame_type, role, sort_by, order))


    @server.tool()
    def list_library_items(limit: int = 50, offset: int = 0, q: str | None = None, frame_type: str | None = None, frame_class: str | None = None, role: str | None = None, sort_by: str = "created_at", order: str = "desc") -> dict[str, Any]:
        """List the library view containing logical datasets and independent assets."""
        return call(lambda client: client.list_library_items(limit, offset, q, frame_type, frame_class, role, sort_by, order))


    @server.tool()
    def get_asset(asset_id: str) -> dict[str, Any]:
        """Read a shared asset and its revision, classification, current parameters and original readiness."""
        return call(lambda client: client.get_asset(asset_id))


    @server.tool()
    def update_asset(asset_id: str, body: AssetPatch) -> dict[str, Any]:
        """Patch asset metadata, classification or parameters at base_revision. Omitted fields remain; explicit null clears; zero is retained."""
        return call(lambda client: client.update_asset(asset_id, body))


    @server.tool()
    def update_asset_parameters(asset_id: str, base_revision: int, parameters: AssetParametersPatch) -> dict[str, Any]:
        """Patch supplied asset parameters at the current revision. Omitted fields remain, null clears and zero is valid."""
        return call(lambda client: client.update_asset_parameters(asset_id, base_revision, parameters))


    @server.tool()
    def list_asset_versions(asset_id: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List fixed original asset versions."""
        return call(lambda client: client.list_asset_versions(asset_id, limit, offset))


    @server.tool()
    def get_asset_version(asset_id: str, version_id: str) -> dict[str, Any]:
        """Read a fixed original version and its immutable intake facts."""
        return call(lambda client: client.get_asset_version(asset_id, version_id))


    @server.tool()
    def create_dataset(body: DatasetCreate) -> dict[str, Any]:
        """Create a logical group of fixed asset versions without copying originals."""
        return call(lambda client: client.create_dataset(body))


    @server.tool()
    def list_datasets(limit: int = 50, offset: int = 0, q: str | None = None, status: str = "active", sort_by: str = "created_at", order: str = "desc") -> dict[str, Any]:
        """Page through logical datasets."""
        return call(lambda client: client.list_datasets(limit, offset, q, status, sort_by, order))


    @server.tool()
    def get_dataset(dataset_id: str) -> dict[str, Any]:
        """Read a dataset revision and current version ID."""
        return call(lambda client: client.get_dataset(dataset_id))


    @server.tool()
    def update_dataset(dataset_id: str, body: DatasetPatch) -> dict[str, Any]:
        """Update group metadata or archive it using base_revision."""
        return call(lambda client: client.update_dataset(dataset_id, body))


    @server.tool()
    def list_dataset_versions(dataset_id: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List fixed group versions with canonical ordered members and calibration bindings."""
        return call(lambda client: client.list_dataset_versions(dataset_id, limit, offset))


    @server.tool()
    def get_dataset_version(dataset_id: str, version_id: str) -> dict[str, Any]:
        """Read all ordered members and calibration bindings from a fixed group version."""
        return call(lambda client: client.get_dataset_version(dataset_id, version_id))


    @server.tool()
    def publish_dataset_version(dataset_id: str, body: DatasetMembersCreate) -> dict[str, Any]:
        """Publish complete membership and optional calibration maps. Retained members keep relative order; new members append. Defaults replace when supplied; submitted member maps replace, missing members retain; absent slots inherit and null disables."""
        return call(lambda client: client.publish_dataset_version(dataset_id, body))


    @server.tool()
    def update_dataset_members(dataset_id: str, body: DatasetMemberParametersUpdate) -> dict[str, Any]:
        """Batch patch group member parameters/classification using dataset revision, fixed base version and revisions for ALL current canonical group assets."""
        return call(lambda client: client.update_dataset_members(dataset_id, body))


    @server.tool()
    def list_calibration_targets(limit: int = 50, offset: int = 0, frame_type: str | None = None, q: str | None = None) -> dict[str, Any]:
        """Find fixed Master asset or calibration dataset version targets, with pagination."""
        return call(lambda client: client.list_calibration_targets(limit, offset, frame_type, q))


    @server.tool()
    def remove_library_items(body: LibraryEntriesRemove) -> dict[str, Any]:
        """Move selected library entries to reversible trash using their current revisions and version IDs."""
        return call(lambda client: client.remove_library_items(body))


    @server.tool()
    def list_trash(limit: int = 50, offset: int = 0, group_id: str | None = None) -> dict[str, Any]:
        """List removed entries and partial or failed cleanup outcomes. Use returned identities for restore/delete preview."""
        return call(lambda client: client.list_trash(limit, offset, group_id))


    @server.tool()
    def restore_trash(body: LibraryTrashSelection) -> dict[str, Any]:
        """Restore the selected trash records without deleting originals."""
        return call(lambda client: client.restore_trash(body))


    @server.tool()
    def preview_trash_delete(body: LibraryTrashSelection) -> dict[str, Any]:
        """Preview permanent cleanup: inspect references, tasks, managed files and fingerprint before explicit deletion."""
        return call(lambda client: client.preview_trash_delete(body))


    @server.tool()
    def delete_trash(body: LibraryTrashDelete) -> dict[str, Any]:
        """Permanently clean selected trash using the current preview fingerprint only when the user authorized this cleanup. Historical references remain protected; re-read trash and preview after partial failures."""
        return call(lambda client: client.delete_trash(body))

    @server.tool()
    def schedule_display_preview(asset_id: str, version_id: str) -> dict[str, Any]:
        """Schedule or retry a lazy display JPEG for a fixed original version. Poll get_display_preview_status for readiness."""
        return call(lambda client: client.schedule_display_preview(asset_id, version_id))

    @server.tool()
    def get_display_preview_status(asset_id: str, version_id: str) -> dict[str, Any]:
        """Read display preview state and errors. Poll generating; for not_ready inspect original/task readiness and wait only for live import/retry work. Cached failed/unsupported are terminal."""
        return call(lambda client: client.get_display_preview_status(asset_id, version_id))

    @server.tool(structured_output=False)
    def read_display_preview(asset_id: str, version_id: str) -> ImageContent:
        """Explicitly read an available cached display JPEG as an MCP image. Schedule and poll first; routine import results contain no image data."""
        data = call(lambda client: client.read_display_preview(asset_id, version_id))
        return ImageContent(type="image", data=b64encode(data).decode("ascii"), mimeType="image/jpeg")
