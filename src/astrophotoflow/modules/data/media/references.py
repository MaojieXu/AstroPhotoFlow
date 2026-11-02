from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from astrophotoflow.core.errors import not_found
from astrophotoflow.modules.data.assets.references import asset_version_scope
from astrophotoflow.modules.data.projects.models import ProjectAssetReference


def library_preview_version(session: Session, asset_id: UUID, version_id: UUID) -> str:
    asset, version = asset_version_scope(session, None, version_id)
    if asset.id != str(asset_id):
        raise not_found()
    return version.id

def project_preview_version(session: Session, project_id: UUID, reference_id: UUID) -> str:
    reference = session.get(ProjectAssetReference, str(reference_id))
    if reference is None or reference.project_id != str(project_id):
        raise not_found()
    asset_version_scope(session, project_id, UUID(reference.asset_version_id))
    return reference.asset_version_id
