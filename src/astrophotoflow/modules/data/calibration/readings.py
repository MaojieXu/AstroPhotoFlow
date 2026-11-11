"""Read fixed calibration relationships without running scientific checks."""
from sqlalchemy import select
from astrophotoflow.core.errors import not_found
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.calibration.checks import ALLOWED_SLOTS
from astrophotoflow.modules.data.calibration.choices import explicit_choices
from astrophotoflow.modules.data.datasets.bindings import dataset_bindings
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember

def target_details(session, choices):
    references = [choice['target'] for bindings in choices for choice in bindings.values() if choice['mode'] == 'target']
    asset_ids = {target['id'] for target in references if target['kind'] == 'asset'}
    result = {}
    if asset_ids:
        for asset in session.scalars(select(Asset).where(Asset.id.in_(asset_ids))):
            from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval
            in_trash = session.get(LibraryEntryRemoval, ('asset', asset.id)) is not None
            result['asset', asset.id] = {'in_trash': in_trash, 'target': {'kind': 'asset', 'id': asset.id}, 'asset_id': asset.id, 'name': asset.name, 'target_kind': 'master', 'master_required': False}
    return result

def slot_details(choices, details, *, standalone=False, frame_type=None):
    result = {}
    for slot, choice in choices.items():
        reference = choice.get('target')
        result[slot] = {'choice': choice, 'source': 'standalone' if standalone else 'dataset', 'status': 'not_applicable' if frame_type is not None and slot not in ALLOWED_SLOTS.get(frame_type, set()) else choice['mode'], 'target_detail': details.get((reference['kind'], reference['id'])) if reference else None, 'check_state': 'not_checked'}
    return result

def read_dataset_calibration(session, dataset_id):
    dataset = session.get(Dataset, str(dataset_id))
    if dataset is None:
        raise not_found()
    choices = explicit_choices(dataset_bindings(dataset), complete=True)
    slots = slot_details(choices, target_details(session, [choices]))
    frame_type = Asset.frame_type
    purposes = set(session.scalars(select(frame_type).join(DatasetMember, DatasetMember.asset_id == Asset.id).where(DatasetMember.dataset_id == dataset.id).distinct()))
    if purposes and None not in purposes:
        for slot, detail in slots.items():
            if any((slot not in ALLOWED_SLOTS.get(purpose, set()) for purpose in purposes)):
                detail['status'] = 'not_applicable'
    from astrophotoflow.modules.data.calibration.checks import inspect_calibration_bindings
    ids = list(session.scalars(select(DatasetMember.asset_id).where(DatasetMember.dataset_id == dataset.id).order_by(DatasetMember.position)))
    diagnostics = inspect_calibration_bindings(session, ids, dataset_bindings(dataset))
    return {'diagnostics': diagnostics, 'dataset_id': dataset.id, 'revision': dataset.revision, 'calibration': choices, 'slots': slots}
