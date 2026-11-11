"""Batch projections for the existing library and fixed member tables."""
from sqlalchemy import select
from astrophotoflow.contracts.calibration import LibraryCalibrationProjection
from astrophotoflow.modules.data.calibration.choices import explicit_choices
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.calibration.readings import slot_details, target_details
from astrophotoflow.modules.data.datasets.bindings import dataset_bindings
from astrophotoflow.modules.data.datasets.models import Dataset

def library_calibration_projections(session, items):
    assets = {str(item.id): item for item in items if item.entry_type == 'asset' and item.id}
    dataset_ids = {str(item.id) for item in items if item.entry_type == 'dataset' and item.id}
    configurations = {asset.id: asset for asset in session.scalars(select(Asset).where(Asset.id.in_(assets)))}
    datasets = session.scalars(select(Dataset).where(Dataset.id.in_(dataset_ids))).all() if dataset_ids else []
    grouped = {version.id: explicit_choices(dataset_bindings(version), complete=True) for version in datasets}
    standalone = {identity: explicit_choices(configurations[identity].calibration if identity in configurations else {}, complete=True) for identity in assets}
    details = target_details(session, [*standalone.values(), *grouped.values()])
    result = {}
    for identity, item in assets.items():
        result[identity] = LibraryCalibrationProjection.model_validate({'slots': slot_details(standalone[identity], details, standalone=True, frame_type=item.summary.classification.frame_type.value)})
    for identity, choices in grouped.items():
        result[identity] = LibraryCalibrationProjection.model_validate({'slots': slot_details(choices, details)})
    return result
