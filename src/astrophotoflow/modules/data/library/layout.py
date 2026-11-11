"""Readable managed paths and capture facts used for explicit dataset grouping."""

import re
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from astrophotoflow.contracts.calibration_status import CALIBRATION_STATUSES
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.models import Dataset
from astrophotoflow.modules.data.files import managed_data_path

PURPOSE_DIRECTORIES = {
    'light': 'Light', 'dark': 'Dark', 'flat': 'Flat', 'bias': 'Bias', 'dark_flat': 'DarkFlat',
}
RESERVED_NAMES = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'} | {
    f'{prefix}{number}' for prefix in ('COM', 'LPT') for number in (*range(1, 10), '¹', '²', '³')
}
CAPTURE_FIELDS = (
    'frame_type', 'camera', 'optical_system', 'readout_mode', 'parameter_mode', 'iso',
    'gain', 'offset', 'sensor_temperature_c', 'exposure_seconds', 'filter', 'binning_x', 'binning_y',
)
UNKNOWN_CAPTURE_TOKENS = 'CAMERA-UNK__MODE-UNK__GAIN-UNK__T-UNK__EXP-UNK__F-UNK'


def safe_component(value: str) -> str:
    component = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).strip().rstrip('. ')
    if not component:
        component = 'UNK'
    if component.split('.')[0].upper() in RESERVED_NAMES:
        component = '_' + component
    return component


def number_text(value: float | None) -> str:
    return 'UNK' if value is None else format(Decimal(str(value)).normalize(), 'f')


def observed_equipment(asset: Asset, slot: str) -> str | None:
    snapshot = (asset.equipment_snapshot or {}).get(slot + '_id')
    if snapshot:
        return snapshot.get('name')
    observed = (asset.scientific_metadata or {}).get('observed_parameters') or {}
    return observed.get({'camera': 'camera_name', 'optical_system': 'telescope_name', 'filter': 'filter_name'}[slot])


def capture_profile(asset: Asset) -> dict:
    """Preserve unknowns and exact observed names, including filter aliases."""
    values = {field: getattr(asset, field) for field in CAPTURE_FIELDS if field not in {'camera', 'optical_system', 'filter'}}
    if (asset.value_sources or {}).get('parameter_mode') == 'unknown':
        values['parameter_mode'] = None
    for slot in ('camera', 'optical_system', 'filter'):
        values[slot] = {
            'id': getattr(asset, slot + '_id'),
            'name': observed_equipment(asset, slot),
        }
    optical = (asset.equipment_snapshot or {}).get('optical_system_id') or {}
    values['optical_system'].update(
        optical_accessory_id=(optical.get('optical_accessory') or {}).get('id'),
        effective_focal_length_mm=optical.get('effective_focal_length_mm'),
    )
    return values


def capture_tokens(asset: Asset) -> str:
    mode = asset.parameter_mode
    parameters = []
    if asset.iso is not None or mode == 'iso':
        parameters.append('ISO' + number_text(asset.iso) if asset.iso is not None else 'ISO-UNK')
    if asset.gain is not None or mode == 'gain':
        parameters.append('GAIN' + number_text(asset.gain) if asset.gain is not None else 'GAIN-UNK')
    if not parameters:
        parameters.append('STANDARD' if mode == 'standard' and (asset.value_sources or {}).get('parameter_mode') != 'unknown' else 'GAIN-UNK')
    tokens = [
        observed_equipment(asset, 'camera') or 'CAMERA-UNK',
        asset.readout_mode or 'MODE-UNK', *parameters,
        'T' + number_text(asset.sensor_temperature_c) + 'C' if asset.sensor_temperature_c is not None else 'T-UNK',
        'EXP' + number_text(asset.exposure_seconds) + 's' if asset.exposure_seconds is not None else 'EXP-UNK',
    ]
    if asset.frame_type not in {'dark', 'bias', 'dark_flat'}:
        tokens.append('F-' + (observed_equipment(asset, 'filter') or 'UNK'))
    return '__'.join(safe_component(token) for token in tokens)


def capture_identity(asset: Asset) -> dict:
    values = capture_profile(asset)
    for slot in ('camera', 'optical_system', 'filter'):
        if values[slot]['id'] is not None:
            values[slot]['name'] = None
    return values


def classification_directory(asset: Asset) -> Path:
    form = {'subframe': 'Subframe', 'masterframe': 'MasterFrame'}.get(asset.frame_class, 'Other')
    purpose = PURPOSE_DIRECTORIES.get(asset.frame_type, 'Unclassified') if form != 'Other' else 'Unclassified'
    return Path(purpose) / form / asset.calibration_status


def initialize_library(data_dir: Path) -> None:
    managed_data_path(data_dir, 'library')
    for name in ('previews', 'staging'):
        managed_data_path(data_dir, name).mkdir(parents=True, exist_ok=True)
    for purpose in (*PURPOSE_DIRECTORIES.values(), 'Unclassified'):
        forms = ('Subframe', 'MasterFrame', 'Other') if purpose == 'Unclassified' else ('Subframe', 'MasterFrame')
        for form in forms:
            for status in CALIBRATION_STATUSES:
                library_path(data_dir, Path(purpose) / form / status).mkdir(parents=True, exist_ok=True)


def library_path(data_dir: Path, relative: str | Path) -> Path:
    root = data_dir.resolve() / 'library'
    path = managed_data_path(data_dir, Path('library') / relative)
    if path == root or not path.is_relative_to(root):
        raise ApiError(422, 'FILE_SCOPE_INVALID', 'Library paths must stay inside the managed library.', message_key='library_paths_must_stay_inside_the_managed_library')
    return path


def named_directory(session: Session, data_dir: Path, parent: Path, label: str, identity: str, *, current: str | None = None) -> str:
    """Increase the stable short ID when another registered path occupies it."""
    occupied = {value.casefold() for value in session.scalars(select(Dataset.library_directory)).all() if value}
    occupied.update(
        str(Path(value).parent.relative_to('library')).replace('\\', '/').casefold()
        for value in session.scalars(select(Asset.storage_location).where(Asset.storage_mode == 'managed'))
        if value and Path(value).parts[0] == 'library'
    )
    compact = identity.replace('-', '')
    for length in range(8, len(compact) + 1):
        relative = (parent / f'{safe_component(label)}__{compact[:length]}').as_posix()
        path = library_path(data_dir, relative)
        if current is not None and relative == current:
            return relative
        if relative.casefold() not in occupied and not path.exists():
            return relative
    raise ApiError(409, 'PATH_CONFLICT', 'The managed directory is already occupied.', message_key='the_managed_directory_is_already_occupied')


def allocate_import_location(session: Session, settings, asset: Asset, task, filename: str) -> str:
    """Reserve paths inside the import write transaction before copying bytes."""
    dataset = session.get(Dataset, task.target_dataset_id) if task.target_dataset_id else None
    directory = dataset.library_directory if dataset else (task.report or {}).get('library_directory')
    grouped = task.target_dataset_id is not None and asset.frame_class == 'subframe'
    if not grouped or not directory:
        parent = classification_directory(asset)
        label = asset.name
        identity = asset.id
        if grouped:
            label = task.dataset_name or 'Dataset'
            identity = task.target_dataset_id
            statuses = {file.get('calibration_status', 'Unknown') for file in (task.image_import_plan or {}).get('files', {}).values()}
            status = next(iter(statuses)) if len(statuses) == 1 else 'Unknown' if statuses else asset.calibration_status
            parent = parent.parent / status
        if asset.frame_class == 'masterframe':
            parent /= capture_tokens(asset)
        else:
            label += '__' + capture_tokens(asset)
        directory = named_directory(session, settings.data_dir, parent, label, identity)
        if grouped:
            task.report = {**(task.report or {}), 'library_directory': directory}
    filename = safe_component(filename)
    if filename.casefold() == 'dataset.json':
        filename = 'dataset__' + asset.id.replace('-', '')[:8] + '.json'
    relative = (Path('library') / directory / filename).as_posix()
    occupied = {value.casefold() for value in session.scalars(select(Asset.storage_location).where(Asset.id != asset.id))}
    original = Path(filename)
    suffix = ''.join(original.suffixes[-2:]) if filename.lower().endswith(('.fits.fz', '.fit.fz', '.fts.fz')) else original.suffix
    stem = filename[:-len(suffix)] if suffix else filename
    compact = asset.id.replace('-', '')
    for length in range(8, len(compact) + 2):
        destination = library_path(settings.data_dir, Path(directory) / filename)
        if relative.casefold() not in occupied and not destination.exists():
            return relative
        filename = f'{stem}__{compact[:length]}{suffix}'
        relative = (Path('library') / directory / filename).as_posix()
    raise ApiError(409, 'PATH_CONFLICT', 'The managed filename is already occupied.', message_key='the_managed_filename_is_already_occupied')
