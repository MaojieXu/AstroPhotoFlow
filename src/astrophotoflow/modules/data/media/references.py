from __future__ import annotations
from uuid import UUID
from sqlalchemy.orm import Session
from astrophotoflow.core.errors import not_found
from astrophotoflow.modules.data.assets.references import asset_scope
from astrophotoflow.modules.data.projects.models import ProjectAssetReference


def library_preview_asset(session: Session, asset_id: UUID) -> str:
    return asset_scope(session, None, asset_id).id


def project_preview_asset(session: Session, project_id: UUID, reference_id: UUID) -> str:
    reference = session.get(ProjectAssetReference, str(reference_id))
    if reference is None or reference.project_id != str(project_id):
        raise not_found()
    asset_scope(session, project_id, UUID(reference.asset_id))
    return reference.asset_id
