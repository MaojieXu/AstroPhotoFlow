"""Read owned display bytes; a preview is never a scientific input."""

from dataclasses import dataclass
from pathlib import Path
from sqlalchemy import case, select
from astrophotoflow.contracts.assets import PreviewReference
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import not_found
from astrophotoflow.modules.data.datasets.models import DatasetMember, Dataset
from astrophotoflow.modules.data.formats.fits import PREVIEW_ALGORITHM_VERSION
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.media.thumbnail_batches import THUMBNAIL_STANDALONE, group_algorithm


@dataclass(frozen=True)
class PreviewContent:
    content: bytes
    mime_type: str


def _content(settings: Settings, preview: Preview) -> PreviewContent:
    relative = Path(preview.storage_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise not_found()
    root = settings.data_dir.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
        return PreviewContent(path.read_bytes(), preview.mime_type)
    except (OSError, ValueError) as exc:
        raise not_found() from exc


def read_preview_content(database: Database, settings: Settings, reference: PreviewReference, size: str) -> PreviewContent:
    if size not in {"thumbnail", "display"} or reference.hdu_index is None:
        raise not_found()
    with database.read_session() as session:
        algorithm = [Preview.algorithm_version == PREVIEW_ALGORITHM_VERSION] if size == "display" else []
        preview = session.scalar(
            select(Preview)
            .where(
                *algorithm,
                Preview.asset_id == str(reference.asset_id),
                Preview.hdu_index == reference.hdu_index,
                Preview.size == size,
                Preview.status == "available",
            )
            .order_by(case((Preview.algorithm_version == THUMBNAIL_STANDALONE, 0), else_=1), Preview.created_at.desc())
            .limit(1)
        )
        if preview is None:
            raise not_found()
        return _content(settings, preview)


def read_dataset_thumbnail(database: Database, settings: Settings, dataset_id: str, asset_id: str) -> PreviewContent:
    with database.read_session() as session:
        owned = select(Dataset.id).where(Dataset.id == str(dataset_id), Dataset.id == str(dataset_id)).exists()
        member = (
            select(DatasetMember.id)
            .where(DatasetMember.dataset_id == str(dataset_id), DatasetMember.asset_id == str(asset_id))
            .correlate(None)
            .exists()
        )
        reference_id = session.scalar(
            select(DatasetMember.asset_id)
            .where(owned, member, DatasetMember.dataset_id == str(dataset_id))
            .order_by(DatasetMember.position)
            .limit(1)
        )
        if reference_id is None:
            raise not_found()
        preview = session.scalar(
            select(Preview).where(
                Preview.asset_id == str(asset_id),
                Preview.size == "group_thumbnail",
                Preview.algorithm_version == group_algorithm(reference_id),
                Preview.status == "available",
            )
        )
        if preview is None:
            raise not_found()
        return _content(settings, preview)
