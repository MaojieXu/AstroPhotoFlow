"""Versioned declarations for externally made Masters, never execution facts."""

import json
from copy import deepcopy
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from astrophotoflow.contracts.image_management import MasterProvenanceChanges
from astrophotoflow.core.errors import ApiError, invalid_reference, not_found
from astrophotoflow.modules.data.assets.models import Asset, MasterProvenanceReference
from astrophotoflow.modules.data.datasets.calibration import validate_bindings
from astrophotoflow.modules.data.assets.metadata import asset_classification


def _master(session: Session, asset_id: UUID | str) -> Asset:
    asset = session.get(Asset, str(asset_id))
    if asset is None or asset.scope != "shared":
        raise not_found()
    if (asset_classification(asset) or {}).get("frame_class") != "masterframe":
        raise invalid_reference("Master provenance is available only for Master images.")
    return asset


def _source_assets(
    session: Session, sources: list[dict] | None, master_id: str, *, refresh_members: bool = True
) -> tuple[list[Asset], set[str], set[str]]:
    from astrophotoflow.modules.data.assets.references import require_referenceable
    selected_assets, asset_ids, dataset_ids = [], set(), set()
    for source in sources or []:
        if source["kind"] == "asset":
            asset = session.get(Asset, str(source["asset_id"]))
            if asset is None or asset.scope != "shared":
                raise invalid_reference("A Master source must identify an existing image.")
            if refresh_members:
                require_referenceable(session, 'asset', asset.id)
            selected = [asset]
        else:
            if refresh_members:
                from astrophotoflow.modules.data.science.inputs import current_dataset_members

                dataset, members = current_dataset_members(session, source["dataset_id"], source.get("member_asset_ids"))
                identities = [member.asset_id for member in members]
                dataset_identity = dataset.id
            else:
                identities = source.get("member_asset_ids") or []
                dataset_identity = str(source["dataset_id"])
            selected = [session.get(Asset, identity) for identity in identities]
            if not selected or any(asset is None or asset.scope != "shared" for asset in selected):
                raise invalid_reference("A Master source contains a missing image.")
            if refresh_members:
                for asset in selected:
                    require_referenceable(session, 'asset', asset.id)
            source["member_asset_ids"] = [asset.id for asset in selected]
            dataset_ids.add(dataset_identity)
        if any(asset.id == master_id for asset in selected):
            raise invalid_reference("A Master cannot declare itself as a source.")
        selected_assets.extend(selected)
        asset_ids.update(asset.id for asset in selected)
    return selected_assets, asset_ids, dataset_ids


def _time_range(assets: list[Asset]) -> dict:
    starts, ends, complete = ([], [], bool(assets))
    for asset in assets:
        times = ((asset.capture_snapshot or {}).get("image_metadata") or {}).get("times", {})
        start = times.get("capture_start") or {}
        end = times.get("capture_end") or {}
        if not start.get("utc") or not end.get("utc"):
            complete = False
        if start.get("utc"):
            starts.append(start)
        if end.get("utc"):
            ends.append(end)

    def instant(value):
        return datetime.fromisoformat(value["utc"])

    return {"start": min(starts, key=instant) if starts else None, "end": max(ends, key=instant) if ends else None, "complete": complete}


def get_master_provenance(session: Session, asset_id: UUID | str) -> dict:
    asset = _master(session, asset_id)
    stored = asset.master_provenance or {}
    return {
        "asset_id": asset.id,
        "asset_revision": asset.revision,
        "revision": asset.revision,
        "source_kind": "user_declared",
        "declaration": deepcopy(stored.get("declaration", {})),
        "platform_provenance": deepcopy((asset.scientific_metadata or {}).get("export_provenance")),
        "source_time_range": deepcopy(stored.get("source_time_range", {"start": None, "end": None, "complete": False})),
    }


def update_master_provenance(session: Session, asset_id: UUID | str, expected_revision: int, changes: MasterProvenanceChanges) -> dict:
    from astrophotoflow.modules.data.assets.references import require_referenceable
    require_referenceable(session, 'asset', asset_id)
    asset = _master(session, asset_id)
    if asset.revision != expected_revision:
        raise ApiError(409, "REVISION_CONFLICT", "The image changed; read it again.", message_key='the_image_changed_read_it_again')
    previous = asset.master_provenance or {}
    declaration = {**previous.get("declaration", {}), **changes.model_dump(mode="json", exclude_unset=True)}
    declaration = MasterProvenanceChanges.model_validate_json(json.dumps(declaration)).model_dump(mode="json", exclude_unset=True)
    sources, asset_refs, dataset_refs = _source_assets(
        session, declaration.get("sources"), asset.id, refresh_members="sources" in changes.model_fields_set
    )
    applied = declaration.get("applied_calibrations") or {}
    validate_bindings(session, applied, {})
    for target in applied.values():
        if target["id"] == asset.id:
            raise invalid_reference("A Master cannot be its own applied calibration.")
        asset_refs.add(target["id"])
    source_range = (
        _time_range(sources) if "sources" in changes.model_fields_set else previous.get("source_time_range", _time_range(sources))
    )
    session.execute(delete(MasterProvenanceReference).where(MasterProvenanceReference.asset_id == asset.id))
    for identity in asset_refs:
        session.add(MasterProvenanceReference(id=str(uuid4()), asset_id=asset.id, source_asset_id=identity))
    for identity in dataset_refs:
        session.add(MasterProvenanceReference(id=str(uuid4()), asset_id=asset.id, dataset_id=identity))
    asset.master_provenance = {"declaration": declaration, "source_time_range": source_range}
    asset.revision += 1
    session.flush()
    return get_master_provenance(session, asset.id)


def master_provenance_references(
    session: Session, asset_ids: set[str], dataset_ids: set[str], excluded_asset_ids: set[str] = frozenset()
) -> list[dict]:
    from sqlalchemy import or_

    rows = session.execute(
        select(MasterProvenanceReference, Asset)
        .join(Asset, Asset.id == MasterProvenanceReference.asset_id)
        .where(
            or_(MasterProvenanceReference.source_asset_id.in_(asset_ids), MasterProvenanceReference.dataset_id.in_(dataset_ids)),
            MasterProvenanceReference.asset_id.not_in(excluded_asset_ids),
        )
    )
    return [
        {"id": UUID(reference.id), "kind": "master_provenance", "name": f"{asset.name} · Master provenance"} for reference, asset in rows
    ]
