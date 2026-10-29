from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from astrophotoflow.core.http import ERROR_RESPONSES, authenticate
from astrophotoflow.contracts.software import SirilCommand, SoftwareInstallRequest, SoftwareUninstallRequest, SoftwarePackage, SoftwarePreparation
from astrophotoflow.contracts.workflows import PendingSoftwareAction, SoftwarePackageDetails
from astrophotoflow.modules.software.public import get_command_catalog, list_packages, prepare_package


router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


@router.get("/software/packages", response_model=list[SoftwarePackage], dependencies=[Depends(authenticate)])
def get_software_packages(request: Request):
    return list_packages(request.app.state.settings)


@router.get("/software/packages/{package_id}/versions/{version}/commands", response_model=list[SirilCommand],
            dependencies=[Depends(authenticate)])
def get_software_commands(package_id: str, version: str):
    return get_command_catalog(package_id, version)


@router.get("/software/packages/{package_id}", response_model=SoftwarePackageDetails, dependencies=[Depends(authenticate)])
def get_software_package(package_id: str, request: Request, operation_id: UUID | None = Query(default=None)):
    return request.app.state.get_software_package_details(package_id, operation_id=operation_id)


@router.post("/software/packages/{package_id}/install", response_model=PendingSoftwareAction, status_code=202,
             dependencies=[Depends(authenticate)])
def request_software_install(package_id: str, body: SoftwareInstallRequest, request: Request):
    return request.app.state.request_software_action(package_id, body)


@router.post("/software/packages/{package_id}/uninstall", response_model=PendingSoftwareAction, status_code=202,
             dependencies=[Depends(authenticate)])
def request_software_uninstall(package_id: str, body: SoftwareUninstallRequest, request: Request):
    return request.app.state.request_software_action(package_id, body)


@router.post("/software/packages/{package_id}/prepare", response_model=SoftwarePreparation,
             dependencies=[Depends(authenticate)])
def prepare_software_package(package_id: str, request: Request):
    return prepare_package(request.app.state.settings, package_id)
