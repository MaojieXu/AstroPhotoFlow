"""SQL exposure totals are separate from common-value metadata summaries."""

from sqlalchemy import and_, case, func, select

from astrophotoflow.contracts.assets import ExposureSummary
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.datasets.models import DatasetMember


def exposure_summary(subframe_count=0, known_count=0, total_seconds=None):
    unknown_count = subframe_count - known_count
    return ExposureSummary(subframe_count=subframe_count, known_count=known_count,
        unknown_count=unknown_count, total_seconds=total_seconds if known_count else None,
        complete=unknown_count == 0)


def summarize_dataset_exposures(session, version_ids, *, frozen=False):
    """Current views adopt corrections; explicit version views use capture facts."""
    ids = [str(identity) for identity in version_ids]
    if not ids:
        return {}
    fixed_class = AssetVersion.capture_snapshot['classification']['frame_class'].as_string()
    fixed_exposure = AssetVersion.capture_snapshot['parameters']['exposure_seconds'].as_float()
    if frozen:
        frame_class, exposure = fixed_class, fixed_exposure
    else:
        current = Asset.current_version_id == AssetVersion.id
        frame_class = case((current, Asset.frame_class), else_=fixed_class)
        exposure = case((current, Asset.exposure_seconds), else_=fixed_exposure)
    subframe = frame_class == 'subframe'
    known = and_(subframe, exposure.is_not(None))
    rows = session.execute(select(DatasetMember.dataset_version_id,
        func.sum(case((subframe, 1), else_=0)),
        func.sum(case((known, 1), else_=0)),
        func.sum(case((subframe, exposure), else_=None)))
        .join(AssetVersion, AssetVersion.id == DatasetMember.asset_version_id)
        .join(Asset, Asset.id == AssetVersion.asset_id)
        .where(DatasetMember.dataset_version_id.in_(ids))
        .group_by(DatasetMember.dataset_version_id))
    result = {identity: exposure_summary() for identity in ids}
    result.update({identity: exposure_summary(count, known_count, total)
        for identity, count, known_count, total in rows})
    return result
