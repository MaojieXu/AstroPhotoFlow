"""Typed HTTP adaptation for explicit image metadata and calibration use cases."""

from uuid import UUID
from fastapi import APIRouter, Depends, Request
import astrophotoflow.interfaces.http.dependencies as deps
import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.image_calibration import (
    CalibrationCandidatePage,
    CalibrationCheckPage,
    CalibrationCheckRequest,
    CalibrationSearchRequest,
    DatasetCalibrationOut,
    DatasetCalibrationUpdate,
    ImageCalibrationOut,
    ImageCalibrationUpdate,
    ImageDatasetEditMembers,
    ImageOperationOut,
)
from astrophotoflow.contracts.image_imports import ScannedCalibrationCheckPage, ScannedCalibrationCheckRequest
from astrophotoflow.contracts.image_management import (
    DatasetImageDetail,
    ImageBatchResult,
    ImageDetail,
    ImageEquipmentApply,
    ImageMetadataBatch,
    MasterProvenanceOut,
    MasterProvenanceUpdate,
)

router = APIRouter(prefix="/api/v1", dependencies=[Depends(deps.authenticate)], responses=deps.ERROR_RESPONSES)


@router.get("/library/assets/{asset_id}/detail", response_model=ImageDetail, operation_id="getImageDetail")
def get_image(asset_id: UUID, session: deps.ReadSession):
    return ImageDetail.model_validate(data.get_image(session, asset_id), strict=False)


@router.post("/library/assets/metadata-updates", response_model=ImageBatchResult, operation_id="updateImageMetadataBatch")
def metadata_batch(body: ImageMetadataBatch, session: deps.WriteSession):
    return ImageBatchResult.model_validate(data.update_image_metadata_batch(session, body.items), strict=False)


@router.post("/library/assets/equipment-applications", response_model=ImageBatchResult, operation_id="applyImageEquipment")
def apply_equipment(body: ImageEquipmentApply, session: deps.WriteSession):
    return ImageBatchResult.model_validate(data.apply_image_equipment(session, body.assets, body.equipment), strict=False)


@router.get("/library/assets/{asset_id}/master-provenance", response_model=MasterProvenanceOut, operation_id="getMasterProvenance")
def master_provenance(asset_id: UUID, session: deps.ReadSession):
    return MasterProvenanceOut.model_validate(data.get_master_provenance(session, asset_id), strict=False)


@router.patch("/library/assets/{asset_id}/master-provenance", response_model=MasterProvenanceOut, operation_id="updateMasterProvenance")
def update_provenance(asset_id: UUID, body: MasterProvenanceUpdate, session: deps.WriteSession):
    return MasterProvenanceOut.model_validate(
        data.update_master_provenance(session, asset_id, body.expected_revision, body.changes), strict=False
    )


@router.get("/datasets/{dataset_id}/detail", response_model=DatasetImageDetail, operation_id="getImageDatasetDetail")
def dataset_detail(dataset_id: UUID, session: deps.ReadSession):
    return DatasetImageDetail.model_validate(data.get_image_dataset(session, dataset_id), strict=False)


@router.post("/datasets/{dataset_id}/member-edits", response_model=ImageOperationOut, operation_id="editImageDatasetMembers")
def edit_members(dataset_id: UUID, body: ImageDatasetEditMembers, session: deps.WriteSession):
    return ImageOperationOut.model_validate(data.edit_image_dataset_members(session, dataset_id, body), strict=False)


@router.post("/calibration/search", response_model=CalibrationCandidatePage, operation_id="searchImageCalibration")
def calibration_search(body: CalibrationSearchRequest, session: deps.ReadSession):
    return CalibrationCandidatePage.model_validate(data.search_image_calibration(session, body), strict=False)


@router.post("/calibration/check", response_model=CalibrationCheckPage, operation_id="checkImageCalibration")
def calibration_check(body: CalibrationCheckRequest, session: deps.ReadSession):
    return CalibrationCheckPage.model_validate(data.check_image_calibration(session, body), strict=False)


@router.post("/calibration/import-check", response_model=ScannedCalibrationCheckPage, operation_id="checkImportCalibration")
def calibration_import_check(body: ScannedCalibrationCheckRequest, request: Request, session: deps.ReadSession):
    return ScannedCalibrationCheckPage.model_validate(
        data.check_import_calibration(session, request.app.state.settings, body), strict=False
    )


@router.get("/library/assets/{asset_id}/calibration", response_model=ImageCalibrationOut, operation_id="getImageCalibration")
def image_calibration(asset_id: UUID, session: deps.ReadSession):
    return ImageCalibrationOut.model_validate(data.get_image_calibration(session, asset_id), strict=False)


@router.post("/library/assets/{asset_id}/calibration", response_model=ImageOperationOut, operation_id="updateImageCalibration")
def update_image_calibration(asset_id: UUID, body: ImageCalibrationUpdate, session: deps.WriteSession):
    return ImageOperationOut.model_validate(data.update_image_calibration(session, asset_id, body), strict=False)


@router.get("/datasets/{dataset_id}/calibration", response_model=DatasetCalibrationOut, operation_id="getDatasetCalibration")
def dataset_calibration(dataset_id: UUID, session: deps.ReadSession):
    return DatasetCalibrationOut.model_validate(data.get_image_dataset_calibration(session, dataset_id), strict=False)


@router.post("/datasets/{dataset_id}/calibration", response_model=ImageOperationOut, operation_id="updateDatasetCalibration")
def update_dataset_calibration(dataset_id: UUID, body: DatasetCalibrationUpdate, session: deps.WriteSession):
    return ImageOperationOut.model_validate(data.update_image_dataset_calibration(session, dataset_id, body), strict=False)


@router.get("/calibration/operations/{request_id}", response_model=ImageOperationOut, operation_id="getCalibrationOperation")
def get_operation(request_id: UUID, session: deps.ReadSession):
    return ImageOperationOut.model_validate(data.get_image_calibration_operation(session, request_id), strict=False)
