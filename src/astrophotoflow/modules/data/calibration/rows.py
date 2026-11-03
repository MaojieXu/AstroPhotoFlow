"""Batch projections for the existing library and fixed member tables."""

from copy import deepcopy

from sqlalchemy import and_, case, func, literal, select
from sqlalchemy.orm import aliased

from astrophotoflow.contracts.calibration import LibraryCalibrationProjection
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.calibration.choices import SLOTS, explicit_choices
from astrophotoflow.modules.data.calibration.models import ImageCalibrationConfiguration
from astrophotoflow.modules.data.calibration.readings import slot_details, target_details
from astrophotoflow.modules.data.datasets.bindings import default_bindings, member_bindings
from astrophotoflow.modules.data.datasets.calibration import version_classification
from astrophotoflow.modules.data.datasets.models import DatasetCalibration, DatasetMember, DatasetVersion, MemberCalibration


def _latest_configurations(session, version_ids):
    if not version_ids:
        return {}
    latest = select(ImageCalibrationConfiguration.asset_version_id.label('version_id'),
        func.max(ImageCalibrationConfiguration.version_number).label('number')).where(
        ImageCalibrationConfiguration.asset_version_id.in_(version_ids)).group_by(
        ImageCalibrationConfiguration.asset_version_id).subquery()
    return {row.asset_version_id: row for row in session.scalars(select(ImageCalibrationConfiguration).join(latest,
        and_(latest.c.version_id == ImageCalibrationConfiguration.asset_version_id,
             latest.c.number == ImageCalibrationConfiguration.version_number)))}


def _token(columns):
    return case((columns.state == 'unconfigured', literal('unconfigured')),
        (columns.disabled.is_(True), literal('disabled')),
        (columns.asset_version_id.is_not(None), literal('target:') + columns.asset_version_id),
        else_=literal('unconfigured'))


def _choice(token):
    return ({'mode': 'target', 'target': {'kind': 'asset_version', 'id': token[7:]}}
            if token.startswith('target:') else {'mode': token})


def _dataset_patterns(session, version_ids):
    """Aggregate relations in SQL; never materialize every group member."""
    if not version_ids:
        return []
    frame_type = case((Asset.current_version_id == AssetVersion.id, Asset.frame_type), else_=AssetVersion.frame_type)
    base = select(DatasetMember.dataset_version_id, frame_type).join(
        AssetVersion, AssetVersion.id == DatasetMember.asset_version_id).join(Asset, Asset.id == AssetVersion.asset_id)
    values, overridden = [], []
    for slot in SLOTS:
        default, override = aliased(DatasetCalibration), aliased(MemberCalibration)
        base = base.outerjoin(default, and_(default.dataset_version_id == DatasetMember.dataset_version_id,
            default.frame_type == slot)).outerjoin(override, and_(override.member_id == DatasetMember.id,
            override.frame_type == slot))
        values.append(case((override.member_id.is_not(None), _token(override)), else_=_token(default)))
        overridden.append(override.member_id.is_not(None))
    columns = [DatasetMember.dataset_version_id, frame_type, *values, *overridden]
    statement = base.with_only_columns(*columns).where(
        DatasetMember.dataset_version_id.in_(version_ids)).group_by(*columns)
    patterns = []
    for row in session.execute(statement):
        choices = dict(zip(SLOTS, map(_choice, row[2:6]), strict=True))
        patterns.append((row[0], row[1], choices, {slot: choices[slot]
            for slot, present in zip(SLOTS, row[6:10], strict=True) if present}))
    return patterns


def library_calibration_projections(session, items):
    assets = {str(item.version_id): item for item in items if item.entry_type == 'asset' and item.version_id}
    datasets = {str(item.version_id) for item in items if item.entry_type == 'dataset' and item.version_id}
    configurations = _latest_configurations(session, assets)
    patterns = _dataset_patterns(session, datasets)
    standalone = {identity: explicit_choices(configurations[identity].bindings if identity in configurations else {}, complete=True)
        for identity in assets}
    details = target_details(session, [*standalone.values(), *(choices for _, _, choices, _ in patterns)])
    result = {}
    for identity, item in assets.items():
        frame_type = item.summary.classification.frame_type.value
        result[identity] = LibraryCalibrationProjection.model_validate({'slots': slot_details(
            standalone[identity], details, standalone=True, frame_type=frame_type),
            'binding_version_id': configurations[identity].id if identity in configurations else None})
    grouped = {identity: [] for identity in datasets}
    for identity, frame_type, choices, overrides in patterns:
        grouped[identity].append(slot_details(choices, details, overrides=overrides, frame_type=frame_type))
    for identity, members in grouped.items():
        slots = {}
        for slot in SLOTS:
            applicable = [member[slot] for member in members if member[slot]['status'] != 'not_applicable']
            if not applicable:
                slots[slot] = {'choice': {'mode': 'unconfigured'}, 'source': 'dataset_default',
                    'status': 'not_applicable' if members else 'unconfigured'}
            elif all(item['choice'] == applicable[0]['choice'] for item in applicable):
                value = deepcopy(applicable[0])
                if any(item['source'] != value['source'] for item in applicable):
                    value['source'] = 'mixed'
                slots[slot] = value
            else:
                slots[slot] = {'choice': None, 'source': 'mixed', 'status': 'mixed'}
        result[identity] = LibraryCalibrationProjection.model_validate({'slots': slots})
    return result


def member_calibration_projections(session, rows):
    """Resolve one already-paged member selection in its group context."""
    if not rows:
        return {}
    version_ids = {member.dataset_version_id for member, _, _ in rows}
    versions = {version.id: version for version in session.scalars(select(DatasetVersion).where(DatasetVersion.id.in_(version_ids)))}
    prepared = []
    for member, version, asset in rows:
        overrides = explicit_choices(member_bindings(member))
        choices = explicit_choices({**default_bindings(versions[member.dataset_version_id]), **member_bindings(member)}, complete=True)
        prepared.append((member, choices, overrides, version_classification(asset, version).get('frame_type')))
    details = target_details(session, [choices for _, choices, _, _ in prepared])
    return {member.id: LibraryCalibrationProjection.model_validate({'slots': slot_details(
        choices, details, overrides=overrides, frame_type=frame_type)})
        for member, choices, overrides, frame_type in prepared}
