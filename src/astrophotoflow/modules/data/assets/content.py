"""Observe the registered original without replacing its content."""
from uuid import UUID
from astrophotoflow.contracts.assets import AssetContentObservation
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.core.localization import exception_error, workspace_locale
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.science.files import hash_file, resolve_storage_path


def observe_asset_content(database: Database, settings: Settings, asset_id: UUID) -> AssetContentObservation:
    identity = str(asset_id)
    with database.read_session() as session:
        asset = session.get(Asset, identity)
        if asset is None or asset.scope != 'shared':
            raise not_found()
        if not asset.content_hash or asset.byte_size is None:
            raise ApiError(422, 'SOURCE_UNAVAILABLE', 'The registered original is not ready.', message_key='the_registered_original_is_not_ready')
        revision, mode, location, stored_hash, stored_size = asset.revision, asset.storage_mode, asset.storage_location, asset.content_hash, asset.byte_size
    observed_hash, size, mtime, error = None, None, None, None
    try:
        observed_hash, size, mtime = hash_file(resolve_storage_path(settings, mode, location))
        state = 'unchanged' if observed_hash == stored_hash and size == stored_size else 'changed'
    except ApiError as exc:
        if exc.code != 'SOURCE_UNAVAILABLE':
            raise
        state = 'missing'
        error = exception_error(workspace_locale(settings.workspace), exc, code='SOURCE_UNAVAILABLE', message_key='the_asset_source_is_currently_inaccessible')
    with database.write_session() as session:
        asset = session.get(Asset, identity)
        if asset is None or asset.revision != revision or asset.content_hash != stored_hash or asset.storage_location != location:
            raise ApiError(409, 'REVISION_CONFLICT', 'The asset changed; read it again.', message_key='the_asset_changed_read_it_again')
        asset.availability = {'unchanged': 'available', 'changed': 'changed', 'missing': 'missing'}[state]
    return AssetContentObservation(asset_id=UUID(identity), base_revision=revision, storage_mode=mode,
        stored_hash=stored_hash, state=state, observed_hash=observed_hash, observed_byte_size=size,
        observed_mtime_ns=str(mtime) if mtime is not None else None, error=error)
