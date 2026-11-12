"""Per-import Object recipes for compatible subframes; masters stay independent."""

from __future__ import annotations
import json
from copy import deepcopy
from pathlib import Path
from sqlalchemy import and_, or_, select
from astrophotoflow.modules.data.assets.metadata import asset_classification, asset_parameters
from astrophotoflow.modules.data.assets.models import Asset, FitsHduMetadata
from astrophotoflow.modules.data.formats.fits import PREVIEW_ALGORITHM_VERSION
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
from astrophotoflow.modules.data.media.models import Preview


def preview_context(database, task_id: str, asset_id: str) -> dict:
    with database.read_session() as session:
        task = session.get(AssetTask, task_id)
        asset = session.get(Asset, asset_id)
        category = (asset.scientific_metadata or {}).get("format")
        frame_class = (asset_classification(asset) or {}).get("frame_class")
        auto = task.target_dataset_id is not None and category in {"fits", "xisf", "image"} and (frame_class in {"subframe", "masterframe"})
        key = None
        observed = (asset.scientific_metadata or {}).get("observed_parameters") or {}
        target = " ".join((observed.get("target_name") or "").split()).casefold()
        if auto and frame_class == "subframe" and target:
            item = session.scalar(select(AssetTaskItem).where(AssetTaskItem.task_id == task_id, AssetTaskItem.asset_id == asset_id))
            if category == "fits":
                hdu = session.scalar(
                    select(FitsHduMetadata).where(FitsHduMetadata.asset_id == asset_id, FitsHduMetadata.is_selected.is_(True))
                )
                layout = (
                    [hdu.supported_kind, hdu.bitpix, hdu.bscale, hdu.bzero, hdu.bunit, (asset_parameters(asset) or {}).get("cfa_pattern")]
                    if hdu
                    else None
                )
            else:
                layout = observed.get("preview_layout")
            if layout is not None:
                key = json.dumps(
                    ["object-mtf-1", item.root_id, str(Path(item.source_path).parent), target, category, layout],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
        profile = None
        owner = task
        while key is not None:
            profile = ((owner.report or {}).get("preview_stretch_groups") or {}).get(key)
            if profile is None:
                rows = session.scalars(
                    select(Preview)
                    .join(AssetTaskItem, AssetTaskItem.asset_id == Preview.asset_id)
                    .where(
                        AssetTaskItem.task_id == owner.id,
                        or_(
                            and_(
                                Preview.size == "thumbnail",
                                Preview.status == "available",
                                Preview.algorithm_version == PREVIEW_ALGORITHM_VERSION,
                            ),
                            and_(
                                Preview.size == "viewer",
                                Preview.status.in_({"available", "generating"}),
                                Preview.algorithm_version.like("media-view-1:%"),
                            ),
                        ),
                    )
                    .order_by(AssetTaskItem.position)
                ).all()
                recipe = next(
                    (
                        row.display_parameters
                        for row in rows
                        if (row.display_parameters or {}).get("stretch_group") == key and "auto_stretch" in row.display_parameters
                    ),
                    None,
                )
                if recipe is not None:
                    profile = {"auto_stretch": recipe["auto_stretch"], "reference_asset_id": recipe["stretch_reference_asset_id"]}
            if profile is not None or owner.retry_of_task_id is None:
                break
            owner = session.get(AssetTask, owner.retry_of_task_id)
        return {
            "task_id": task_id,
            "auto": auto,
            "group_key": key,
            "auto_stretch": deepcopy(profile["auto_stretch"]) if profile else None,
            "save_group": key is not None and key not in ((task.report or {}).get("preview_stretch_groups") or {}),
            "reference_asset_id": profile["reference_asset_id"] if profile else asset_id,
        }


def backfill_context(database, asset_id: str) -> dict:
    with database.read_session() as session:
        task_ids = session.scalars(
            select(AssetTaskItem.task_id)
            .join(AssetTask, AssetTask.id == AssetTaskItem.task_id)
            .where(AssetTaskItem.asset_id == asset_id)
            .order_by(AssetTask.created_at.desc(), AssetTask.id.desc())
        ).all()
    if not task_ids:
        return {"auto": False, "auto_stretch": None, "group_key": None}
    context = preview_context(database, task_ids[0], asset_id)
    for task_id in task_ids:
        candidate = preview_context(database, task_id, asset_id)
        if candidate["auto_stretch"] is not None:
            return candidate
    return context


def describe_recipe(context: dict, display: dict) -> dict:
    if context["group_key"] is not None:
        return {**display, "stretch_group": context["group_key"], "stretch_reference_asset_id": context["reference_asset_id"]}
    return display


def save_group_recipe(database, context: dict, display: dict) -> None:
    if not context["save_group"] or "auto_stretch" not in display:
        return
    with database.write_session() as session:
        task = session.get(AssetTask, context["task_id"])
        groups = dict((task.report or {}).get("preview_stretch_groups") or {})
        if context["group_key"] not in groups:
            groups[context["group_key"]] = {
                "auto_stretch": deepcopy(display["auto_stretch"]),
                "reference_asset_id": context["reference_asset_id"],
            }
            task.report = {**(task.report or {}), "preview_stretch_groups": groups}
