"""Database-authoritative dataset mirrors, published after the primary commit."""

import json
import logging
import os
from pathlib import Path
from uuid import uuid4

from sqlalchemy import event, inspect, select

from astrophotoflow.modules.data.assets.calibration_status import dataset_calibration_summary
from astrophotoflow.modules.data.assets.models import Asset, ImageMetadataState
from astrophotoflow.modules.data.datasets.bindings import dataset_bindings
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetCalibration, DatasetMember
from astrophotoflow.modules.data.library.layout import (
    UNKNOWN_CAPTURE_TOKENS,
    capture_profile,
    capture_tokens,
    classification_directory,
    initialize_library,
    library_path,
    named_directory,
)

logger = logging.getLogger(__name__)
MANIFEST_FIELDS = {'library_directory', 'manifest_status', 'manifest_error'}


def _member_location(asset: Asset) -> dict:
    if asset.storage_mode == 'managed':
        location = Path(asset.storage_location).relative_to('library').as_posix()
        return {'path': location, 'storage_mode': 'managed'}
    return {'path': None, 'storage_mode': 'reference', 'source_location': asset.storage_location}


def dataset_manifest(session, dataset: Dataset) -> dict:
    members = session.scalars(
        select(Asset).join(DatasetMember, DatasetMember.asset_id == Asset.id)
        .where(DatasetMember.dataset_id == dataset.id).order_by(DatasetMember.position)
    ).all()
    pending = {}
    for purpose, binding in dataset_bindings(dataset).items():
        value = dict(binding) if binding is not None else None
        if value and value.get('kind') == 'asset':
            master = session.get(Asset, str(value['id']))
            if master:
                value.update(asset_id=master.id, name=master.name, **_member_location(master))
        pending[purpose] = value
    from astrophotoflow.modules.data.datasets.consistency import dataset_capture_diagnostics
    return {
        'capture_diagnostics': dataset_capture_diagnostics(session, dataset.id),
        'dataset_id': dataset.id, 'name': dataset.name, 'revision': dataset.revision,
        **dataset_calibration_summary(session, dataset.id).model_dump(mode='json'),
        'members': [
            {
                'asset_id': asset.id, 'name': asset.name, 'position': position,
                **_member_location(asset), 'content_hash': asset.content_hash,
                'byte_size': asset.byte_size, 'availability': asset.availability,
                'calibration_status': asset.calibration_status,
                'calibration_evidence': asset.calibration_evidence or {},
                'capture': capture_profile(asset),
            }
            for position, asset in enumerate(members)
        ],
        'pending_calibration': pending,
        'executed_processing': [
            {'asset_id': asset.id, 'calibration_evidence': (asset.scientific_metadata or {}).get('processing_calibration') or {},
             'processing': (asset.scientific_metadata or {}).get('export_provenance')}
            for asset in members
            if (asset.scientific_metadata or {}).get('processing_calibration')
            or (asset.scientific_metadata or {}).get('export_provenance')
        ],
    }


def _directory(session, settings, dataset: Dataset) -> str:
    if dataset.library_directory:
        return dataset.library_directory
    asset = session.scalar(
        select(Asset).join(DatasetMember, DatasetMember.asset_id == Asset.id)
        .where(DatasetMember.dataset_id == dataset.id).order_by(DatasetMember.position).limit(1)
    )
    if asset is None:
        parent = Path('Unclassified/Subframe/Unknown')
        label = dataset.name + '__' + UNKNOWN_CAPTURE_TOKENS
    else:
        parent = classification_directory(asset)
        parent = parent.parent / dataset_calibration_summary(session, dataset.id).calibration_status
        label = dataset.name + '__' + capture_tokens(asset)
    return named_directory(session, settings.data_dir, parent, label, dataset.id)


def publish_manifest(session, settings, dataset: Dataset) -> None:
    """Keep a committed database state usable when mirror publication fails."""
    temporary = None
    try:
        directory = _directory(session, settings, dataset)
        dataset.library_directory = directory
        destination = library_path(settings.data_dir, Path(directory) / 'dataset.json')
        temporary = destination.with_name('dataset.json.' + str(uuid4()) + '.tmp')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open('w', encoding='utf-8', newline='\n') as stream:
            json.dump(dataset_manifest(session, dataset), stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        dataset.manifest_status = 'ready'
        dataset.manifest_error = None
    except Exception as exc:
        logger.exception('Dataset manifest publication failed', extra={'dataset_id': dataset.id})
        dataset.manifest_status = 'failed'
        dataset.manifest_error = str(exc)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                logger.exception('Dataset manifest temporary file cleanup failed')


def synchronize_manifests(database, settings, dataset_ids: set[str], asset_ids: set[str]) -> None:
    # The writer lock serializes snapshots and publication, so an older callback
    # always publishes the latest committed state rather than overwriting it.
    with database.write_session() as session:
        affected = set(dataset_ids)
        affected.update(session.scalars(select(DatasetMember.dataset_id).where(DatasetMember.asset_id.in_(asset_ids))))
        affected.update(session.scalars(select(DatasetCalibration.dataset_id).where(DatasetCalibration.asset_id.in_(asset_ids))))
        for identity in sorted(affected):
            dataset = session.get(Dataset, identity)
            if dataset is not None:
                publish_manifest(session, settings, dataset)


def schedule_mirrors(session, *, dataset_ids=(), asset_ids=()) -> None:
    """Also track conditional SQL updates, which bypass ORM dirty tracking."""
    publisher = session.info.get('library_mirror_publisher')
    if publisher is None:
        return
    affected = set(dataset_ids)
    with session.no_autoflush:
        affected.update(session.scalars(select(DatasetMember.dataset_id).where(DatasetMember.asset_id.in_(asset_ids))))
        affected.update(session.scalars(select(DatasetCalibration.dataset_id).where(DatasetCalibration.asset_id.in_(asset_ids))))
        for identity in affected:
            dataset = session.get(Dataset, identity)
            if dataset is not None and dataset not in session.deleted:
                dataset.manifest_status = 'pending'
                dataset.manifest_error = None
    dirty = session.info.get('library_mirrors')
    if dirty is None:
        dirty = session.info['library_mirrors'] = (set(), set())
        session.info.setdefault('after_commit_callbacks', []).append(lambda: publisher(*dirty))
    dirty[0].update(affected)
    dirty[1].update(asset_ids)


def configure_library(database, settings) -> None:
    """Attach mirror tracking to this database's sessions, including imports."""
    initialize_library(settings.data_dir)

    def publish(dataset_ids, asset_ids):
        try:
            synchronize_manifests(database, settings, dataset_ids, asset_ids)
        except Exception:
            # The primary transaction already committed. Pending flags survive
            # and expose the need to rebuild instead of misreporting a rollback.
            logger.exception('Dataset mirror synchronization failed after commit')

    database.sessions.configure(info={'library_mirror_publisher': publish})

    def before_flush(session, _context, _instances):
        dataset_ids, asset_ids = set(), set()
        for row in (*session.new, *session.dirty, *session.deleted):
            if isinstance(row, Dataset):
                changed = {attribute.key for attribute in inspect(row).attrs if attribute.history.has_changes()}
                if row in session.new or changed - MANIFEST_FIELDS:
                    dataset_ids.add(row.id)
            elif isinstance(row, (DatasetMember, DatasetCalibration)):
                dataset_ids.add(row.dataset_id)
            elif isinstance(row, Asset):
                asset_ids.add(row.id)
            elif isinstance(row, ImageMetadataState):
                asset_ids.add(row.asset_id)
        if not dataset_ids and not asset_ids:
            return
        schedule_mirrors(session, dataset_ids=dataset_ids, asset_ids=asset_ids)

    event.listen(database.sessions, 'before_flush', before_flush)
