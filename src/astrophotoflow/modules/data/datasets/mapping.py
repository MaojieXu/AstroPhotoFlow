from astrophotoflow.modules.data.assets.queries import empty_version_summary, summarize_dataset_versions
from astrophotoflow.modules.data.assets.summaries import VersionSummaryFacts

"""Fixed dataset DTOs assembled in member order without transport dependencies."""

from datetime import UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from astrophotoflow.contracts.datasets import DatasetMemberOut, DatasetOut, DatasetVersionOut, DatasetVersionSummary
from astrophotoflow.modules.data.assets.exposure import summarize_dataset_exposures
from astrophotoflow.modules.data.assets.mapping import asset_out, asset_version_out
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.calibration.rows import member_calibration_projections
from astrophotoflow.modules.data.datasets.bindings import default_bindings, member_bindings
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion


def dataset_out(session: Session, row: Dataset, facts: VersionSummaryFacts | None = None) -> DatasetOut:
    if facts is None:
        facts = summarize_dataset_versions(session, [row.current_version_id])[row.current_version_id] if row.current_version_id else empty_version_summary()
    return DatasetOut(summary=facts.summary, exposure_summary=facts.exposure_summary, input_ready=facts.input_ready, current_version_number=facts.version_number, id=UUID(row.id), name=row.name, notes=row.notes, status=row.status, revision=row.revision,
                      current_version_id=UUID(row.current_version_id) if row.current_version_id else None, member_count=facts.member_count,
                      created_at=row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at.astimezone(UTC),
                      updated_at=row.updated_at.replace(tzinfo=UTC) if row.updated_at.tzinfo is None else row.updated_at.astimezone(UTC))


def dataset_version_out(session: Session, row: DatasetVersion) -> DatasetVersionOut:
    members = session.execute(select(DatasetMember, AssetVersion, Asset).outerjoin(
        AssetVersion, AssetVersion.id == DatasetMember.asset_version_id).outerjoin(Asset, Asset.id == AssetVersion.asset_id)
        .where(DatasetMember.dataset_version_id == row.id).order_by(DatasetMember.position)).all()
    if any(version is None or asset is None for _, version, asset in members):
        raise RuntimeError("A fixed dataset member points to missing content.")
    calibrations = member_calibration_projections(session, members)
    result = [dataset_member_out(session, member, version, asset, calibration_projection=calibrations[member.id])
        for member, version, asset in members]
    return DatasetVersionOut(id=UUID(row.id), dataset_id=UUID(row.dataset_id), version_number=row.version_number,
                             created_at=row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at.astimezone(UTC),
                             members=result, calibration_defaults=default_bindings(row),
                             exposure_summary=summarize_dataset_exposures(session, [row.id], frozen=True)[row.id])


def dataset_member_out(session: Session, member: DatasetMember, version: AssetVersion | None, asset: Asset | None, *, calibration_projection=None) -> DatasetMemberOut:
    if asset is None or version is None:
        raise RuntimeError("A fixed dataset member points to missing content.")
    return DatasetMemberOut(
        id=UUID(member.id), dataset_version_id=UUID(member.dataset_version_id), asset_version_id=UUID(version.id),
        position=member.position, relative_path=member.relative_path,
        calibration_overrides=member_bindings(member), calibration_projection=calibration_projection,
        asset=asset_out(session, asset), version=asset_version_out(version),
    )


def dataset_version_summary(session: Session, row: DatasetVersion, exposure=None) -> DatasetVersionSummary:
    return DatasetVersionSummary(id=UUID(row.id), dataset_id=UUID(row.dataset_id), version_number=row.version_number,
        created_at=row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at.astimezone(UTC),
        calibration_defaults=default_bindings(row),
        exposure_summary=exposure if exposure is not None else summarize_dataset_exposures(session, [row.id], frozen=True)[row.id])
