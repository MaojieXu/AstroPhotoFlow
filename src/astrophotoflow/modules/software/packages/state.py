"""Persist package state without installation or process policy."""
import logging
import os

from astrophotoflow.contracts.software import SoftwarePackageState
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.files import replace_file

logger = logging.getLogger(__name__)

def state_path(settings, package_id):
    return settings.workspace / "software" / package_id / "state.json"


def write_package_state(settings, package_id, state, *, progress_only=False):
    path = state_path(settings, package_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(".part")
    part.write_text(state.model_dump_json(indent=2) + "\n", encoding="utf-8")
    try:
        replace_file(part, path)
    except PermissionError as exc:
        if os.name != "nt" or getattr(exc, "winerror", None) != 5:
            raise
        if progress_only:
            logger.warning("安装进度状态暂未写入，保留上次进度 package=%s phase=%s progress=%s path=%s",
                           package_id, state.phase, state.progress, path, exc_info=True)
            return
        logger.exception("安装结果状态保存失败 package=%s path=%s", package_id, path)
        raise ApiError(503, "SOFTWARE_STATE_SAVE_FAILED", "安装结果未能保存，需核对软件状态；请勿直接重复安装。", message_key='the_installation_result_could_not_be_saved_check_the_software_state_do_not_') from exc


def state_from_package(package):
    return SoftwarePackageState.model_validate(package.model_dump(include=set(SoftwarePackageState.model_fields)))

