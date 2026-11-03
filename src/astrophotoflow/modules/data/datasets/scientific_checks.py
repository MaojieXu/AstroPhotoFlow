"""Read scientific compatibility facts without decoding or changing image files."""

from sqlalchemy import select

from astrophotoflow.modules.data.assets.metadata import asset_parameters
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion, FitsHduMetadata
from astrophotoflow.modules.data.datasets.calibration import version_classification


def version_facts(session, version_id: str) -> dict:
    version = session.get(AssetVersion, str(version_id))
    asset = session.get(Asset, version.asset_id) if version else None
    if asset is None:
        return {"asset_version_id": str(version_id), "missing": True}
    snapshot = version.capture_snapshot or {}
    parameters = dict(snapshot.get("parameters") or {})
    if asset.current_version_id == version.id:
        parameters = asset_parameters(asset)
    metadata = version.scientific_metadata or {}
    selected = session.scalar(select(FitsHduMetadata).where(
        FitsHduMetadata.asset_version_id == version.id, FitsHduMetadata.is_selected.is_(True),
    ))
    shape = selected.shape if selected else metadata.get("shape")
    dimensions = None
    if shape is not None:
        dimensions = list(shape)
    elif metadata.get("width") is not None and metadata.get("height") is not None:
        dimensions = [metadata["height"], metadata["width"]]
    return {
        "asset_version_id": version.id, "asset_id": asset.id,
        "asset_revision": asset.revision if asset.current_version_id == version.id else None,
        "metadata_basis": "current_metadata" if asset.current_version_id == version.id else "frozen_capture_snapshot",
        "missing": False, "availability": version.availability,
        "classification": version_classification(asset, version),
        "parameters": parameters, "dimensions": dimensions,
        "pixel_layout": selected.supported_kind if selected else metadata.get("supported_kind"),
        "equipment_snapshot": asset.equipment_snapshot if asset.current_version_id == version.id else snapshot.get("equipment_snapshot", {}),
    }


def compare_facts(source: dict, target: dict, frame_type: str) -> list[dict]:
    """Return conflicts and unknowns; absence never counts as a successful match."""
    issues = []

    def issue(code, field, severity, left=None, right=None):
        issues.append({"code": code, "field": field, "severity": severity,
                       "source_asset_version_id": source["asset_version_id"],
                       "target_asset_version_id": target["asset_version_id"],
                       "source_value": left, "target_value": right})

    if source.get("missing") or target.get("missing"):
        issue("REFERENCE_MISSING", "asset_version_id", "conflict")
        return issues
    for facts in (source, target):
        if facts.get("availability") != "available":
            issue("CONTENT_UNAVAILABLE", "availability", "conflict", source.get("availability"), target.get("availability"))
            break
    left, right = source["parameters"], target["parameters"]
    fields = ["camera_id", "binning_x", "binning_y", "cfa_pattern"]
    mode = left.get("parameter_mode")
    if frame_type in {"bias", "dark", "dark_flat"}:
        fields.extend(("parameter_mode", "readout_mode"))
        if mode == "iso" or (left.get("iso") is not None and right.get("iso") is not None):
            fields.append("iso")
        if mode == "gain" or (left.get("gain") is not None and right.get("gain") is not None):
            fields.append("gain")
        if mode == "gain" or (left.get("offset") is not None and right.get("offset") is not None):
            fields.append("offset")
    if frame_type in {"dark", "dark_flat"}:
        fields.append("exposure_seconds")
    if frame_type == "flat":
        fields.extend(("optical_system_id", "filter_id"))
    for field in fields:
        a, b = left.get(field), right.get(field)
        if a is None or b is None:
            issue("METADATA_UNKNOWN", field, "unknown", a, b)
        elif a != b:
            issue("METADATA_MISMATCH", field, "conflict", a, b)
    for field in ("dimensions", "pixel_layout"):
        a, b = source.get(field), target.get(field)
        if a is None or b is None:
            issue("METADATA_UNKNOWN", field, "unknown", a, b)
        elif a != b:
            issue("METADATA_MISMATCH", field, "conflict", a, b)
    if frame_type in {"dark", "dark_flat"}:
        a, b = left.get("sensor_temperature_c"), right.get("sensor_temperature_c")
        if a is None or b is None:
            issue("METADATA_UNKNOWN", "sensor_temperature_c", "unknown", a, b)
        elif a != b:
            issue("TEMPERATURE_DIFFERENCE", "sensor_temperature_c", "warning", a, b)
    if frame_type == "flat":
        a = (source.get("equipment_snapshot") or {}).get("optical_system_id") or {}
        b = (target.get("equipment_snapshot") or {}).get("optical_system_id") or {}
        for field in ("effective_focal_length_mm",):
            left_value, right_value = a.get(field), b.get(field)
            if left_value is not None and right_value is not None and left_value != right_value:
                issue("OPTICAL_STATE_MISMATCH", field, "conflict", left_value, right_value)
        if "optical_accessory" in a and "optical_accessory" in b:
            left_accessory = (a["optical_accessory"] or {}).get("id")
            right_accessory = (b["optical_accessory"] or {}).get("id")
            if left_accessory != right_accessory:
                issue("OPTICAL_STATE_MISMATCH", "optical_accessory_id", "conflict", left_accessory, right_accessory)
    return issues
