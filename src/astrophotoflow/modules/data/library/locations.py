"""Read actual managed positions and explicitly rebuild a current mirror."""

import os
from pathlib import Path

from sqlalchemy import select

from astrophotoflow.contracts.library import LibraryDirectoryOpened, LibraryFileLocation, LibraryLocationOut
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember
from astrophotoflow.modules.data.library.layout import library_path
from astrophotoflow.modules.data.library.manifests import publish_manifest


def _registered_path(settings, asset: Asset) -> Path:
    if asset.storage_mode == 'managed':
        try:
            relative = Path(asset.storage_location).relative_to('library')
        except ValueError as exc:
            raise ApiError(409, 'FILE_SCOPE_INVALID', 'Managed originals must belong to the library.', message_key='managed_originals_must_belong_to_the_library') from exc
        return library_path(settings.data_dir, relative)
    try:
        prefix, root_id, relative = asset.storage_location.split('/', 2)
        configured = next(root for root in settings.import_roots if root.id == root_id)
        root = configured.path.resolve()
        path = (root / relative).resolve()
        if prefix != 'roots' or not path.is_relative_to(root):
            raise ValueError('Reference path escapes its configured root.')
        return path
    except (ValueError, StopIteration) as exc:
        raise ApiError(422, 'SOURCE_UNAVAILABLE', 'The registered directory is currently unavailable.', message_key='the_registered_directory_is_currently_unavailable') from exc


def library_location(session, settings, entry_type: str, entry_id) -> LibraryLocationOut:
    row = session.get(Asset if entry_type == 'asset' else Dataset, str(entry_id))
    if row is None or isinstance(row, Asset) and row.scope != 'shared':
        raise not_found()
    if entry_type == 'asset':
        assets = [row]
        directory = str(_registered_path(settings, row).parent)
        manifest_path = None
    else:
        assets = session.scalars(
            select(Asset).join(DatasetMember, DatasetMember.asset_id == Asset.id)
            .where(DatasetMember.dataset_id == row.id).order_by(DatasetMember.position)
        ).all()
        directory = str(library_path(settings.data_dir, row.library_directory)) if row.library_directory else None
        manifest_path = str(library_path(settings.data_dir, Path(row.library_directory) / 'dataset.json')) if directory else None
    files = []
    for asset in assets:
        path = _registered_path(settings, asset)
        relative = path.relative_to((settings.data_dir / 'library').resolve()).as_posix() if asset.storage_mode == 'managed' else None
        files.append(LibraryFileLocation(
            asset_id=asset.id, storage_mode=asset.storage_mode, availability=asset.availability if path.is_file() else 'missing',
            path=str(path), library_relative_path=relative,
            processing_calibration=(asset.scientific_metadata or {}).get('processing_calibration'),
            processing_provenance=(asset.scientific_metadata or {}).get('export_provenance'),
            calibration_status=asset.calibration_status, calibration_evidence=asset.calibration_evidence or {},
        ))
    return LibraryLocationOut(
        entry_type=entry_type, id=row.id, revision=row.revision, directory=directory, files=files,
        manifest_path=manifest_path, manifest_status=(row.manifest_status if manifest_path and Path(manifest_path).is_file() else 'pending') if entry_type == 'dataset' else None,
        manifest_error=row.manifest_error if entry_type == 'dataset' else None,
    )


def rebuild_dataset_manifest(session, settings, dataset_id, base_revision: int) -> LibraryLocationOut:
    dataset = session.get(Dataset, str(dataset_id))
    if dataset is None:
        raise not_found()
    if dataset.revision != base_revision:
        raise ApiError(409, 'REVISION_CONFLICT', 'The dataset changed; read its current revision.', message_key='the_dataset_changed_read_its_current_revision')
    publish_manifest(session, settings, dataset)
    session.flush()
    return library_location(session, settings, 'dataset', dataset.id)


def open_library_directory(session, settings, entry_type: str, entry_id) -> LibraryDirectoryOpened:
    location = library_location(session, settings, entry_type, entry_id)
    if location.directory is None or not Path(location.directory).is_dir():
        raise ApiError(409, 'SOURCE_UNAVAILABLE', 'The registered directory is currently unavailable.', message_key='the_registered_directory_is_currently_unavailable')
    if os.name != 'nt':
        raise ApiError(422, 'UNSUPPORTED_PLATFORM', 'Opening a local directory requires Windows.', message_key='opening_a_local_directory_requires_windows')
    os.startfile(location.directory)
    return LibraryDirectoryOpened(directory=location.directory)
