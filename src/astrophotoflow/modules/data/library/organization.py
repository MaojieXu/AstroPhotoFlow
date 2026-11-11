"""Explicit, preflighted layout changes with current per-file receipts."""

import hashlib
import json
import logging
import os
from copy import deepcopy
from pathlib import Path

from sqlalchemy import select

from astrophotoflow.contracts.library import LibraryFileMove, LibraryOrganizePlan, LibraryOrganizeReceipt
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.assets.calibration_status import dataset_calibration_summary
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.calibration.models import ImageCalibrationOperation
from astrophotoflow.modules.data.calibration.service import operation_fingerprint, replay_operation
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
from astrophotoflow.modules.data.library.layout import (
    UNKNOWN_CAPTURE_TOKENS,
    capture_tokens,
    classification_directory,
    library_path,
    named_directory,
)
from astrophotoflow.modules.data.library.manifests import schedule_mirrors
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.science.files import hash_file, read_hash_and_copy, try_hardlink

OPERATION = 'organize_library'
logger = logging.getLogger(__name__)


def _relative(asset: Asset) -> Path:
    try:
        return Path(asset.storage_location).relative_to('library')
    except ValueError as exc:
        raise ApiError(409, 'FILE_SCOPE_INVALID', 'Managed originals must belong to the library.', message_key='managed_originals_must_belong_to_the_library') from exc


def _available_for_move(path: Path) -> None:
    if os.name != 'nt':
        return
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    # Request delete access while allowing other readers, writers and movers.
    handle = kernel.CreateFileW('\\\\?\\' + str(path), 0x10000, 7, None, 3, 0x80, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    kernel.CloseHandle(handle)


def _root(session, body):
    row = session.get(Asset if body.entry_type == 'asset' else Dataset, str(body.id))
    if row is None or isinstance(row, Asset) and row.scope != 'shared':
        raise not_found()
    if row.revision != body.base_revision:
        raise ApiError(409, 'REVISION_CONFLICT', 'Read the current revision before organizing directories.', message_key='read_the_current_revision_before_organizing_directories')
    return row


def plan_library_organization(session, settings, body) -> LibraryOrganizePlan:
    row = _root(session, body)
    blockers = []
    if isinstance(row, Dataset):
        source_directory = row.library_directory
        representative = session.scalar(
            select(Asset).join(DatasetMember, DatasetMember.asset_id == Asset.id)
            .where(DatasetMember.dataset_id == row.id).order_by(DatasetMember.position).limit(1)
        )
        parent = classification_directory(representative).parent if representative else Path('Unclassified/Subframe')
        parent /= dataset_calibration_summary(session, row.id).calibration_status
        label = row.name + '__' + (capture_tokens(representative) if representative else UNKNOWN_CAPTURE_TOKENS)
        assets = [asset for asset in session.scalars(select(Asset).where(Asset.storage_mode == 'managed'))
                  if source_directory and _relative(asset).parent.as_posix() == source_directory]
    else:
        source_directory = _relative(row).parent.as_posix() if row.storage_mode == 'managed' else None
        parent = classification_directory(row)
        label = row.name
        if row.frame_class == 'masterframe':
            parent /= capture_tokens(row)
        else:
            label += '__' + capture_tokens(row)
        assets = [row] if row.storage_mode == 'managed' else []
        if row.storage_mode != 'managed':
            blockers.append('Reference originals stay in their external source directory.')
    destination = named_directory(session, settings.data_dir, parent, label, row.id, current=source_directory)
    ids = [asset.id for asset in assets]
    active_imports = session.scalars(
        select(AssetTask.id).join(AssetTaskItem, AssetTaskItem.task_id == AssetTask.id)
        .where(AssetTaskItem.asset_id.in_(ids), AssetTask.status.in_({'queued', 'running', 'cancelling', 'interrupted'})).distinct()
    ).all()
    blockers.extend(f'Import task {identity} owns a selected original.' for identity in active_imports)
    if isinstance(row, Dataset):
        target_import = session.scalar(select(AssetTask.id).where(
            AssetTask.target_dataset_id == row.id, AssetTask.status.in_({'queued', 'running', 'cancelling', 'interrupted'})
        ).limit(1))
        if target_import and target_import not in active_imports:
            blockers.append(f'Import task {target_import} targets this dataset.')
    preview_ids = session.scalars(select(Preview.id).where(Preview.asset_id.in_(ids), Preview.status == 'generating')).all()
    blockers.extend(f'Preview {identity} is reading a selected original.' for identity in preview_ids)
    moves = []
    targets = set()
    for asset in assets:
        source = _relative(asset)
        target = Path(destination) / source.name
        move = LibraryFileMove(asset_id=asset.id, revision=asset.revision, content_hash=asset.content_hash,
                               byte_size=asset.byte_size, source=source.as_posix(), destination=target.as_posix())
        try:
            path = library_path(settings.data_dir, source)
            target_path = library_path(settings.data_dir, target)
            if target != source and (target_path.exists() or str(target_path).casefold() in targets):
                raise ApiError(409, 'PATH_CONFLICT', 'A destination file is already present.', message_key='a_destination_file_is_already_present')
            if asset.availability != 'available' or not asset.content_hash or asset.byte_size is None:
                raise ApiError(409, 'SOURCE_UNAVAILABLE', 'The original is not ready for movement.', message_key='the_original_is_not_ready_for_movement')
            observed, size, _ = hash_file(path)
            if (observed, size) != (asset.content_hash, asset.byte_size):
                raise ApiError(409, 'SOURCE_CHANGED', 'The original bytes changed; restore them before organizing.', message_key='the_original_bytes_changed_restore_them_before_organizing')
            _available_for_move(path)
            targets.add(str(target_path).casefold())
        except (ApiError, OSError) as exc:
            move.error = str(exc)
            blockers.append(f'{asset.id}: {exc}')
        moves.append(move)
    payload = {
        'entry_type': body.entry_type, 'id': str(body.id), 'base_revision': body.base_revision,
        'source_directory': source_directory, 'destination_directory': destination,
        'moves': [move.model_dump(mode='json') for move in moves], 'blockers': blockers,
    }
    token = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return LibraryOrganizePlan.model_validate({**payload, 'token': token})


def get_library_organization(session, request_id) -> LibraryOrganizeReceipt:
    row = session.get(ImageCalibrationOperation, str(request_id))
    if row is None or row.response.get('operation') != OPERATION:
        raise not_found()
    return LibraryOrganizeReceipt.model_validate(row.response)


def find_library_organization(session, body) -> LibraryOrganizeReceipt | None:
    previous = replay_operation(session, body.request_id, OPERATION, body.model_dump(mode='json'))
    return LibraryOrganizeReceipt.model_validate(previous) if previous is not None else None


def _save_receipt(session, receipt: LibraryOrganizeReceipt) -> None:
    session.get(ImageCalibrationOperation, str(receipt.request_id)).response = receipt.model_dump(mode='json')


def _clean_duplicate(settings, move, *, registered_path: str) -> None:
    source = library_path(settings.data_dir, move.source)
    target = library_path(settings.data_dir, move.destination)
    obsolete, retained = (source, target) if registered_path == move.destination else (target, source)
    if obsolete == retained or not obsolete.exists():
        return
    if not retained.exists():
        raise ApiError(409, 'FILE_SCOPE_INVALID', 'The duplicate no longer shares the registered original identity.', message_key='the_duplicate_no_longer_shares_the_registered_original_identity')
    observed, size, _ = hash_file(retained)
    if (observed, size) != (move.content_hash, move.byte_size):
        raise ApiError(409, 'SOURCE_CHANGED', 'The original changed before duplicate cleanup.', message_key='the_original_changed_before_duplicate_cleanup')
    if not os.path.samefile(obsolete, retained) and hash_file(obsolete)[:2] != (move.content_hash, move.byte_size):
        raise ApiError(409, 'FILE_SCOPE_INVALID', 'The duplicate no longer shares the registered original identity.', message_key='the_duplicate_no_longer_shares_the_registered_original_identity')
    obsolete.unlink()


def _move_part(settings, move, request_id) -> Path:
    relative = Path(move.destination)
    return library_path(settings.data_dir, relative.with_name(f'.apf-organize-{request_id}-{move.asset_id}.part'))


def _establish_entry(settings, source, target, move, request_id) -> None:
    if try_hardlink(source, target):
        return
    # Filesystems without hard links use the import copy/hash primitive. The
    # old registered path remains readable until the new location commits.
    part = _move_part(settings, move, request_id)
    try:
        observed, size = read_hash_and_copy(source, part, lambda: False)
        if (observed, size) != (move.content_hash, move.byte_size):
            raise ApiError(409, 'SOURCE_CHANGED', 'Original bytes changed after preflight.', message_key='original_bytes_changed_after_preflight')
        if target.exists():
            raise ApiError(409, 'PATH_CONFLICT', 'A destination file is already present.', message_key='a_destination_file_is_already_present')
        os.rename(part, target)
    finally:
        part.unlink(missing_ok=True)


def _move_file(database, settings, receipt, index) -> None:
    move = receipt.plan.moves[index]
    if move.source == move.destination:
        move.state = 'completed'
        return
    source = library_path(settings.data_dir, move.source)
    target = library_path(settings.data_dir, move.destination)
    created = False
    try:
        with database.write_session() as session:
            asset = session.get(Asset, str(move.asset_id))
            if asset is None or asset.revision != move.revision or _relative(asset).as_posix() != move.source:
                raise ApiError(409, 'REVISION_CONFLICT', 'The original changed after preflight.', message_key='the_original_changed_after_preflight')
            _root(session, receipt.plan)
            if session.scalar(select(Preview.id).where(Preview.asset_id == asset.id, Preview.status == 'generating').limit(1)):
                raise ApiError(409, 'LIBRARY_BUSY', 'A preview started reading this original after preflight.', message_key='a_preview_started_reading_this_original_after_preflight')
            if session.scalar(select(AssetTask.id).join(AssetTaskItem, AssetTaskItem.task_id == AssetTask.id).where(
                AssetTaskItem.asset_id == asset.id, AssetTask.status.in_({'queued', 'running', 'cancelling', 'interrupted'})
            ).limit(1)):
                raise ApiError(409, 'LIBRARY_BUSY', 'An import owns this original after preflight.', message_key='an_import_owns_this_original_after_preflight')
            _available_for_move(source)
            observed, size, _ = hash_file(source)
            if (observed, size) != (move.content_hash, move.byte_size):
                raise ApiError(409, 'SOURCE_CHANGED', 'Original bytes changed after preflight.', message_key='original_bytes_changed_after_preflight')
            target.parent.mkdir(parents=True, exist_ok=True)
            # Both names refer to identical bytes until the database commits.
            # A crash leaves the previously registered original readable.
            _establish_entry(settings, source, target, move, receipt.request_id)
            created = True
            asset.storage_location = (Path('library') / move.destination).as_posix()
            asset.revision += 1
            move.state = 'cleanup_pending'
            _save_receipt(session, receipt)
        _clean_duplicate(settings, move, registered_path=move.destination)
        move.state = 'completed'
    except (ApiError, OSError) as exc:
        move.error = str(exc)
        with database.read_session() as session:
            asset = session.get(Asset, str(move.asset_id))
            registered = _relative(asset).as_posix() if asset else None
        if registered == move.destination:
            move.state = 'cleanup_pending'
        else:
            move.state = 'failed'
            if created and target.exists() and source.exists():
                try:
                    _clean_duplicate(settings, move, registered_path=move.source)
                except (ApiError, OSError) as cleanup:
                    move.error += f' Cleanup pending: {cleanup}'


def _remove_old_manifest(session, settings, receipt) -> None:
    plan = receipt.plan
    if plan.entry_type != 'dataset' or not plan.source_directory or plan.source_directory == plan.destination_directory:
        return
    dataset = session.get(Dataset, str(plan.id))
    if dataset is None or dataset.library_directory != plan.destination_directory or dataset.manifest_status != 'ready':
        return
    previous = library_path(settings.data_dir, Path(plan.source_directory) / 'dataset.json')
    try:
        if previous.exists():
            if json.loads(previous.read_text(encoding='utf-8')).get('dataset_id') != str(plan.id):
                raise ApiError(409, 'FILE_SCOPE_INVALID', 'The old manifest belongs to another dataset.', message_key='the_old_manifest_belongs_to_another_dataset')
            previous.unlink()
        if previous.parent.is_dir() and not any(previous.parent.iterdir()):
            previous.parent.rmdir()
    except (ApiError, OSError, ValueError) as exc:
        receipt.error = f'Old manifest cleanup pending: {exc}'
        receipt.state = 'partial'


def organize_library(database, settings, body, *, blockers=()) -> LibraryOrganizeReceipt:
    payload = body.model_dump(mode='json')
    with database.write_session() as session:
        previous = find_library_organization(session, body)
        if previous is not None:
            return previous
        plan = plan_library_organization(session, settings, body)
        if plan.token != body.plan_token:
            raise ApiError(409, 'REVISION_CONFLICT', 'The layout changed; read a fresh organization plan.', message_key='the_layout_changed_read_a_fresh_organization_plan')
        if plan.blockers or blockers:
            raise ApiError(409, 'LIBRARY_BUSY', '\n'.join([*plan.blockers, *blockers]), message_key='library_organization_busy', message_params={'details': '\n'.join([*plan.blockers, *blockers])})
        selected = {str(move.asset_id) for move in plan.moves}
        for operation in session.scalars(select(ImageCalibrationOperation).where(
            ImageCalibrationOperation.response['operation'].as_string() == OPERATION,
            ImageCalibrationOperation.response['state'].as_string() == 'running',
        )):
            other = LibraryOrganizeReceipt.model_validate(operation.response)
            if (other.plan.entry_type, other.plan.id) == (plan.entry_type, plan.id) or selected.intersection(str(move.asset_id) for move in other.plan.moves):
                raise ApiError(409, 'LIBRARY_BUSY', 'Another directory organization owns the selected originals.', message_key='another_directory_organization_owns_the_selected_originals')
        receipt = LibraryOrganizeReceipt(request_id=body.request_id, state='running', plan=plan)
        session.add(ImageCalibrationOperation(request_id=str(body.request_id),
                    fingerprint=operation_fingerprint(OPERATION, payload), response=receipt.model_dump(mode='json')))
    try:
        for index in range(len(receipt.plan.moves)):
            _move_file(database, settings, receipt, index)
            with database.write_session() as session:
                _save_receipt(session, receipt)
        with database.write_session() as session:
            if receipt.plan.entry_type == 'dataset':
                try:
                    dataset = _root(session, receipt.plan)
                    dataset.library_directory = receipt.plan.destination_directory
                    dataset.revision += 1
                    schedule_mirrors(session, dataset_ids={dataset.id})
                except ApiError as exc:
                    receipt.error = str(exc)
            receipt.state = 'partial' if receipt.error or any(move.state != 'completed' for move in receipt.plan.moves) else 'completed'
            _save_receipt(session, receipt)
        with database.write_session() as session:
            _remove_old_manifest(session, settings, receipt)
            _save_receipt(session, receipt)
        return receipt
    except Exception as exc:
        receipt.state = 'interrupted'
        receipt.error = str(exc)
        try:
            with database.write_session() as session:
                _save_receipt(session, receipt)
        except Exception:
            logger.exception('Directory organization receipt could not record interruption')
        raise


def recover_library_organization(database, settings) -> None:
    """Reconcile only duplicate names from committed organization receipts."""
    with database.read_session() as session:
        receipts = [deepcopy(row.response) for row in session.scalars(select(ImageCalibrationOperation).where(
            ImageCalibrationOperation.response['operation'].as_string() == OPERATION,
            ImageCalibrationOperation.response['state'].as_string().in_(['running', 'partial']),
        ))]
    for value in receipts:
        receipt = LibraryOrganizeReceipt.model_validate(value)
        for move in receipt.plan.moves:
            with database.read_session() as session:
                asset = session.get(Asset, str(move.asset_id))
                registered = _relative(asset).as_posix() if asset else None
            if registered not in {move.source, move.destination}:
                move.error = 'The asset has another registered location; inspect it before retrying.'
                continue
            try:
                _move_part(settings, move, receipt.request_id).unlink(missing_ok=True)
                _clean_duplicate(settings, move, registered_path=registered)
                move.state = 'completed' if registered == move.destination else 'pending'
                move.error = None
            except (ApiError, OSError) as exc:
                move.error = str(exc)
        receipt.state = 'interrupted' if receipt.state == 'running' else 'partial'
        with database.write_session() as session:
            _remove_old_manifest(session, settings, receipt)
            _save_receipt(session, receipt)
