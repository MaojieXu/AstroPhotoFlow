"""Map API metadata groups to their single set of persisted scalar columns."""

from astrophotoflow.contracts.metadata import AssetClassification, AssetParametersPatch
from astrophotoflow.modules.data.assets.models import Asset


def asset_parameters(asset: Asset) -> dict:
    return {name: getattr(asset, name) for name in AssetParametersPatch.model_fields}


def asset_classification(asset: Asset) -> dict:
    return {name: getattr(asset, name) for name in AssetClassification.model_fields}


def parameter_columns(values: dict | AssetParametersPatch) -> dict:
    model = values if isinstance(values, AssetParametersPatch) else AssetParametersPatch.model_validate(values)
    return model.model_dump(mode="json", exclude_unset=True)


def classification_columns(values: dict | AssetClassification | None) -> dict:
    if values is None:
        return {name: None for name in AssetClassification.model_fields}
    model = values if isinstance(values, AssetClassification) else AssetClassification.model_validate(values)
    return model.model_dump(mode="json", exclude_unset=True)


def set_asset_parameters(asset: Asset, values: dict | AssetParametersPatch) -> None:
    for name, value in parameter_columns(values).items():
        setattr(asset, name, value)


def set_asset_classification(asset: Asset, values: dict | AssetClassification) -> None:
    for name, value in classification_columns(values).items():
        setattr(asset, name, value)


CALIBRATION_TYPES = {"bias", "dark", "flat", "dark_flat"}

def capture_role(classification: dict) -> tuple[str, str | None]:
    frame_type = classification.get("frame_type")
    if frame_type in CALIBRATION_TYPES:
        level = {"masterframe": "master", "subframe": "individual"}.get(classification.get("frame_class"))
        return "calibration", level
    return "raw", None


PARAMETER_KEYS = (
    "camera_id", "optical_system_id", "filter_id", "parameter_mode", "iso", "gain", "offset",
    "exposure_seconds", "integration_seconds", "sensor_temperature_c", "binning_x", "binning_y", "cfa_pattern", "readout_mode",
)
