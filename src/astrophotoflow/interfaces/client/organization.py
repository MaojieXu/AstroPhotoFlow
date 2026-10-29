from typing import Any

from astrophotoflow.contracts.projects import ProjectDatasetReferenceCreate, ProjectReferenceCreate, ProjectReferenceDelete
from astrophotoflow.contracts.equipment import EquipmentCreate, EquipmentPatch
from astrophotoflow.contracts.projects import ProjectCreate, ProjectPatch
from astrophotoflow.contracts.setups import CapturePresetCreate, CapturePresetPatch, EquipmentSetupCreate, EquipmentSetupPatch
from astrophotoflow.contracts.trash import EquipmentDelete, EquipmentDeleteSelection


class OrganizationOperations:
    def list_projects(self, limit: int = 50, offset: int = 0, q: str | None = None,
                      status: str = "active", sort_by: str = "created_at", order: str = "desc") -> dict[str, Any]:
        return self.request("GET", "/projects", params={"limit": limit, "offset": offset, "q": q,
                            "status": status, "sort_by": sort_by, "order": order})

    def create_project(self, body: ProjectCreate) -> dict[str, Any]:
        return self.request("POST", "/projects", json=body)

    def get_project(self, project_id: str) -> dict[str, Any]:
        return self.request("GET", f"/projects/{project_id}")

    def update_project(self, project_id: str, body: ProjectPatch) -> dict[str, Any]:
        return self.request("PATCH", f"/projects/{project_id}", json=body)

    def list_project_assets(self, project_id: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        return self.request("GET", f"/projects/{project_id}/assets", params={"limit": limit, "offset": offset})

    def get_project_asset(self, project_id: str, reference_id: str) -> dict[str, Any]:
        return self.request("GET", f"/projects/{project_id}/asset-references/{reference_id}")

    def add_project_asset(self, project_id: str, body: ProjectReferenceCreate) -> dict[str, Any]:
        return self.request("POST", f"/projects/{project_id}/asset-references", json=body)

    def remove_project_asset(self, project_id: str, reference_id: str, body: ProjectReferenceDelete) -> dict[str, Any]:
        return self.request("DELETE", f"/projects/{project_id}/asset-references/{reference_id}", json=body)

    def list_project_datasets(self, project_id: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        return self.request("GET", f"/projects/{project_id}/dataset-references", params={"limit": limit, "offset": offset})

    def get_project_dataset(self, project_id: str, reference_id: str) -> dict[str, Any]:
        return self.request("GET", f"/projects/{project_id}/dataset-references/{reference_id}")

    def add_project_dataset(self, project_id: str, body: ProjectDatasetReferenceCreate) -> dict[str, Any]:
        return self.request("POST", f"/projects/{project_id}/dataset-references", json=body)

    def remove_project_dataset(self, project_id: str, reference_id: str, body: ProjectReferenceDelete) -> dict[str, Any]:
        return self.request("DELETE", f"/projects/{project_id}/dataset-references/{reference_id}", json=body)

    def list_equipment(self, limit: int = 50, offset: int = 0, q: str | None = None, status: str = "active",
                       kind: str | None = None, sort_by: str = "created_at", order: str = "desc") -> dict[str, Any]:
        return self.request("GET", "/equipment", params={"limit": limit, "offset": offset, "q": q,
                            "status": status, "kind": kind, "sort_by": sort_by, "order": order})

    def create_equipment(self, body: EquipmentCreate) -> dict[str, Any]:
        return self.request("POST", "/equipment", json=body)

    def get_equipment(self, equipment_id: str) -> dict[str, Any]:
        return self.request("GET", f"/equipment/{equipment_id}")

    def update_equipment(self, equipment_id: str, body: EquipmentPatch) -> dict[str, Any]:
        return self.request("PATCH", f"/equipment/{equipment_id}", json=body)

    def preview_equipment_delete(self, body: EquipmentDeleteSelection) -> dict[str, Any]:
        return self.request("POST", "/equipment-management/delete-preview", json=body)

    def delete_equipment_entries(self, body: EquipmentDelete) -> dict[str, Any]:
        return self.request("POST", "/equipment-management/delete", json=body)

    def list_equipment_setups(self, limit: int = 50, offset: int = 0, q: str | None = None,
                              status: str = "active", sort_by: str = "created_at", order: str = "desc") -> dict[str, Any]:
        return self.request("GET", "/equipment-setups", params={"limit": limit, "offset": offset, "q": q,
                            "status": status, "sort_by": sort_by, "order": order})

    def create_equipment_setup(self, body: EquipmentSetupCreate) -> dict[str, Any]:
        return self.request("POST", "/equipment-setups", json=body)

    def get_equipment_setup(self, setup_id: str) -> dict[str, Any]:
        return self.request("GET", f"/equipment-setups/{setup_id}")

    def update_equipment_setup(self, setup_id: str, body: EquipmentSetupPatch) -> dict[str, Any]:
        return self.request("PATCH", f"/equipment-setups/{setup_id}", json=body)

    def list_capture_presets(self, limit: int = 50, offset: int = 0, q: str | None = None,
                            status: str = "active", equipment_setup_id: str | None = None,
                            sort_by: str = "created_at", order: str = "desc") -> dict[str, Any]:
        return self.request("GET", "/capture-presets", params={"limit": limit, "offset": offset, "q": q,
                            "status": status, "equipment_setup_id": equipment_setup_id, "sort_by": sort_by, "order": order})

    def create_capture_preset(self, setup_id: str, body: CapturePresetCreate) -> dict[str, Any]:
        return self.request("POST", f"/equipment-setups/{setup_id}/presets", json=body)

    def get_capture_preset(self, preset_id: str) -> dict[str, Any]:
        return self.request("GET", f"/capture-presets/{preset_id}")

    def update_capture_preset(self, preset_id: str, body: CapturePresetPatch) -> dict[str, Any]:
        return self.request("PATCH", f"/capture-presets/{preset_id}", json=body)
