from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from astrophotoflow.contracts.packages import PendingSoftwareAction, SoftwarePackageDetails
from astrophotoflow.contracts.software import (
    SirilCommand,
    SoftwareInstallRequest,
    SoftwarePackage,
    SoftwarePreparation,
    SoftwareReleaseListing,
    SoftwareUninstallRequest,
)
from astrophotoflow.interfaces.http.dependencies import ERROR_RESPONSES, authenticate
from astrophotoflow.modules.software.public import get_command_catalog, list_packages, list_releases, prepare_package

router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


@router.get("/software/packages", response_model=list[SoftwarePackage], dependencies=[Depends(authenticate)], operation_id='get_software_packages_api_v1_software_packages_get')
def get_software_packages(request: Request):
    return list_packages(request.app.state.settings)


@router.get('/software/packages/{package_id}/releases', response_model=SoftwareReleaseListing, dependencies=[Depends(authenticate)], operation_id='get_software_releases_api_v1_software_packages__package_id__releases_get')
def get_software_releases(package_id: str, request: Request):
    return list_releases(request.app.state.settings, package_id)


@router.get("/software/packages/{package_id}/versions/{version}/commands", response_model=list[SirilCommand],
            dependencies=[Depends(authenticate)], operation_id='get_software_commands_api_v1_software_packages__package_id__versions__version__commands_get')
def get_software_commands(package_id: str, version: str, request: Request):
    return get_command_catalog(package_id, version, request.app.state.settings)


@router.get("/software/packages/{package_id}", response_model=SoftwarePackageDetails, dependencies=[Depends(authenticate)], operation_id='get_software_package_api_v1_software_packages__package_id__get')
def get_software_package(package_id: str, request: Request, operation_id: Annotated[UUID | None, Query()] = None):
    return request.app.state.get_software_package_details(package_id, operation_id=operation_id)


@router.post("/software/packages/{package_id}/install", response_model=PendingSoftwareAction, status_code=202,
             dependencies=[Depends(authenticate)], operation_id='request_software_install_api_v1_software_packages__package_id__install_post')
def request_software_install(package_id: str, body: SoftwareInstallRequest, request: Request):
    return request.app.state.request_software_action(package_id, body)


@router.post("/software/packages/{package_id}/uninstall", response_model=PendingSoftwareAction, status_code=202,
             dependencies=[Depends(authenticate)], operation_id='request_software_uninstall_api_v1_software_packages__package_id__uninstall_post')
def request_software_uninstall(package_id: str, body: SoftwareUninstallRequest, request: Request):
    return request.app.state.request_software_action(package_id, body)


@router.post("/software/packages/{package_id}/prepare", response_model=SoftwarePreparation,
             dependencies=[Depends(authenticate)], operation_id='prepare_software_package_api_v1_software_packages__package_id__prepare_post')
def prepare_software_package(package_id: str, request: Request):
    return prepare_package(request.app.state.settings, package_id)
