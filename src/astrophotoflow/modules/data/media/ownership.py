from pathlib import Path
from sqlalchemy import select
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.media.cache import media_locations
from astrophotoflow.modules.data.media.models import Preview


def owned_preview_locations(preview, settings) -> list[str]:
    if preview.storage_path and Path(preview.storage_path).name == "manifest.json":
        return media_locations(preview, settings)
    if not preview.storage_path:
        return []
    locations = [preview.storage_path]
    temporary = preview.storage_path + ".tmp"
    if preview.size == "display" and (settings.data_dir / temporary).is_file():
        locations.append(temporary)
    return locations


def assert_no_preview_jobs(session, version_ids) -> None:
    if session.scalar(select(Preview.id).where(Preview.asset_id.in_(version_ids), Preview.status == "generating").limit(1)):
        raise ApiError(
            409,
            "PREVIEW_ACTIVE",
            "大图预览仍在生成，请完成后重新预览清理范围。",
            message_key="the_full_size_preview_is_still_being_generated_preview_cleanup_again_after_",
        )
