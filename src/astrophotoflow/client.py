from __future__ import annotations

from pydantic import TypeAdapter

from astrophotoflow.contracts.localization import WorkspaceLocale
from astrophotoflow.contracts.workbench import ConfigSave, ConfigState, DirectorySelectionResult
from astrophotoflow.interfaces.client.canvas import CanvasOperations
from astrophotoflow.interfaces.client.errors import ServiceApiError
from astrophotoflow.interfaces.client.exports import ExportOperations
from astrophotoflow.interfaces.client.image_management import ImageManagementOperations
from astrophotoflow.interfaces.client.imports import ImportOperations
from astrophotoflow.interfaces.client.library import LibraryOperations
from astrophotoflow.interfaces.client.organization import OrganizationOperations
from astrophotoflow.interfaces.client.software import SoftwareOperations
from astrophotoflow.interfaces.client.transport import HttpTransport


class AssetClient(ImageManagementOperations, ImportOperations, LibraryOperations, OrganizationOperations, SoftwareOperations, CanvasOperations, ExportOperations, HttpTransport):
    def get_workbench_configuration(self) -> ConfigState:
        return self.request("GET", "/settings/workbench", adapter=TypeAdapter(ConfigState))

    def get_workspace_locale(self) -> WorkspaceLocale:
        return self.request('GET', '/settings/locale', adapter=TypeAdapter(WorkspaceLocale))

    def save_workbench_configuration(self, body: ConfigSave) -> ConfigState:
        return self.request("PATCH", "/settings/workbench", json=body, adapter=TypeAdapter(ConfigState))

    def select_workbench_directory(self, path: str) -> DirectorySelectionResult:
        return self._result(self.client.post(
            "/settings/workbench/select-directory", json={"path": path}, timeout=None,
        ), adapter=TypeAdapter(DirectorySelectionResult))


__all__ = ["AssetClient", "ServiceApiError"]
