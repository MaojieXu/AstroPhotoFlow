"""Current calibration projections shared by datasets and manifests."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from astrophotoflow.contracts.calibration_status import CALIBRATION_STATUSES, CalibrationSummary
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.models import DatasetMember


def dataset_calibration_summary(session: Session, dataset_id: str) -> CalibrationSummary:
    return dataset_calibration_summaries(session, [dataset_id])[dataset_id]


def dataset_calibration_summaries(session: Session, dataset_ids: list[str]) -> dict[str, CalibrationSummary]:
    counts_by_id = {identity: dict.fromkeys(CALIBRATION_STATUSES, 0) for identity in dataset_ids}
    if not dataset_ids:
        return {}
    rows = session.execute(
        select(DatasetMember.dataset_id, Asset.calibration_status, func.count())
        .select_from(Asset)
        .join(DatasetMember, DatasetMember.asset_id == Asset.id)
        .where(DatasetMember.dataset_id.in_(dataset_ids))
        .group_by(DatasetMember.dataset_id, Asset.calibration_status)
    )
    for identity, status, count in rows:
        counts_by_id[identity][status] = count
    return {identity: calibration_summary(counts) for identity, counts in counts_by_id.items()}


def calibration_summary(counts: dict) -> CalibrationSummary:
    present = [status for status, count in counts.items() if count]
    return CalibrationSummary(
        calibration_status=present[0] if len(present) == 1 else 'Unknown',
        calibration_counts=counts,
    )


def single_calibration_summary(status: str) -> CalibrationSummary:
    return calibration_summary({value: int(value == status) for value in CALIBRATION_STATUSES})
