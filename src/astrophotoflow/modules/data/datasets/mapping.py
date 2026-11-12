"""Current dataset projections."""
from datetime import UTC
from uuid import UUID
from sqlalchemy.orm import Session
from astrophotoflow.contracts.datasets import DatasetMemberOut, DatasetOut
from astrophotoflow.modules.data.assets.calibration_status import dataset_calibration_summary
from astrophotoflow.modules.data.assets.queries import summarize_datasets
from astrophotoflow.modules.data.assets.mapping import asset_out
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.bindings import dataset_bindings
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember

def dataset_out(session: Session, row: Dataset, facts=None) -> DatasetOut:
    from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval
    from sqlalchemy import select
    from astrophotoflow.modules.data.datasets.consistency import dataset_capture_diagnostics
    from astrophotoflow.modules.data.projects.models import Project, ProjectDatasetReference
    projects = session.execute(select(Project.id, Project.name).join(ProjectDatasetReference, ProjectDatasetReference.project_id == Project.id).where(ProjectDatasetReference.dataset_id == row.id)).all()
    facts = facts or summarize_datasets(session, [row.id])[row.id]
    return DatasetOut(in_trash=session.get(LibraryEntryRemoval, ('dataset', row.id)) is not None, capture_diagnostics=dataset_capture_diagnostics(session, row.id), referencing_projects=[{'id': identity, 'name': name} for identity, name in projects], library_directory=row.library_directory, manifest_status=row.manifest_status, manifest_error=row.manifest_error, **dataset_calibration_summary(session, row.id).model_dump(), summary=facts.summary, exposure_summary=facts.exposure_summary, input_ready=facts.input_ready, id=UUID(row.id), name=row.name, notes=row.notes, status=row.status, revision=row.revision, member_count=facts.member_count, calibration=dataset_bindings(row), created_at=row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at.astimezone(UTC), updated_at=row.updated_at.replace(tzinfo=UTC) if row.updated_at.tzinfo is None else row.updated_at.astimezone(UTC))

def dataset_member_out(session: Session, member: DatasetMember, asset: Asset) -> DatasetMemberOut:
    if asset is None:
        raise RuntimeError('A dataset member points to a missing asset.')
    return DatasetMemberOut(id=UUID(member.id), dataset_id=UUID(member.dataset_id), asset_id=UUID(asset.id), position=member.position, relative_path=member.relative_path, asset=asset_out(session, asset))
