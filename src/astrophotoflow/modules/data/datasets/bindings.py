"""Project calibration relations into the public sparse binding map."""

from astrophotoflow.modules.data.datasets.models import DatasetCalibration, DatasetMember, DatasetVersion, MemberCalibration


def _bindings(rows) -> dict:
    return {row.frame_type: {"mode": "unconfigured"} if row.state == "unconfigured" else None if row.disabled else {
        "kind": "asset_version",
        "id": row.asset_version_id,
    } for row in rows}


def default_bindings(version: DatasetVersion) -> dict:
    return _bindings(version.defaults)


def member_bindings(member: DatasetMember) -> dict:
    return _bindings(member.overrides)


def set_default_bindings(version: DatasetVersion, bindings: dict) -> None:
    version.defaults = [DatasetCalibration(
        dataset_version_id=version.id, frame_type=frame_type, **_target_columns(target),
    ) for frame_type, target in bindings.items()]


def set_member_bindings(member: DatasetMember, bindings: dict) -> None:
    member.overrides = [MemberCalibration(
        member_id=member.id, frame_type=frame_type, **_target_columns(target),
    ) for frame_type, target in bindings.items()]


def _target_columns(target) -> dict:
    unconfigured = bool(target and target.get("mode") == "unconfigured")
    return {
        "state": "unconfigured" if unconfigured else "disabled" if target is None else "target",
        "disabled": target is None or unconfigured,
        "asset_version_id": target["id"] if target and target.get("kind") == "asset_version" else None,
    }
