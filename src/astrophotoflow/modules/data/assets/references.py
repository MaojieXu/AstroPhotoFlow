"""Validate fixed content references within shared or project visibility."""

from uuid import UUID

from sqlalchemy.orm import Session

from astrophotoflow.core.errors import not_found
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion


def asset_version_scope(session: Session, project_id: UUID | None, version_id: UUID) -> tuple[Asset, AssetVersion]:
    version = session.get(AssetVersion, str(version_id))
    asset = session.get(Asset, version.asset_id) if version else None
    if asset is None or version is None:
        raise not_found()
    if asset.scope != "shared" and (project_id is None or asset.owner_project_id != str(project_id)):
        raise not_found()
    return asset, version
