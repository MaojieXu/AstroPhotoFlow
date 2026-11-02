from astrophotoflow.modules.data.assets.queries import summarize_dataset_versions
from astrophotoflow.modules.data.assets.summaries import VersionSummaryFacts

"""Typed project background and fixed-reference projections."""

from datetime import UTC
from uuid import UUID

from sqlalchemy.orm import Session

from astrophotoflow.contracts.projects import ProjectAssetReferenceOut, ProjectDatasetReferenceOut, ProjectOut
from astrophotoflow.modules.data.assets.mapping import asset_out, asset_version_out
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.datasets.mapping import dataset_out, dataset_version_summary
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetVersion
from astrophotoflow.modules.data.media.links import project_asset_media_base
from astrophotoflow.modules.data.projects.models import Project, ProjectAssetReference, ProjectDatasetReference


def project_out(row: Project) -> ProjectOut:
    return ProjectOut(id=UUID(row.id), name=row.name, target_name=row.target_name, notes=row.notes,
                      status=row.status, revision=row.revision,
                      created_at=row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at.astimezone(UTC),
                      updated_at=row.updated_at.replace(tzinfo=UTC) if row.updated_at.tzinfo is None else row.updated_at.astimezone(UTC))


def project_asset_reference_out(session: Session, reference: ProjectAssetReference, asset: Asset, version: AssetVersion) -> ProjectAssetReferenceOut:
    return ProjectAssetReferenceOut(id=UUID(reference.id), project_id=UUID(reference.project_id),
                                    asset_version_id=UUID(reference.asset_version_id),
                                    view_base=project_asset_media_base(reference.project_id, reference.id),
                                    added_at=reference.added_at.replace(tzinfo=UTC) if reference.added_at.tzinfo is None else reference.added_at.astimezone(UTC),
                                    asset=asset_out(session, asset), version=asset_version_out(version))


def project_dataset_reference_out(session: Session, reference: ProjectDatasetReference, facts: dict[str, VersionSummaryFacts] | None = None) -> ProjectDatasetReferenceOut:
    dataset = session.get(Dataset, reference.dataset_id)
    version = session.get(DatasetVersion, reference.dataset_version_id)
    if dataset is None or version is None or version.dataset_id != dataset.id:
        raise RuntimeError("A fixed project dataset reference points to missing content.")
    if facts is None:
        facts = summarize_dataset_versions(session, list({value for value in (version.id, dataset.current_version_id) if value}))
    fixed = facts[version.id]
    current = facts[dataset.current_version_id] if dataset.current_version_id else None
    return ProjectDatasetReferenceOut(summary=fixed.summary, input_ready=fixed.input_ready, member_count=fixed.member_count, id=UUID(reference.id), project_id=UUID(reference.project_id),
                                      dataset_id=UUID(reference.dataset_id), dataset_version_id=UUID(reference.dataset_version_id),
                                      base_revision=reference.base_revision,
                                      added_at=reference.added_at.replace(tzinfo=UTC) if reference.added_at.tzinfo is None else reference.added_at.astimezone(UTC),
                                      dataset=dataset_out(session, dataset, current), version=dataset_version_summary(version))
