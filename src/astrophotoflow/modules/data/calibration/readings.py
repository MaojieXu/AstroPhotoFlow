"""Read effective relationships without running scientific compatibility checks."""

import hashlib

from sqlalchemy import and_, case, func, literal, select
from sqlalchemy.orm import aliased, selectinload

from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.calibration.checks import ALLOWED_SLOTS
from astrophotoflow.modules.data.calibration.choices import SLOTS, UNCONFIGURED, explicit_choices
from astrophotoflow.modules.data.datasets.bindings import default_bindings, member_bindings
from astrophotoflow.modules.data.datasets.calibration import version_classification
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion, MemberCalibration


def target_details(session, choices):
    references = [choice['target'] for bindings in choices for choice in bindings.values() if choice['mode'] == 'target']
    asset_ids = {target['id'] for target in references if target['kind'] == 'asset_version'}
    result = {}
    if asset_ids:
        for asset, version in session.execute(select(Asset, AssetVersion).join(AssetVersion, AssetVersion.asset_id == Asset.id).where(AssetVersion.id.in_(asset_ids))):
            result[('asset_version', version.id)] = {'target': {'kind': 'asset_version', 'id': version.id},
                'asset_id': asset.id, 'name': asset.name, 'version_number': version.version_number, 'target_kind': 'master', 'master_required': False}
    return result


def slot_details(choices, details, *, overrides=None, standalone=False, frame_type=None, classify=True):
    result = {}
    for slot, choice in choices.items():
        reference = choice.get('target')
        result[slot] = {'choice': choice,
            'source': 'standalone' if standalone else 'member_override' if slot in (overrides or {}) else 'dataset_default',
            'status': 'not_applicable' if classify and frame_type is not None and slot not in ALLOWED_SLOTS.get(frame_type, set()) else choice['mode'],
            'target_detail': details.get((reference['kind'], reference['id'])) if reference else None,
            'check_state': 'not_checked'}
    return result


def _token(value):
    if value is None:
        return 'disabled'
    if value == UNCONFIGURED:
        return 'unconfigured'
    return value['kind'] + ':' + str(value['id'])


def _choice(token):
    if ':' not in token:
        return {'mode': token}
    kind, identity = token.split(':', 1)
    return {'mode': 'target', 'target': {'kind': kind, 'id': identity}}


def _key(tokens):
    return hashlib.sha256('|'.join(tokens).encode()).hexdigest()


def dataset_calibration_page(session, dataset_id, version_id, member_asset_version_ids=None, limit=50, offset=0, combination_key=None):
    dataset = session.get(Dataset, str(dataset_id))
    version = session.get(DatasetVersion, str(version_id))
    if dataset is None or version is None or version.dataset_id != dataset.id:
        raise not_found()
    defaults = default_bindings(version)
    # Group the four effective slot identities in SQL. This reads relationship
    # columns only, never loads every scientific image or runs recursive checks.
    base = select(DatasetMember.id).where(DatasetMember.dataset_version_id == version.id)
    tokens = []
    for slot in SLOTS:
        override = aliased(MemberCalibration)
        base = base.outerjoin(override, and_(override.member_id == DatasetMember.id, override.frame_type == slot))
        tokens.append(case((override.member_id.is_(None), literal(_token(defaults.get(slot, UNCONFIGURED)))),
            (override.state == 'unconfigured', literal('unconfigured')),
            (override.disabled.is_(True), literal('disabled')),
            else_=literal('asset_version:') + override.asset_version_id))
    grouped = base.with_only_columns(*tokens, func.count()).group_by(*tokens)
    combinations = []
    token_sets = {}
    for row in session.execute(grouped):
        values = tuple(row[:len(SLOTS)])
        key = _key(values)
        token_sets[key] = values
        combinations.append({'key': key, 'member_count': row[-1], 'effective': dict(zip(SLOTS, map(_choice, values), strict=True))})
    combinations.sort(key=lambda item: (-item['member_count'], item['key']))
    if combination_key is not None:
        if combination_key not in token_sets:
            raise ApiError(422, 'INVALID_REFERENCE', 'The calibration combination does not belong to this fixed dataset version.')
        base = base.where(*(expression == value for expression, value in zip(tokens, token_sets[combination_key], strict=True)))
    if member_asset_version_ids is not None:
        identities = [str(value) for value in member_asset_version_ids]
        present = set(session.scalars(select(DatasetMember.asset_version_id).where(DatasetMember.dataset_version_id == version.id, DatasetMember.asset_version_id.in_(identities))))
        if not identities or len(identities) != len(set(identities)) or present != set(identities):
            raise ApiError(422, 'INVALID_REFERENCE', 'Select unique members belonging to the fixed dataset version.')
        base = base.where(DatasetMember.asset_version_id.in_(identities))
    total = session.scalar(select(func.count()).select_from(base.subquery()))
    page_ids = base.order_by(DatasetMember.position).limit(limit).offset(offset)
    members = session.execute(select(DatasetMember, Asset, AssetVersion)
        .options(selectinload(DatasetMember.overrides))
        .join(AssetVersion, AssetVersion.id == DatasetMember.asset_version_id).join(Asset, Asset.id == AssetVersion.asset_id)
        .where(DatasetMember.id.in_(page_ids)).order_by(DatasetMember.position)).all()
    rows = []
    for member, asset, asset_version in members:
        overrides = member_bindings(member)
        frame_type = version_classification(asset, asset_version).get('frame_type')
        rows.append({'asset_id': asset.id, 'asset_name': asset.name, 'asset_version_number': asset_version.version_number,
            'frame_type': frame_type, 'asset_version_id': member.asset_version_id, 'overrides': explicit_choices(overrides),
            'effective': explicit_choices({**defaults, **overrides}, complete=True),
            '_frame_type': frame_type})
    details = target_details(session, [row['effective'] for row in rows] + [item['effective'] for item in combinations])
    for row in rows:
        row['slots'] = slot_details(row['effective'], details, overrides=row['overrides'], frame_type=row.pop('_frame_type'))
    for item in combinations:
        item['slots'] = slot_details(item['effective'], details, classify=False)
    return {'dataset_id': dataset.id, 'dataset_version_id': version.id, 'revision': dataset.revision,
        'defaults': explicit_choices(defaults, complete=True), 'items': rows, 'combinations': combinations,
        'total': total, 'limit': limit, 'offset': offset}
