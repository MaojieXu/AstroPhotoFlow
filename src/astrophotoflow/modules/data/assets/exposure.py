"""SQL exposure totals are separate from common-value metadata summaries."""
from sqlalchemy import case, func, select
from astrophotoflow.contracts.assets import ExposureSummary
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.models import DatasetMember

def exposure_summary(subframe_count=0, known_count=0, total_seconds=None):
    unknown_count = subframe_count - known_count
    return ExposureSummary(subframe_count=subframe_count, known_count=known_count, unknown_count=unknown_count, total_seconds=total_seconds if known_count else None, complete=unknown_count == 0)

def summarize_dataset_exposures(session, dataset_ids):
    """Aggregate the current member exposures independently of pagination."""
    ids = [str(identity) for identity in dataset_ids]
    if not ids:
        return {}
    exposure = Asset.exposure_seconds
    known = exposure.is_not(None)
    rows = session.execute(select(DatasetMember.dataset_id, func.count(), func.sum(case((known, 1), else_=0)), func.sum(exposure)).join(Asset, Asset.id == DatasetMember.asset_id).where(DatasetMember.dataset_id.in_(ids)).group_by(DatasetMember.dataset_id))
    result = {identity: exposure_summary() for identity in ids}
    result.update({identity: exposure_summary(count, known_count, total) for identity, count, known_count, total in rows})
    return result
