from pydantic import TypeAdapter

from astrophotoflow.contracts.equipment import EquipmentCreate, EquipmentOut, EquipmentPage, EquipmentPatch, EquipmentQuery
from astrophotoflow.contracts.projects import (
    ProjectAssetReferenceOut,
    ProjectAssetReferencePage,
    ProjectCreate,
    ProjectDatasetReferenceCreate,
    ProjectDatasetReferenceOut,
    ProjectDatasetReferencePage,
    ProjectOut,
    ProjectPage,
    ProjectPatch,
    ProjectQuery,
    ProjectReferenceCreate,
    ProjectReferenceDelete,
    ProjectReferenceDeleteResult,
)
from astrophotoflow.contracts.setups import (
    EquipmentSetupCreate,
    EquipmentSetupOut,
    EquipmentSetupPage,
    EquipmentSetupPatch,
    EquipmentSetupQuery,
)
from astrophotoflow.contracts.trash import EquipmentDelete, EquipmentDeleteSelection, ManagementTrashDeleteOut, ManagementTrashPreviewOut


class OrganizationOperations:
    def list_projects(self, query: ProjectQuery | None = None) -> ProjectPage:
        params = query if query is not None else ProjectQuery()
        return self.request('GET', '/projects', params=params.model_dump(mode="json"), adapter=TypeAdapter(ProjectPage))

    def create_project(self, body: ProjectCreate) -> ProjectOut:
        return self.request("POST", "/projects", json=body, adapter=TypeAdapter(ProjectOut))

    def get_project(self, project_id: str) -> ProjectOut:
        return self.request("GET", f"/projects/{project_id}", adapter=TypeAdapter(ProjectOut))

    def update_project(self, project_id: str, body: ProjectPatch) -> ProjectOut:
        return self.request("PATCH", f"/projects/{project_id}", json=body, adapter=TypeAdapter(ProjectOut))

    def list_project_assets(self, project_id: str, limit: int = 50, offset: int = 0) -> ProjectAssetReferencePage:
        return self.request("GET", f"/projects/{project_id}/assets", params={"limit": limit, "offset": offset}, adapter=TypeAdapter(ProjectAssetReferencePage))

    def get_project_asset(self, project_id: str, reference_id: str) -> ProjectAssetReferenceOut:
        return self.request("GET", f"/projects/{project_id}/asset-references/{reference_id}", adapter=TypeAdapter(ProjectAssetReferenceOut))

    def add_project_asset(self, project_id: str, body: ProjectReferenceCreate) -> ProjectAssetReferenceOut:
        return self.request("POST", f"/projects/{project_id}/asset-references", json=body, adapter=TypeAdapter(ProjectAssetReferenceOut))

    def remove_project_asset(self, project_id: str, reference_id: str, body: ProjectReferenceDelete) -> ProjectReferenceDeleteResult:
        return self.request("DELETE", f"/projects/{project_id}/asset-references/{reference_id}", json=body, adapter=TypeAdapter(ProjectReferenceDeleteResult))

    def list_project_datasets(self, project_id: str, limit: int = 50, offset: int = 0) -> ProjectDatasetReferencePage:
        return self.request("GET", f"/projects/{project_id}/dataset-references", params={"limit": limit, "offset": offset}, adapter=TypeAdapter(ProjectDatasetReferencePage))

    def get_project_dataset(self, project_id: str, reference_id: str) -> ProjectDatasetReferenceOut:
        return self.request("GET", f"/projects/{project_id}/dataset-references/{reference_id}", adapter=TypeAdapter(ProjectDatasetReferenceOut))

    def add_project_dataset(self, project_id: str, body: ProjectDatasetReferenceCreate) -> ProjectDatasetReferenceOut:
        return self.request("POST", f"/projects/{project_id}/dataset-references", json=body, adapter=TypeAdapter(ProjectDatasetReferenceOut))

    def remove_project_dataset(self, project_id: str, reference_id: str, body: ProjectReferenceDelete) -> ProjectReferenceDeleteResult:
        return self.request("DELETE", f"/projects/{project_id}/dataset-references/{reference_id}", json=body, adapter=TypeAdapter(ProjectReferenceDeleteResult))

    def list_equipment(self, query: EquipmentQuery | None = None) -> EquipmentPage:
        params = query if query is not None else EquipmentQuery()
        return self.request('GET', '/equipment', params=params.model_dump(mode="json"), adapter=TypeAdapter(EquipmentPage))

    def create_equipment(self, body: EquipmentCreate) -> EquipmentOut:
        return self.request("POST", "/equipment", json=body, adapter=TypeAdapter(EquipmentOut))

    def get_equipment(self, equipment_id: str) -> EquipmentOut:
        return self.request("GET", f"/equipment/{equipment_id}", adapter=TypeAdapter(EquipmentOut))

    def update_equipment(self, equipment_id: str, body: EquipmentPatch) -> EquipmentOut:
        return self.request("PATCH", f"/equipment/{equipment_id}", json=body, adapter=TypeAdapter(EquipmentOut))

    def preview_equipment_delete(self, body: EquipmentDeleteSelection) -> ManagementTrashPreviewOut:
        return self.request("POST", "/equipment-management/delete-preview", json=body, adapter=TypeAdapter(ManagementTrashPreviewOut))

    def delete_equipment_entries(self, body: EquipmentDelete) -> ManagementTrashDeleteOut:
        return self.request("POST", "/equipment-management/delete", json=body, adapter=TypeAdapter(ManagementTrashDeleteOut))

    def list_equipment_setups(self, query: EquipmentSetupQuery | None = None) -> EquipmentSetupPage:
        params = query if query is not None else EquipmentSetupQuery()
        return self.request('GET', '/equipment-setups', params=params.model_dump(mode="json"), adapter=TypeAdapter(EquipmentSetupPage))

    def create_equipment_setup(self, body: EquipmentSetupCreate) -> EquipmentSetupOut:
        return self.request("POST", "/equipment-setups", json=body, adapter=TypeAdapter(EquipmentSetupOut))

    def get_equipment_setup(self, setup_id: str) -> EquipmentSetupOut:
        return self.request("GET", f"/equipment-setups/{setup_id}", adapter=TypeAdapter(EquipmentSetupOut))

    def update_equipment_setup(self, setup_id: str, body: EquipmentSetupPatch) -> EquipmentSetupOut:
        return self.request("PATCH", f"/equipment-setups/{setup_id}", json=body, adapter=TypeAdapter(EquipmentSetupOut))
