"""Explicit calibration writes, immutable receipts and paginated dependency reads."""

import hashlib
import json
from uuid import uuid4

from sqlalchemy import select

from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.calibration.checks import (
    inspect_calibration_bindings,
    validate_calibration_bindings,
    validate_target_structure,
)
from astrophotoflow.modules.data.calibration.choices import UNCONFIGURED, explicit_choices, incoming_bindings, patch_bindings
from astrophotoflow.modules.data.calibration.models import ImageCalibrationConfiguration, ImageCalibrationOperation
from astrophotoflow.modules.data.datasets.bindings import default_bindings, member_bindings
from astrophotoflow.modules.data.datasets.calibration import list_calibration_targets
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion
from astrophotoflow.modules.data.datasets.service import publish_dataset_members

MESSAGE = "关系已保存，尚未执行校准。"


def _json(value):
    normalized = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    return json.loads(json.dumps(normalized, default=str))


def operation_fingerprint(operation: str, payload: dict) -> str:
    return hashlib.sha256(json.dumps({"operation": operation, "payload": _json(payload)}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def replay_operation(session, request_id, operation: str, payload: dict):
    fingerprint = operation_fingerprint(operation, payload)
    previous = session.get(ImageCalibrationOperation, str(request_id))
    if previous:
        if previous.fingerprint != fingerprint:
            raise ApiError(409, "REQUEST_CONFLICT", "The request_id was already used with different content.")
        return previous.response
    return None


def save_operation(session, request_id, operation: str, payload: dict, result: dict) -> dict:
    receipt = {"request_id": str(request_id), "operation": operation, "result": _json(result), "message": MESSAGE}
    session.add(ImageCalibrationOperation(request_id=str(request_id), fingerprint=operation_fingerprint(operation, payload), response=receipt))
    session.flush()
    return receipt


def get_image_calibration_operation(session, request_id) -> dict:
    row = session.get(ImageCalibrationOperation, str(request_id))
    if row is None:
        raise not_found()
    return row.response


def require_image(session, asset_id, asset_version_id):
    asset = session.get(Asset, str(asset_id))
    version = session.get(AssetVersion, str(asset_version_id))
    if asset is None or asset.scope != "shared" or version is None or version.asset_id != asset.id:
        raise not_found()
    return asset, version


def latest_configuration(session, asset_version_id, binding_version_id=None):
    if binding_version_id is not None:
        row = session.get(ImageCalibrationConfiguration, str(binding_version_id))
        if row is None or row.asset_version_id != str(asset_version_id):
            raise not_found()
        return row
    return session.scalar(select(ImageCalibrationConfiguration).where(
        ImageCalibrationConfiguration.asset_version_id == str(asset_version_id),
    ).order_by(ImageCalibrationConfiguration.version_number.desc()).limit(1))


def get_image_calibration(session, asset_id, asset_version_id, binding_version_id=None) -> dict:
    from astrophotoflow.modules.data.calibration.readings import slot_details, target_details
    from astrophotoflow.modules.data.datasets.calibration import version_classification

    asset, version = require_image(session, asset_id, asset_version_id)
    row = latest_configuration(session, version.id, binding_version_id)
    bindings = explicit_choices(row.bindings if row else {}, complete=True)
    return {"asset_id": asset.id, "asset_version_id": version.id, "asset_revision": asset.revision,
            "binding_version_id": row.id if row else None, "version_number": row.version_number if row else None,
            "bindings": bindings, "slots": slot_details(bindings, target_details(session, [bindings]),
                standalone=True, frame_type=version_classification(asset, version).get('frame_type')), "message": MESSAGE}


def apply_import_calibration(session, asset_version_id: str, bindings: dict, *, accept_unknown: bool = False) -> dict:
    """Persist one immutable standalone configuration in the caller's import transaction."""
    version = session.get(AssetVersion, str(asset_version_id))
    if version is None:
        raise not_found()
    validate_calibration_bindings(session, [version.id], bindings, accept_unknown=accept_unknown)
    return _save_image_configuration(session, version, bindings)


def _save_image_configuration(session, version, bindings: dict) -> dict:
    latest = latest_configuration(session, version.id)
    if latest is not None and latest.bindings == bindings:
        return get_image_calibration(session, version.asset_id, version.id, latest.id)
    row = ImageCalibrationConfiguration(id=str(uuid4()), asset_version_id=version.id,
                                        version_number=latest.version_number + 1 if latest else 1, bindings=_json(bindings))
    session.add(row)
    session.flush()
    return get_image_calibration(session, version.asset_id, version.id, row.id)


def update_image_calibration(session, asset_id, asset_version_id, body) -> dict:
    payload = {"asset_id": str(asset_id), "asset_version_id": str(asset_version_id), **_json(body)}
    request_id = payload["request_id"]
    replay = replay_operation(session, request_id, "update_image", payload)
    if replay is not None:
        return replay
    asset, version = require_image(session, asset_id, asset_version_id)
    current = latest_configuration(session, version.id)
    if asset.revision != payload["expected_revision"] or (current.id if current else None) != payload["base_binding_version_id"]:
        raise ApiError(409, "REVISION_CONFLICT", "The image or calibration configuration changed; read it again.")
    bindings = patch_bindings(current.bindings if current else {}, payload["changes"])
    previous = current.bindings if current else {}
    changed = {slot: value for slot, value in bindings.items() if slot not in previous or previous[slot] != value}
    validate_calibration_bindings(session, [version.id], changed, context_bindings=bindings,
                                  accept_unknown=payload.get("accept_unknown", False))
    result = _save_image_configuration(session, version, bindings)
    if current is None or current.bindings != bindings:
        asset.revision += 1
    result["asset_revision"] = asset.revision
    return save_operation(session, request_id, "update_image", payload, result)


def _require_dataset(session, dataset_id, version_id):
    dataset = session.get(Dataset, str(dataset_id))
    version = session.get(DatasetVersion, str(version_id))
    if dataset is None or version is None or version.dataset_id != dataset.id:
        raise not_found()
    members = session.scalars(select(DatasetMember).where(DatasetMember.dataset_version_id == version.id).order_by(DatasetMember.position)).all()
    return dataset, version, members


def get_image_dataset_calibration(session, dataset_id, version_id, member_asset_version_ids=None, limit=50, offset=0, combination_key=None) -> dict:
    from astrophotoflow.modules.data.calibration.readings import dataset_calibration_page

    return dataset_calibration_page(session, dataset_id, version_id, member_asset_version_ids, limit, offset, combination_key)


def _select_members(members, ids):
    if ids is None:
        return members
    normalized = [str(value) for value in ids]
    if not normalized or len(normalized) != len(set(normalized)) or set(normalized) - {member.asset_version_id for member in members}:
        raise ApiError(422, "INVALID_REFERENCE", "Select unique members belonging to the fixed dataset version.")
    selected = set(normalized)
    return [member for member in members if member.asset_version_id in selected]


def consumer_bindings(session, consumer) -> list[tuple[str, dict]]:
    consumer = _json(consumer)
    if consumer["kind"] == "asset_version":
        _, version = require_image(session, consumer["asset_id"], consumer["asset_version_id"])
        row = latest_configuration(session, version.id, consumer.get("binding_version_id"))
        return [(version.id, row.bindings if row else {})]
    _, version, members = _require_dataset(session, consumer["dataset_id"], consumer["dataset_version_id"])
    defaults = default_bindings(version)
    return [(member.asset_version_id, {**defaults, **member_bindings(member)})
            for member in _select_members(members, consumer.get("member_asset_version_ids"))]


def check_calibration(session, consumer, proposal=None, limit=50, offset=0) -> dict:
    selected = consumer_bindings(session, consumer)
    consumer = _json(consumer)
    proposed = _json(proposal) if proposal is not None else {}
    member_changes = {item["asset_version_id"]: item["changes"] for item in proposed.get("member_changes", [])}
    if set(member_changes) - {identity for identity, _ in selected}:
        raise ApiError(422, "INVALID_REFERENCE", "Proposed changes must address selected members.")
    if consumer["kind"] == "asset_version" and member_changes:
        raise ApiError(422, "INVALID_REQUEST", "A standalone image does not have member overrides.")
    if consumer["kind"] == "dataset_version":
        _, fixed, members = _require_dataset(session, consumer["dataset_id"], consumer["dataset_version_id"])
        defaults = patch_bindings(default_bindings(fixed), proposed.get("changes", {}))
        overrides = {member.asset_version_id: member_bindings(member) for member in members}
    rows = []
    for identity, effective in selected:
        if consumer["kind"] == "dataset_version":
            override = patch_bindings(overrides[identity], member_changes.get(identity, {}), allow_inherit=True)
            bindings = {**defaults, **override}
            sources = {slot: "member_override" if slot in override else "dataset_default" for slot in bindings}
            for slot in proposed.get("changes", {}):
                if slot not in override:
                    sources[slot] = "proposal"
            for slot in member_changes.get(identity, {}):
                sources[slot] = "proposal"
        else:
            bindings = patch_bindings(effective, proposed.get("changes", {}))
            sources = {slot: "proposal" if slot in proposed.get("changes", {}) else "standalone" for slot in bindings}
        rows.extend(inspect_calibration_bindings(session, [identity], bindings, binding_sources=sources))
    conflicts = sum(row["state"] == "conflict" for row in rows)
    unknowns = sum(row["state"] == "unknown" for row in rows)
    return {"state": "conflict" if conflicts else "unknown" if unknowns else "compatible",
            "checked_bindings": len(rows), "conflict_count": conflicts, "unknown_count": unknowns,
            "master_required_count": sum(row["master_required"] for row in rows),
            "items": rows[offset:offset + limit], "total": len(rows), "limit": limit, "offset": offset}


def search_calibrations(session, slot, consumer=None, query=None) -> dict:
    query = _json(query) if query is not None else {}
    limit, offset = query.get("limit", 50), query.get("offset", 0)
    if query.get("target_kind") not in (None, "master"):
        return {"items": [], "total": 0, "limit": limit, "offset": offset}
    options = list_calibration_targets(session, limit=limit, offset=offset, frame_type=slot, q=query.get("text"))
    rows = []
    for option in options.items:
        target = option.target.model_dump(mode="json")
        row = {**option.model_dump(mode="json"), "target_kind": "master"}
        if consumer is not None:
            row["check"] = check_calibration(session, consumer, {"changes": {slot: {"mode": "target", "target": target}}}, limit=1)
        rows.append(row)
    return {"items": rows, "total": options.total, "limit": limit, "offset": offset}


def _guard_dataset(dataset, version, expected_revision, base_version_id):
    if dataset.revision != expected_revision or dataset.current_version_id != str(base_version_id) or version.id != str(base_version_id):
        raise ApiError(409, "REVISION_CONFLICT", "The dataset changed; read its revision and current version again.")


def _update_group(session, dataset_id, body, *, members: bool) -> dict:
    payload = {"dataset_id": str(dataset_id), **_json(body)}
    operation = "update_members" if members else "update_defaults"
    replay = replay_operation(session, payload["request_id"], operation, payload)
    if replay is not None:
        return replay
    dataset, version, rows = _require_dataset(session, dataset_id, payload["base_version_id"])
    _guard_dataset(dataset, version, payload["expected_revision"], payload["base_version_id"])
    defaults = default_bindings(version)
    overrides = {row.asset_version_id: member_bindings(row) for row in rows}
    previous_effective = {identity: {**defaults, **override} for identity, override in overrides.items()}
    if members:
        changes = payload["members"]
        ids = [item["asset_version_id"] for item in changes]
        if len(ids) != len(set(ids)) or set(ids) - set(overrides):
            raise ApiError(422, "INVALID_REFERENCE", "Member changes must address unique current members.")
        for item in changes:
            identity = item["asset_version_id"]
            overrides[identity] = patch_bindings(overrides[identity], item["changes"], allow_inherit=True)
    else:
        previous_defaults = defaults
        defaults = patch_bindings(defaults, payload["changes"])
        validate_target_structure(session, {slot: value for slot, value in defaults.items()
                                             if slot not in previous_defaults or previous_defaults[slot] != value})
    diagnostics = {"checked_bindings": 0, "unknown_count": 0, "master_required_count": 0}
    for identity, override in overrides.items():
        effective = {**defaults, **override}
        previous = previous_effective[identity]
        changed = {slot: value for slot, value in effective.items() if slot not in previous or previous[slot] != value}
        checked = validate_calibration_bindings(session, [identity], changed, context_bindings=effective,
                                               accept_unknown=payload.get("accept_unknown", False))
        for field in diagnostics:
            diagnostics[field] += checked[field]
    published = publish_dataset_members(session, dataset, [row.asset_version_id for row in rows], calibration_defaults=defaults, member_overrides=overrides)
    result = {"dataset_id": dataset.id, "dataset_version_id": published.id, "revision": dataset.revision, "diagnostics": diagnostics}
    return save_operation(session, payload["request_id"], operation, payload, result)


def update_image_dataset_calibration_defaults(session, dataset_id, body) -> dict:
    return _update_group(session, dataset_id, body, members=False)


def update_image_dataset_calibration_members(session, dataset_id, body) -> dict:
    return _update_group(session, dataset_id, body, members=True)


def search_image_calibration(session, body) -> dict:
    values = _json(body)
    return search_calibrations(session, values["slot"], values.get("consumer"), values.get("query"))


def check_image_calibration(session, body) -> dict:
    values = _json(body)
    return check_calibration(session, values["consumer"], values.get("proposal"), values.get("limit", 50), values.get("offset", 0))


def create_image_dataset(session, body) -> dict:
    payload = _json(body)
    replay = replay_operation(session, payload["request_id"], "create_dataset", payload)
    if replay is not None:
        return replay
    defaults = patch_bindings({}, payload.get("calibration_defaults", {}))
    validate_target_structure(session, defaults)
    ids, overrides = [], {}
    for item in payload["members"]:
        identity = str(item["asset_version_id"])
        if identity in ids:
            raise ApiError(422, "INVALID_REQUEST", "Dataset members must be unique.")
        ids.append(identity)
        overrides[identity] = patch_bindings({}, item.get("calibration", {}), allow_inherit=True)
        validate_calibration_bindings(session, [identity], {**defaults, **overrides[identity]}, accept_unknown=payload.get("accept_unknown", False))
    dataset = Dataset(id=str(uuid4()), name=payload["name"], notes=payload.get("notes"), status="active", revision=1)
    session.add(dataset)
    session.flush()
    version = publish_dataset_members(session, dataset, ids, calibration_defaults=defaults, member_overrides=overrides)
    dataset.revision = 1
    return save_operation(session, payload["request_id"], "create_dataset", payload,
                          {"dataset_id": dataset.id, "dataset_version_id": version.id, "revision": dataset.revision, "member_count": len(ids)})


def edit_image_dataset_members(session, dataset_id, body) -> dict:
    payload = {"dataset_id": str(dataset_id), **_json(body)}
    replay = replay_operation(session, payload["request_id"], "edit_members", payload)
    if replay is not None:
        return replay
    dataset, version, members = _require_dataset(session, dataset_id, payload["base_version_id"])
    _guard_dataset(dataset, version, payload["expected_revision"], payload["base_version_id"])
    old_ids = [member.asset_version_id for member in members]
    removed = [str(value) for value in payload.get("remove", [])]
    added = payload.get("add", [])
    added_ids = [str(item["asset_version_id"]) for item in added]
    if len(removed) != len(set(removed)) or set(removed) - set(old_ids) or len(added_ids) != len(set(added_ids)) or set(added_ids) & set(old_ids):
        raise ApiError(422, "INVALID_REFERENCE", "Remove current unique members and add only new unique members.")
    defaults = default_bindings(version)
    overrides = {member.asset_version_id: member_bindings(member) for member in members if member.asset_version_id not in removed}
    ids = [identity for identity in old_ids if identity not in set(removed)] + added_ids
    for item in added:
        identity = str(item["asset_version_id"])
        overrides[identity] = incoming_bindings(item.get("calibration"))
        validate_calibration_bindings(session, [identity], {**defaults, **overrides[identity]}, accept_unknown=payload.get("accept_unknown", False))
    published = publish_dataset_members(session, dataset, ids, calibration_defaults=defaults, member_overrides=overrides)
    return save_operation(session, payload["request_id"], "edit_members", payload,
                          {"dataset_id": dataset.id, "dataset_version_id": published.id, "revision": dataset.revision, "member_count": len(ids)})


def calibration_references(session, asset_version_ids: set[str], dataset_version_ids: set[str], excluded_asset_version_ids: set[str] = frozenset()) -> list[dict]:
    """Protect all immutable standalone revisions, not only the current one."""
    references = []
    for row in session.scalars(select(ImageCalibrationConfiguration)):
        if row.asset_version_id in excluded_asset_version_ids:
            continue
        for slot, target in row.bindings.items():
            if target is None or target == UNCONFIGURED:
                continue
            if target["id"] in asset_version_ids:
                references.append({"id": row.id, "kind": "calibration", "name": f"Standalone {row.asset_version_id} · {slot}", "version": row.version_number})
    return references
