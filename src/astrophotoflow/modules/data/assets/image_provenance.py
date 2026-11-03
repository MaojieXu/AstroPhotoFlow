"""Versioned declarations for externally made Masters, never execution facts."""

import json
from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from astrophotoflow.contracts.image_management import MasterProvenanceChanges
from astrophotoflow.core.errors import ApiError, invalid_reference, not_found
from astrophotoflow.modules.data.assets.models import (
    Asset,
    AssetVersion,
    MasterProvenanceReference,
    MasterProvenanceRevision,
)
from astrophotoflow.modules.data.datasets.calibration import validate_bindings, version_classification
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion


def _master(session: Session, asset_id: UUID | str, version_id: UUID | str):
    asset = session.get(Asset, str(asset_id))
    version = session.get(AssetVersion, str(version_id))
    if asset is None or asset.scope != "shared" or version is None or version.asset_id != asset.id:
        raise not_found()
    if version_classification(asset, version).get("frame_class") != "masterframe":
        raise invalid_reference("Master provenance is available only for Master image versions.")
    return asset, version


def _source_versions(session: Session, sources: list[dict] | None, master_version_id: str) -> tuple[list[AssetVersion], set[str], set[str]]:
    versions, assets, datasets = [], set(), set()
    for source in sources or []:
        if source["kind"] == "asset_version":
            version = session.get(AssetVersion, source["asset_version_id"])
            asset = session.get(Asset, version.asset_id) if version else None
            if asset is None or asset.scope != "shared" or asset.id != source["asset_id"]:
                raise invalid_reference("A Master source must identify its actual fixed image version.")
            selected = [version]
            assets.add(version.id)
        else:
            version = session.get(DatasetVersion, source["dataset_version_id"])
            dataset = session.get(Dataset, source["dataset_id"])
            if version is None or dataset is None or version.dataset_id != dataset.id:
                raise invalid_reference("A Master source must identify its actual fixed dataset version.")
            members = session.scalars(select(DatasetMember).where(DatasetMember.dataset_version_id == version.id)
                                      .order_by(DatasetMember.position)).all()
            ids = [member.asset_version_id for member in members]
            requested = source.get("member_asset_version_ids")
            if requested is not None and (len(set(requested)) != len(requested) or set(requested) - set(ids)):
                raise invalid_reference("Selected Master source members must belong to the fixed dataset version.")
            selected = [session.get(AssetVersion, identity) for identity in ids if requested is None or identity in requested]
            if not selected:
                raise invalid_reference("A Master source dataset selection must not be empty.")
            datasets.add(version.id)
            assets.update(item.id for item in selected)
        if any(item.id == master_version_id for item in selected):
            raise invalid_reference("A Master cannot declare itself as a source.")
        versions.extend(selected)
    return versions, assets, datasets


def _time_range(versions: list[AssetVersion]) -> dict:
    starts, ends, complete = [], [], bool(versions)
    for version in versions:
        times = ((version.capture_snapshot or {}).get("image_metadata") or {}).get("times", {})
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
    return {"start": min(starts, key=instant) if starts else None,
            "end": max(ends, key=instant) if ends else None, "complete": complete}


def get_master_provenance(session: Session, asset_id: UUID | str, version_id: UUID | str,
                            provenance_version_id: UUID | str | None = None) -> dict:
    asset, version = _master(session, asset_id, version_id)
    if provenance_version_id is not None:
        row = session.get(MasterProvenanceRevision, str(provenance_version_id))
        if row is None or row.asset_version_id != version.id:
            raise not_found()
    else:
        row = session.scalar(select(MasterProvenanceRevision).where(MasterProvenanceRevision.asset_version_id == version.id)
                             .order_by(MasterProvenanceRevision.revision.desc()).limit(1))
    return {"asset_id": asset.id, "asset_version_id": version.id, "asset_revision": asset.revision,
            "provenance_version_id": row.id if row else None, "revision": row.revision if row else 0,
            "source_kind": "user_declared", "declaration": deepcopy(row.data) if row else {},
            "platform_provenance": deepcopy((version.scientific_metadata or {}).get("export_provenance")),
            "source_time_range": deepcopy(row.source_time_range) if row else {"start": None, "end": None, "complete": False}}


def update_master_provenance(session: Session, asset_id: UUID | str, version_id: UUID | str,
                               expected_revision: int, changes: MasterProvenanceChanges) -> dict:
    asset, version = _master(session, asset_id, version_id)
    if asset.revision != expected_revision:
        raise ApiError(409, "REVISION_CONFLICT", "The image changed; read its current revision before saving provenance.")
    previous = session.scalar(select(MasterProvenanceRevision).where(MasterProvenanceRevision.asset_version_id == version.id)
                              .order_by(MasterProvenanceRevision.revision.desc()).limit(1))
    declaration = {**(previous.data if previous else {}), **changes.model_dump(mode="json", exclude_unset=True)}
    declaration = MasterProvenanceChanges.model_validate_json(json.dumps(declaration)).model_dump(mode="json", exclude_unset=True)
    source_versions, asset_refs, dataset_refs = _source_versions(session, declaration.get("sources"), version.id)
    applied = declaration.get("applied_calibrations") or {}
    validate_bindings(session, applied, {})
    for target in applied.values():
        if target["kind"] == "asset_version":
            if target["id"] == version.id:
                raise invalid_reference("A Master cannot be its own applied calibration.")
            asset_refs.add(target["id"])
        else:
            dataset_refs.add(target["id"])
    source_range = _time_range(source_versions)
    # An unchanged source declaration retains the historical observed source times.
    if previous and "sources" not in changes.model_fields_set:
        source_range = deepcopy(previous.source_time_range)
    result = session.execute(update(Asset).where(Asset.id == asset.id, Asset.revision == expected_revision)
                             .values(revision=expected_revision + 1))
    if result.rowcount != 1:
        raise ApiError(409, "REVISION_CONFLICT", "The image changed while saving provenance.")
    row = MasterProvenanceRevision(id=str(uuid4()), asset_version_id=version.id,
                                   revision=(previous.revision if previous else 0) + 1,
                                   asset_revision=expected_revision + 1, source_kind="user_declared", data=declaration,
                                   source_time_range=source_range, created_at=datetime.now(UTC))
    session.add(row)
    session.flush()
    for identity in asset_refs:
        session.add(MasterProvenanceReference(id=str(uuid4()), provenance_id=row.id, asset_version_id=identity))
    for identity in dataset_refs:
        session.add(MasterProvenanceReference(id=str(uuid4()), provenance_id=row.id, dataset_version_id=identity))
    session.flush()
    session.expire(asset)
    return get_master_provenance(session, asset.id, version.id)


def master_provenance_references(session: Session, asset_version_ids: set[str], dataset_version_ids: set[str],
                                  excluded_asset_version_ids: set[str] = frozenset()) -> list[dict]:
    """Historical declarations protect their fixed sources while their Master survives."""
    from sqlalchemy import or_
    rows = session.execute(select(MasterProvenanceReference, MasterProvenanceRevision, Asset).join(
        MasterProvenanceRevision, MasterProvenanceRevision.id == MasterProvenanceReference.provenance_id).join(
        AssetVersion, AssetVersion.id == MasterProvenanceRevision.asset_version_id).join(Asset, Asset.id == AssetVersion.asset_id)
        .where(or_(MasterProvenanceReference.asset_version_id.in_(asset_version_ids),
                   MasterProvenanceReference.dataset_version_id.in_(dataset_version_ids)),
               MasterProvenanceRevision.asset_version_id.not_in(excluded_asset_version_ids)))
    return [{"id": UUID(reference.id), "kind": "master_provenance", "name": f"{asset.name} · Master provenance",
             "version": provenance.revision} for reference, provenance, asset in rows]
