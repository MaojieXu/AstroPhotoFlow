from urllib.parse import quote
from uuid import UUID

from pydantic import TypeAdapter

from astrophotoflow.contracts.bundles import AnalysisResult
from astrophotoflow.contracts.packages import PendingSoftwareAction, SoftwarePackageDetails
from astrophotoflow.contracts.software import (
    BundlePreviewRequest,
    SoftwareCallResult,
    SoftwareCommand,
    SoftwareInstallRequest,
    SoftwarePackage,
    SoftwarePreparation,
    SoftwareReleaseListing,
    SoftwareUninstallRequest,
)
from astrophotoflow.interfaces.client.errors import ServiceApiError


class SoftwareOperations:
    def preview_bundle(self, body: BundlePreviewRequest) -> bytes:
        response = self.client.post("/software/preview", json=body.model_dump(mode="json", exclude_unset=True), timeout=None)
        if not response.is_success:
            self._result(response)
        if response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "image/png":
            raise ServiceApiError(response.status_code, "INVALID_RESPONSE", "Preview response is not image/png.", response.headers.get("X-Request-ID"))
        return response.content

    def release_bundle_preview(self, consumer_id: UUID) -> None:
        response = self.client.delete(f"/software/preview/{consumer_id}")
        if not response.is_success:
            self._result(response)

    def list_software_releases(self, package_id: str) -> SoftwareReleaseListing:
        return self.request('GET', f'/software/packages/{quote(package_id, safe="")}/releases', adapter=TypeAdapter(SoftwareReleaseListing))

    def list_software_packages(self) -> list[SoftwarePackage]:
        return self.request("GET", "/software/packages", adapter=TypeAdapter(list[SoftwarePackage]))

    def list_software_commands(self, package_id: str, version: str) -> list[SoftwareCommand]:
        path = f"/software/packages/{quote(package_id, safe='')}/versions/{quote(version, safe='')}/commands"
        return self.request("GET", path, adapter=TypeAdapter(list[SoftwareCommand]))

    def get_software_package(self, package_id: str, *, operation_id: UUID | None = None) -> SoftwarePackageDetails:
        return self.request("GET", f"/software/packages/{package_id}", params={"operation_id": operation_id}, adapter=TypeAdapter(SoftwarePackageDetails))

    def install_software(self, package_id: str, body: SoftwareInstallRequest) -> PendingSoftwareAction:
        return self.request("POST", f"/software/packages/{package_id}/install", json=body, adapter=TypeAdapter(PendingSoftwareAction))

    def prepare_software(self, package_id: str) -> SoftwarePreparation:
        return self.request("POST", f"/software/packages/{package_id}/prepare", adapter=TypeAdapter(SoftwarePreparation))

    def uninstall_software(self, package_id: str, body: SoftwareUninstallRequest) -> PendingSoftwareAction:
        return self.request("POST", f"/software/packages/{package_id}/uninstall", json=body, adapter=TypeAdapter(PendingSoftwareAction))

    def list_run_calls(self, prompt_id: str, node_id: str | None = None, limit: int = 50, offset: int = 0) -> list[SoftwareCallResult]:
        return self.request('GET', f'/runs/{prompt_id}/calls', params={'node_id': node_id, 'limit': limit, 'offset': offset}, adapter=TypeAdapter(list[SoftwareCallResult]))

    def get_run_call(self, prompt_id: str, call_id: str) -> SoftwareCallResult:
        return self.request('GET', f'/runs/{prompt_id}/calls/{call_id}', adapter=TypeAdapter(SoftwareCallResult))

    def get_run_analysis(self, prompt_id: str, call_id: str, output_index: int, member_index: int) -> list[AnalysisResult]:
        return self.request('GET', f'/runs/{prompt_id}/calls/{call_id}/outputs/{output_index}/members/{member_index}/analysis', adapter=TypeAdapter(list[AnalysisResult]))
from uuid import UUID
