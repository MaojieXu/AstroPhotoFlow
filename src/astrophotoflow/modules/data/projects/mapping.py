'Typed project background and fixed-reference projections.'
from datetime import UTC
from uuid import UUID
from sqlalchemy.orm import Session
from astrophotoflow.contracts.projects import ProjectAssetReferenceOut, ProjectDatasetReferenceOut, ProjectOut
from astrophotoflow.modules.data.assets.mapping import asset_out
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.mapping import dataset_out
from astrophotoflow.modules.data.datasets.models import Dataset
from astrophotoflow.modules.data.media.links import project_asset_media_base
from astrophotoflow.modules.data.projects.models import Project, ProjectAssetReference, ProjectDatasetReference

def project_out(row: Project) -> ProjectOut:
    return ProjectOut(id=UUID(row.id), name=row.name, target_name=row.target_name, notes=row.notes, status=row.status, revision=row.revision, created_at=row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at.astimezone(UTC), updated_at=row.updated_at.replace(tzinfo=UTC) if row.updated_at.tzinfo is None else row.updated_at.astimezone(UTC))

def project_asset_reference_out(session: Session, reference: ProjectAssetReference, asset: Asset) -> ProjectAssetReferenceOut:
    return ProjectAssetReferenceOut(id=UUID(reference.id), project_id=UUID(reference.project_id),
        asset_id=UUID(reference.asset_id), view_base=project_asset_media_base(reference.project_id, reference.id),
        added_at=reference.added_at.replace(tzinfo=UTC) if reference.added_at.tzinfo is None else reference.added_at.astimezone(UTC),
        asset=asset_out(session, asset))


def project_dataset_reference_out(session: Session, reference: ProjectDatasetReference, facts=None) -> ProjectDatasetReferenceOut:
    dataset = session.get(Dataset, reference.dataset_id)
    if dataset is None:
        raise RuntimeError('Project dataset reference is missing.')
    data = dataset_out(session, dataset, facts.get(dataset.id) if facts else None)
    return ProjectDatasetReferenceOut(id=UUID(reference.id), project_id=UUID(reference.project_id),
        dataset_id=UUID(reference.dataset_id), base_revision=reference.base_revision, summary=data.summary,
        input_ready=data.input_ready, member_count=data.member_count, dataset=data,
        added_at=reference.added_at.replace(tzinfo=UTC) if reference.added_at.tzinfo is None else reference.added_at.astimezone(UTC))
