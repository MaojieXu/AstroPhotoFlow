from typing import Any

from ..backend.import_schemas import ProjectDatasetReferenceCreate, ProjectReferenceCreate, ProjectReferenceDelete
from ..backend.schemas import EquipmentCreate, EquipmentPatch, ProjectCreate, ProjectPatch
from ..backend.setup_schemas import CapturePresetCreate, CapturePresetPatch, EquipmentSetupCreate, EquipmentSetupPatch



def register(server, call):
    @server.tool()
    def list_projects(limit: int = 50, offset: int = 0, q: str | None = None, status: str = "active", sort_by: str = "created_at", order: str = "desc") -> dict[str, Any]:
        """Page through projects."""
        return call(lambda client: client.list_projects(limit, offset, q, status, sort_by, order))


    @server.tool()
    def create_project(body: ProjectCreate) -> dict[str, Any]:
        """Create a project organized by target or processing task."""
        return call(lambda client: client.create_project(body))


    @server.tool()
    def get_project(project_id: str) -> dict[str, Any]:
        """Read a project and its current revision."""
        return call(lambda client: client.get_project(project_id))


    @server.tool()
    def update_project(project_id: str, body: ProjectPatch) -> dict[str, Any]:
        """Patch or archive a project at base_revision; configuration deletion is archival."""
        return call(lambda client: client.update_project(project_id, body))


    @server.tool()
    def list_project_assets(project_id: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List project references pinned to fixed asset versions."""
        return call(lambda client: client.list_project_assets(project_id, limit, offset))


    @server.tool()
    def get_project_asset(project_id: str, reference_id: str) -> dict[str, Any]:
        """Read one project asset reference and its pinned version."""
        return call(lambda client: client.get_project_asset(project_id, reference_id))


    @server.tool()
    def add_project_asset(project_id: str, body: ProjectReferenceCreate) -> dict[str, Any]:
        """Pin an existing asset version to a project without copying the original. Requires current project revision."""
        return call(lambda client: client.add_project_asset(project_id, body))


    @server.tool()
    def remove_project_asset(project_id: str, reference_id: str, body: ProjectReferenceDelete) -> dict[str, Any]:
        """Remove a project asset reference at project base_revision; retain library originals."""
        return call(lambda client: client.remove_project_asset(project_id, reference_id, body))


    @server.tool()
    def list_project_datasets(project_id: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List project references pinned to fixed dataset versions."""
        return call(lambda client: client.list_project_datasets(project_id, limit, offset))


    @server.tool()
    def get_project_dataset(project_id: str, reference_id: str) -> dict[str, Any]:
        """Read one pinned project dataset reference."""
        return call(lambda client: client.get_project_dataset(project_id, reference_id))


    @server.tool()
    def add_project_dataset(project_id: str, body: ProjectDatasetReferenceCreate) -> dict[str, Any]:
        """Pin a fixed dataset version to a project at the current project revision."""
        return call(lambda client: client.add_project_dataset(project_id, body))


    @server.tool()
    def remove_project_dataset(project_id: str, reference_id: str, body: ProjectReferenceDelete) -> dict[str, Any]:
        """Remove a project dataset reference at project base_revision; retain the logical dataset."""
        return call(lambda client: client.remove_project_dataset(project_id, reference_id, body))


    @server.tool()
    def list_equipment(limit: int = 50, offset: int = 0, q: str | None = None, status: str = "active", kind: str | None = None, sort_by: str = "created_at", order: str = "desc") -> dict[str, Any]:
        """Page through registered cameras, telescopes, optical systems, filters, mounts and accessories."""
        return call(lambda client: client.list_equipment(limit, offset, q, status, kind, sort_by, order))


    @server.tool()
    def create_equipment(body: EquipmentCreate) -> dict[str, Any]:
        """Register equipment with the backend discriminated kind/specification schema."""
        return call(lambda client: client.create_equipment(body))


    @server.tool()
    def get_equipment(equipment_id: str) -> dict[str, Any]:
        """Read registered equipment."""
        return call(lambda client: client.get_equipment(equipment_id))


    @server.tool()
    def update_equipment(equipment_id: str, body: EquipmentPatch) -> dict[str, Any]:
        """Patch or archive registered equipment at base_revision. Include its kind."""
        return call(lambda client: client.update_equipment(equipment_id, body))


    @server.tool()
    def list_equipment_setups(limit: int = 50, offset: int = 0, q: str | None = None, status: str = "active", sort_by: str = "created_at", order: str = "desc") -> dict[str, Any]:
        """Page through equipment setups."""
        return call(lambda client: client.list_equipment_setups(limit, offset, q, status, sort_by, order))


    @server.tool()
    def create_equipment_setup(body: EquipmentSetupCreate) -> dict[str, Any]:
        """Create a setup with registered references or inline equipment snapshots. Inline equipment is not auto-registered."""
        return call(lambda client: client.create_equipment_setup(body))


    @server.tool()
    def get_equipment_setup(setup_id: str) -> dict[str, Any]:
        """Read an equipment setup."""
        return call(lambda client: client.get_equipment_setup(setup_id))


    @server.tool()
    def update_equipment_setup(setup_id: str, body: EquipmentSetupPatch) -> dict[str, Any]:
        """Patch or archive a setup without modifying registered equipment."""
        return call(lambda client: client.update_equipment_setup(setup_id, body))


    @server.tool()
    def list_capture_presets(limit: int = 50, offset: int = 0, q: str | None = None, status: str = "active", equipment_setup_id: str | None = None, sort_by: str = "created_at", order: str = "desc") -> dict[str, Any]:
        """Page through capture presets, optionally restricted to their owning setup."""
        return call(lambda client: client.list_capture_presets(limit, offset, q, status, equipment_setup_id, sort_by, order))


    @server.tool()
    def create_capture_preset(setup_id: str, body: CapturePresetCreate) -> dict[str, Any]:
        """Create a capture preset owned by a setup; omitted defaults stay unknown."""
        return call(lambda client: client.create_capture_preset(setup_id, body))


    @server.tool()
    def get_capture_preset(preset_id: str) -> dict[str, Any]:
        """Read a capture preset and its owning setup."""
        return call(lambda client: client.get_capture_preset(preset_id))


    @server.tool()
    def update_capture_preset(preset_id: str, body: CapturePresetPatch) -> dict[str, Any]:
        """Patch or archive a preset. Already accepted import snapshots remain immutable."""
        return call(lambda client: client.update_capture_preset(preset_id, body))
