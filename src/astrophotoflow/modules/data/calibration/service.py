"""Explicit calibration writes, immutable receipts and paginated dependency reads."""

import hashlib
import json
from uuid import uuid4
from sqlalchemy import select
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.calibration.checks import (
    inspect_calibration_bindings,
    validate_calibration_bindings,
    validate_target_structure,
)
from astrophotoflow.modules.data.calibration.choices import explicit_choices, patch_bindings
from astrophotoflow.modules.data.calibration.models import ImageCalibrationOperation
from astrophotoflow.modules.data.datasets.bindings import dataset_bindings
from astrophotoflow.modules.data.datasets.calibration import list_calibration_targets, validate_dataset_members
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember
from astrophotoflow.modules.data.datasets.service import publish_dataset_members

MESSAGE = "关系已保存，尚未执行校准。"

from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval


def _json(value):
    normalized = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    return json.loads(json.dumps(normalized, default=str))


def operation_fingerprint(operation: str, payload: dict) -> str:
    return hashlib.sha256(
        json.dumps({"operation": operation, "payload": _json(payload)}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def replay_operation(session, request_id, operation: str, payload: dict):
    fingerprint = operation_fingerprint(operation, payload)
    previous = session.get(ImageCalibrationOperation, str(request_id))
    if previous:
        if previous.fingerprint != fingerprint:
            raise ApiError(
                409,
                "REQUEST_CONFLICT",
                "The request_id was already used with different content.",
                message_key="the_request_id_was_already_used_with_different_content",
            )
        return previous.response
    return None


def save_operation(session, request_id, operation: str, payload: dict, result: dict) -> dict:
    result = dict(result)
    if result.get('dataset_id'):
        from astrophotoflow.modules.data.datasets.consistency import dataset_capture_diagnostics
        result['capture_diagnostics'] = dataset_capture_diagnostics(session, str(result['dataset_id']))
    receipt = {"request_id": str(request_id), "operation": operation, "result": _json(result), "message": MESSAGE}
    session.add(
        ImageCalibrationOperation(request_id=str(request_id), fingerprint=operation_fingerprint(operation, payload), response=receipt)
    )
    session.flush()
    return receipt


def get_image_calibration_operation(session, request_id) -> dict:
    row = session.get(ImageCalibrationOperation, str(request_id))
    if row is None or 'result' not in row.response:
        raise not_found()
    return row.response


def require_image(session, asset_id):
    asset = session.get(Asset, str(asset_id))
    if asset is None or asset.scope != "shared":
        raise not_found()
    return asset


def get_image_calibration(session, asset_id) -> dict:
    from astrophotoflow.modules.data.calibration.readings import slot_details, target_details

    asset = require_image(session, asset_id)
    bindings = explicit_choices(asset.calibration or {}, complete=True)
    return {
        "diagnostics": inspect_calibration_bindings(session, [asset.id], asset.calibration or {}),
        "asset_id": asset.id,
        "asset_revision": asset.revision,
        "bindings": bindings,
        "slots": slot_details(bindings, target_details(session, [bindings]), standalone=True, frame_type=asset.frame_type),
        "message": MESSAGE,
    }


def apply_import_calibration(session, asset_id: str, bindings: dict, *, accept_unknown: bool = False) -> dict:
    asset = require_image(session, asset_id)
    validate_calibration_bindings(session, [asset.id], bindings, accept_unknown=accept_unknown)
    asset.calibration = _json(bindings)
    session.flush()
    return get_image_calibration(session, asset.id)


def update_image_calibration(session, asset_id, body) -> dict:
    payload = {"asset_id": str(asset_id), **_json(body)}
    replay = replay_operation(session, payload["request_id"], "update_image", payload)
    if replay is not None:
        return replay
    from astrophotoflow.modules.data.assets.references import require_referenceable
    asset = require_referenceable(session, 'asset', asset_id)
    if asset.revision != payload["expected_revision"]:
        raise ApiError(409, "REVISION_CONFLICT", "The image changed; read it again.", message_key='the_image_changed_read_it_again')
    previous = asset.calibration or {}
    bindings = patch_bindings(previous, payload["changes"])
    changed = {slot: value for slot, value in bindings.items() if slot not in previous or previous[slot] != value}
    validate_calibration_bindings(
        session, [asset.id], changed, context_bindings=bindings, accept_unknown=payload.get("accept_unknown", False)
    )
    if bindings != previous:
        asset.calibration = _json(bindings)
        asset.revision += 1
    session.flush()
    return save_operation(session, payload["request_id"], "update_image", payload, get_image_calibration(session, asset.id))


def _require_dataset(session, dataset_id):
    if session.get(LibraryEntryRemoval, ("dataset", str(dataset_id))) is not None:
        raise not_found()
    from astrophotoflow.modules.data.assets.references import require_referenceable
    dataset = require_referenceable(session, 'dataset', dataset_id)
    members = session.scalars(select(DatasetMember).where(DatasetMember.dataset_id == dataset.id).order_by(DatasetMember.position)).all()
    return dataset, members


def get_image_dataset_calibration(session, dataset_id) -> dict:
    from astrophotoflow.modules.data.calibration.readings import read_dataset_calibration

    return read_dataset_calibration(session, dataset_id)


def _select_members(members, ids):
    if ids is None:
        return members
    normalized = [str(value) for value in ids]
    if not normalized or len(normalized) != len(set(normalized)) or set(normalized) - {member.asset_id for member in members}:
        raise ApiError(
            422,
            "INVALID_REFERENCE",
            "Select unique members belonging to the fixed dataset version.",
            message_key="select_unique_members_belonging_to_the_fixed_dataset",
        )
    selected = set(normalized)
    return [member for member in members if member.asset_id in selected]


def consumer_bindings(session, consumer) -> list[tuple[str, dict]]:
    consumer = _json(consumer)
    if consumer["kind"] == "asset":
        asset = require_image(session, consumer["asset_id"])
        return [(asset.id, asset.calibration or {})]
    dataset, members = _require_dataset(session, consumer["dataset_id"])
    return [(member.asset_id, dataset_bindings(dataset)) for member in _select_members(members, consumer.get("member_asset_ids"))]


def check_calibration(session, consumer, proposal=None, limit=50, offset=0) -> dict:
    selected = consumer_bindings(session, consumer)
    consumer = _json(consumer)
    proposed = _json(proposal) if proposal is not None else {}
    changes = proposed.get("changes", {})
    origin = "dataset" if consumer["kind"] == "dataset" else "standalone"
    rows = []
    for identity, effective in selected:
        bindings = patch_bindings(effective, changes)
        sources = {slot: "proposal" if slot in changes else origin for slot in bindings}
        rows.extend(inspect_calibration_bindings(session, [identity], bindings, binding_sources=sources))
    conflicts = sum((row["state"] == "conflict" for row in rows))
    unknowns = sum((row["state"] == "unknown" for row in rows))
    warnings = sum(any(item["severity"] == "warning" for item in row["diagnostics"]) for row in rows)
    return {
        "state": "conflict" if conflicts else "unknown" if unknowns else "warning" if warnings else "compatible",
        "checked_bindings": len(rows),
        "conflict_count": conflicts,
        "unknown_count": unknowns,
        "warning_count": warnings,
        "master_required_count": sum((row["master_required"] for row in rows)),
        "items": rows[offset : offset + limit],
        "total": len(rows),
        "limit": limit,
        "offset": offset,
    }


def search_calibrations(session, slot, consumer=None, query=None) -> dict:
    query = _json(query) if query is not None else {}
    limit, offset = (query.get("limit", 50), query.get("offset", 0))
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


def _guard_dataset(dataset, expected_revision):
    if dataset.revision != expected_revision:
        raise ApiError(409, "REVISION_CONFLICT", "The dataset changed; read it again.", message_key='the_dataset_changed_read_it_again')


def update_image_dataset_calibration(session, dataset_id, body) -> dict:
    payload = {"dataset_id": str(dataset_id), **_json(body)}
    operation = "update_dataset_calibration"
    replay = replay_operation(session, payload["request_id"], operation, payload)
    if replay is not None:
        return replay
    dataset, rows = _require_dataset(session, dataset_id)
    _guard_dataset(dataset, payload["expected_revision"])
    previous = dataset_bindings(dataset)
    bindings = patch_bindings(previous, payload["changes"])
    changed = {slot: value for slot, value in bindings.items() if slot not in previous or previous[slot] != value}
    validate_target_structure(session, changed)
    ids = [row.asset_id for row in rows]
    diagnostics = validate_calibration_bindings(
        session, ids, changed, context_bindings=bindings, accept_unknown=payload.get("accept_unknown", False)
    )
    published = publish_dataset_members(session, dataset, ids, calibration=bindings)
    result = {
        "dataset_id": published.id,
        "revision": dataset.revision,
        "diagnostics": {key: diagnostics[key] for key in ("checked_bindings", "unknown_count", "warning_count", "items", "master_required_count")},
    }
    return save_operation(session, payload["request_id"], operation, payload, result)


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
    bindings = patch_bindings({}, payload.get("calibration", {}))
    validate_target_structure(session, bindings)
    ids = [str(item["asset_id"]) for item in payload["members"]]
    validate_dataset_members(session, ids)
    validate_calibration_bindings(session, ids, bindings, accept_unknown=payload.get("accept_unknown", False))
    dataset = Dataset(id=str(uuid4()), name=payload["name"], notes=payload.get("notes"), status="active", revision=1)
    session.add(dataset)
    session.flush()
    version = publish_dataset_members(session, dataset, ids, calibration=bindings)
    dataset.revision = 1
    result = {"dataset_id": version.id, "revision": dataset.revision, "member_count": len(ids)}
    if payload.get("project_id") is not None:
        from astrophotoflow.contracts.projects import ProjectDatasetReferenceCreate
        from astrophotoflow.modules.data.projects.references import add_project_dataset_reference
        add_project_dataset_reference(session, payload["project_id"], ProjectDatasetReferenceCreate(
            base_revision=payload["project_base_revision"], dataset_id=dataset.id,
        ))
        result["project_revision"] = payload["project_base_revision"] + 1
    return save_operation(
        session,
        payload["request_id"],
        "create_dataset",
        payload,
        result,
    )


def edit_image_dataset_members(session, dataset_id, body) -> dict:
    payload = {"dataset_id": str(dataset_id), **_json(body)}
    replay = replay_operation(session, payload["request_id"], "edit_members", payload)
    if replay is not None:
        return replay
    dataset, members = _require_dataset(session, dataset_id)
    _guard_dataset(dataset, payload["expected_revision"])
    old_ids = [member.asset_id for member in members]
    removed = [str(value) for value in payload.get("remove", [])]
    added = payload.get("add", [])
    added_ids = [str(item["asset_id"]) for item in added]
    if (
        len(removed) != len(set(removed))
        or set(removed) - set(old_ids)
        or len(added_ids) != len(set(added_ids))
        or set(added_ids) & set(old_ids)
    ):
        raise ApiError(
            422,
            "INVALID_REFERENCE",
            "Remove current unique members and add only new unique members.",
            message_key="remove_current_unique_members_and_add_only_new_unique_members",
        )
    bindings = dataset_bindings(dataset)
    ids = [identity for identity in old_ids if identity not in set(removed)] + added_ids
    validate_dataset_members(session, added_ids, dataset.id)
    validate_calibration_bindings(session, added_ids, bindings, accept_unknown=payload.get("accept_unknown", False))
    published = publish_dataset_members(session, dataset, ids)
    return save_operation(
        session,
        payload["request_id"],
        "edit_members",
        payload,
        {"dataset_id": published.id, "revision": dataset.revision, "member_count": len(ids)},
    )


def calibration_references(session, asset_ids: set[str], dataset_ids: set[str], excluded_asset_ids: set[str] = frozenset()) -> list[dict]:
    from uuid import NAMESPACE_URL, uuid5

    references = []
    for asset in session.scalars(select(Asset).where(Asset.id.not_in(excluded_asset_ids))):
        for slot, target in (asset.calibration or {}).items():
            if target and target.get("kind") == "asset" and target["id"] in asset_ids:
                references.append(
                    {"id": uuid5(NAMESPACE_URL, f"calibration:{asset.id}:{slot}"), "kind": "calibration", "name": f"{asset.name} · {slot}"}
                )
    return references
