from __future__ import annotations
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session
from astrophotoflow.contracts.assets import FitsHduPage, FitsHeaderOut, PreviewReference
from astrophotoflow.contracts.metadata import FrameClass
from astrophotoflow.contracts.projects import ProjectAssetReferenceOut, ProjectAssetReferencePage, ProjectDatasetReferenceCreate, ProjectDatasetReferenceOut, ProjectDatasetReferencePage, ProjectReferenceCreate, ProjectReferenceDelete, ProjectReferenceDeleteResult
from astrophotoflow.core.errors import ApiError, invalid_reference, not_found
from astrophotoflow.modules.data.assets.mapping import fits_hdu_out, header_out
from astrophotoflow.modules.data.assets.models import Asset, FitsHduMetadata
from astrophotoflow.modules.data.assets.queries import summarize_datasets
from astrophotoflow.modules.data.assets.references import asset_scope, require_referenceable
from astrophotoflow.modules.data.datasets.models import Dataset
from astrophotoflow.modules.data.projects.mapping import project_asset_reference_out, project_dataset_reference_out
from astrophotoflow.modules.data.projects.models import Project, ProjectAssetReference, ProjectDatasetReference
from astrophotoflow.modules.data.projects.service import advance_project_revision

def project_reference_filters(project_id: str, params: dict):
    scope = or_(Asset.scope == 'shared', and_(Asset.scope == 'project', Asset.owner_project_id == project_id))
    filters = [ProjectAssetReference.project_id == project_id, scope]
    if params.get('q'):
        filters.append(Asset.name_search_key.contains(params['q'].casefold(), autoescape=True))
    if params.get('role'):
        filters.append(Asset.role == params['role'])
    for key in ('frame_type', 'camera_id', 'optical_system_id', 'filter_id'):
        value = params.get(key)
        if value is not None:
            column = Asset.frame_type if key == 'frame_type' and params.get('frame_class') is not None else getattr(Asset, key)
            filters.append(column == (str(value) if isinstance(value, UUID) else value))
    if params.get('frame_class') is not None:
        filters.append(Asset.frame_class == params['frame_class'])
    if params.get('calibration_level') is not None:
        frame_class = 'masterframe' if params['calibration_level'] == 'master' else 'subframe'
        filters.extend((Asset.role == 'calibration', Asset.frame_class == frame_class))
    return filters

def list_project_assets(session: Session, project_id: UUID, limit: int=50, offset: int=0, sort_by: Literal['created_at', 'name']='created_at', order: Literal['asc', 'desc']='desc', q: str | None=None, role: Literal['raw', 'calibration', 'intermediate', 'final'] | None=None, frame_type: Literal['light', 'bias', 'dark', 'flat', 'dark_flat'] | None=None, calibration_level: Literal['individual', 'master'] | None=None, camera_id: UUID | None=None, optical_system_id: UUID | None=None, filter_id: UUID | None=None, frame_class: FrameClass | None=None) -> ProjectAssetReferencePage:
    project_key = str(project_id)
    if session.get(Project, project_key) is None:
        raise not_found()
    params = locals()
    filters = project_reference_filters(project_key, params)
    stmt = select(ProjectAssetReference, Asset).join(Asset, Asset.id == ProjectAssetReference.asset_id).where(*filters)
    total = session.scalar(select(func.count()).select_from(ProjectAssetReference).join(Asset, Asset.id == ProjectAssetReference.asset_id).where(*filters)) or 0
    column = Asset.name_search_key if sort_by == 'name' else Asset.created_at
    rows = session.execute(stmt.order_by(column.desc() if order == 'desc' else column.asc(), ProjectAssetReference.id.asc()).limit(limit).offset(offset)).all()
    return ProjectAssetReferencePage.model_validate({'items': [project_asset_reference_out(session, ref, asset) for ref, asset in rows], 'total': total, 'limit': limit, 'offset': offset})

def get_project_asset_reference(session: Session, project_id: UUID, reference_id: UUID) -> ProjectAssetReferenceOut:
    project_key = str(project_id)
    if session.get(Project, project_key) is None:
        raise not_found()
    row = session.execute(select(ProjectAssetReference, Asset).join(Asset, Asset.id == ProjectAssetReference.asset_id).where(ProjectAssetReference.id == str(reference_id), ProjectAssetReference.project_id == project_key, or_(Asset.scope == 'shared', and_(Asset.scope == 'project', Asset.owner_project_id == project_key)))).first()
    if row is None:
        raise not_found()
    return ProjectAssetReferenceOut.model_validate(project_asset_reference_out(session, row[0], row[1]))

def list_project_dataset_references(session: Session, project_id: UUID, limit: int=50, offset: int=0, sort_by: Literal['created_at', 'name']='created_at', order: Literal['asc', 'desc']='desc') -> ProjectDatasetReferencePage:
    project = session.get(Project, str(project_id))
    if project is None:
        raise not_found()
    total = session.scalar(select(func.count()).select_from(ProjectDatasetReference).where(ProjectDatasetReference.project_id == project.id)) or 0
    column = ProjectDatasetReference.added_at
    rows = session.scalars(select(ProjectDatasetReference).where(ProjectDatasetReference.project_id == project.id).order_by(column.desc() if order == 'desc' else column.asc(), ProjectDatasetReference.id.asc()).limit(limit).offset(offset)).all()
    facts = summarize_datasets(session, list({row.dataset_id for row in rows}))
    return ProjectDatasetReferencePage(items=[project_dataset_reference_out(session, row, facts) for row in rows], total=total, limit=limit, offset=offset)

def list_project_datasets(session: Session, project_id: UUID, limit: int=50, offset: int=0) -> ProjectDatasetReferencePage:
    return ProjectDatasetReferencePage.model_validate(list_project_dataset_references(session, project_id, limit, offset))

def add_project_dataset_reference(session: Session, project_id: UUID, body: ProjectDatasetReferenceCreate) -> ProjectDatasetReferenceOut:
    project_id_text = str(project_id)
    project = session.get(Project, project_id_text)
    if project is None or project.status != 'active':
        raise not_found()
    require_referenceable(session, 'dataset', body.dataset_id)
    dataset = session.get(Dataset, str(body.dataset_id))
    if dataset is None:
        raise invalid_reference('数据集版本不属于指定的数据集。', message_key='the_dataset_does_not_belong_to_the_specified_dataset')
    if dataset.status != 'active':
        raise invalid_reference('已归档数据集不能新建项目引用。', message_key='archived_datasets_cannot_be_added_to_projects')
    advance_project_revision(session, project.id, body.base_revision)
    existing = session.scalar(select(ProjectDatasetReference).where(ProjectDatasetReference.project_id == project_id_text, ProjectDatasetReference.dataset_id == dataset.id))
    if existing:
        raise ApiError(409, 'REVISION_CONFLICT', '项目已引用该数据集版本。', message_key='the_project_already_references_this_dataset')
    reference = ProjectDatasetReference(id=str(uuid4()), project_id=project_id_text, dataset_id=dataset.id, base_revision=body.base_revision + 1, added_at=datetime.now(UTC))
    session.add(reference)
    session.flush()
    session.expire_all()
    return ProjectDatasetReferenceOut.model_validate(project_dataset_reference_out(session, session.get(ProjectDatasetReference, reference.id)))

def get_project_dataset_reference(session: Session, project_id: UUID, reference_id: UUID) -> ProjectDatasetReferenceOut:
    project = session.get(Project, str(project_id))
    row = session.get(ProjectDatasetReference, str(reference_id))
    if project is None or row is None or row.project_id != project.id:
        raise not_found()
    return ProjectDatasetReferenceOut.model_validate(project_dataset_reference_out(session, row))

def remove_project_dataset_reference(session: Session, project_id: UUID, reference_id: UUID, body: ProjectReferenceDelete) -> ProjectReferenceDeleteResult:
    project_id_text, reference_id_text = (str(project_id), str(reference_id))
    project = session.get(Project, project_id_text)
    reference = session.get(ProjectDatasetReference, reference_id_text)
    if project is None or reference is None or reference.project_id != project_id_text:
        raise not_found()
    advance_project_revision(session, project.id, body.base_revision)
    session.delete(reference)
    session.flush()
    return ProjectReferenceDeleteResult.model_validate({'deleted_id': reference_id_text, 'revision': body.base_revision + 1})

def add_project_asset_reference(session: Session, project_id: UUID, body: ProjectReferenceCreate) -> ProjectAssetReferenceOut:
    project_id_text = str(project_id)
    project = session.get(Project, project_id_text)
    if project is None or project.status != 'active':
        raise not_found()
    require_referenceable(session, 'asset', body.asset_id)
    asset = asset_scope(session, project_id, body.asset_id)
    if asset.status != 'active':
        raise invalid_reference('已归档资产不能新建项目引用。', message_key='archived_assets_cannot_be_added_to_projects')
    if session.scalar(select(ProjectAssetReference.id).where(ProjectAssetReference.project_id == project_id_text, ProjectAssetReference.asset_id == asset.id)):
        raise ApiError(409, 'REVISION_CONFLICT', '项目已引用该资产版本。', message_key='the_project_already_references_this_asset')
    advance_project_revision(session, project.id, body.base_revision)
    reference = ProjectAssetReference(id=str(uuid4()), project_id=project_id_text, asset_id=asset.id, added_at=datetime.now(UTC))
    session.add(reference)
    session.flush()
    session.expire_all()
    return ProjectAssetReferenceOut.model_validate(project_asset_reference_out(session, session.get(ProjectAssetReference, reference.id), asset))

def remove_project_asset_reference(session: Session, project_id: UUID, reference_id: UUID, body: ProjectReferenceDelete) -> ProjectReferenceDeleteResult:
    project_id_text, reference_id_text = (str(project_id), str(reference_id))
    project = session.get(Project, project_id_text)
    reference = session.get(ProjectAssetReference, reference_id_text)
    if project is None or reference is None or reference.project_id != project_id_text:
        raise not_found()
    advance_project_revision(session, project.id, body.base_revision)
    session.delete(reference)
    session.flush()
    return ProjectReferenceDeleteResult.model_validate({'deleted_id': reference_id_text, 'revision': body.base_revision + 1})

def _require_project_reference(session, project_id: UUID, reference_id: UUID):
    reference = session.get(ProjectAssetReference, str(reference_id))
    if reference is None or reference.project_id != str(project_id):
        raise not_found()
    asset = asset_scope(session, project_id, UUID(reference.asset_id))
    return asset

def list_project_reference_hdus(session: Session, project_id: UUID, reference_id: UUID, limit: int=200, offset: int=0) -> FitsHduPage:
    asset = _require_project_reference(session, project_id, reference_id)
    total = session.scalar(select(func.count()).select_from(FitsHduMetadata).where(FitsHduMetadata.asset_id == asset.id)) or 0
    rows = session.scalars(select(FitsHduMetadata).where(FitsHduMetadata.asset_id == asset.id).order_by(FitsHduMetadata.hdu_index).limit(limit).offset(offset)).all()
    return FitsHduPage.model_validate({'items': [fits_hdu_out(row).model_dump() for row in rows], 'total': total, 'limit': limit, 'offset': offset})

def get_project_reference_header(session: Session, project_id: UUID, reference_id: UUID, hdu_index: int) -> FitsHeaderOut:
    asset = _require_project_reference(session, project_id, reference_id)
    hdu = session.scalar(select(FitsHduMetadata).where(FitsHduMetadata.asset_id == asset.id, FitsHduMetadata.hdu_index == hdu_index))
    if hdu is None:
        raise not_found()
    return FitsHeaderOut.model_validate(header_out(asset, hdu).model_dump())

def get_project_preview_reference(session: Session, project_id: UUID, reference_id: UUID) -> PreviewReference:
    asset = _require_project_reference(session, project_id, reference_id)
    selected = session.scalar(select(FitsHduMetadata.hdu_index).where(FitsHduMetadata.asset_id == asset.id, FitsHduMetadata.is_selected.is_(True)))
    if selected is None and (asset.scientific_metadata or {}).get('format') in {'image', 'raw', 'xisf', 'video'}:
        selected = 0
    return PreviewReference(asset_id=UUID(asset.id), hdu_index=selected)
