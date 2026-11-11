"""Project calibration relations into the public sparse binding map."""
from astrophotoflow.modules.data.datasets.models import DatasetCalibration, Dataset

def _bindings(rows) -> dict:
    return {row.frame_type: {'mode': 'unconfigured'} if row.state == 'unconfigured' else None if row.disabled else {'kind': 'asset', 'id': row.asset_id} for row in rows}

def dataset_bindings(version: Dataset) -> dict:
    return _bindings(version.calibration)

def set_dataset_bindings(dataset: Dataset, bindings: dict) -> None:
    existing = {row.frame_type: row for row in dataset.calibration}
    current = []
    for frame_type, target in bindings.items():
        row = existing.get(frame_type)
        if row is None:
            row = DatasetCalibration(dataset_id=dataset.id, frame_type=frame_type)
        for field, value in _target_columns(target).items():
            setattr(row, field, value)
        current.append(row)
    dataset.calibration = current

def _target_columns(target) -> dict:
    unconfigured = bool(target and target.get('mode') == 'unconfigured')
    return {'state': 'unconfigured' if unconfigured else 'disabled' if target is None else 'target', 'disabled': target is None or unconfigured, 'asset_id': target['id'] if target and target.get('kind') == 'asset' else None}
