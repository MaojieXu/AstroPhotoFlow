from urllib.parse import quote
from uuid import UUID

from astrophotoflow.contracts.software import SirilCommand, SoftwareInstallRequest, SoftwareUninstallRequest, SoftwarePackage, SoftwarePreparation
from astrophotoflow.contracts.workflows import PendingSoftwareAction, SoftwarePackageDetails


class SoftwareOperations:
    def list_software_packages(self) -> list[SoftwarePackage]:
        return [SoftwarePackage.model_validate(item) for item in self.request("GET", "/software/packages")]

    def list_software_commands(self, package_id: str, version: str) -> list[SirilCommand]:
        path = f"/software/packages/{quote(package_id, safe='')}/versions/{quote(version, safe='')}/commands"
        return [SirilCommand.model_validate(item) for item in self.request("GET", path)]

    def get_software_package(self, package_id: str, *, operation_id: UUID | None = None) -> SoftwarePackageDetails:
        return SoftwarePackageDetails.model_validate(self.request(
            "GET", f"/software/packages/{package_id}", params={"operation_id": operation_id},
        ))

    def install_software(self, package_id: str, body: SoftwareInstallRequest) -> PendingSoftwareAction:
        return PendingSoftwareAction.model_validate(self.request("POST", f"/software/packages/{package_id}/install", json=body))

    def prepare_software(self, package_id: str) -> SoftwarePreparation:
        return SoftwarePreparation.model_validate(self.request("POST", f"/software/packages/{package_id}/prepare"))

    def uninstall_software(self, package_id: str, body: SoftwareUninstallRequest) -> PendingSoftwareAction:
        return PendingSoftwareAction.model_validate(self.request("POST", f"/software/packages/{package_id}/uninstall", json=body))
from uuid import UUID
