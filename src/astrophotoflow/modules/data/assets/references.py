"""Validate asset visibility."""
from uuid import UUID
from sqlalchemy.orm import Session
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.assets.models import Asset

def asset_scope(session: Session, project_id: UUID | None, asset_id: UUID) -> Asset:
    asset = session.get(Asset, str(asset_id))
    if asset is None or (asset.scope != 'shared' and (project_id is None or asset.owner_project_id != str(project_id))):
        raise not_found()
    return asset


def require_referenceable(session: Session, entry_type: str, identity: UUID | str):
    from astrophotoflow.modules.data.datasets.models import Dataset
    from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval

    key = str(identity)
    row = session.get(Asset if entry_type == 'asset' else Dataset, key)
    if row is None or row.status != 'active' or session.get(LibraryEntryRemoval, (entry_type, key)) is not None:
        raise ApiError(409, 'REFERENCE_UNAVAILABLE', 'The selected object is unavailable or in trash.',
                       [{'path': entry_type + '_id', 'message': key}])
    return row
