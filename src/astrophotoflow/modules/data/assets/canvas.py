from sqlalchemy import select
from sqlalchemy.orm import Session

from astrophotoflow.contracts.inputs import (
    AssetInputReference,
    CanvasDataOut,
    CanvasDataRequest,
    CanvasInspectOut,
    CanvasInspectRequest,
    DatasetInputMember,
    DatasetInputReference,
    ScienceSelection,
)
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.assets.metadata import asset_parameters
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion, FitsHduMetadata
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion
from astrophotoflow.modules.data.equipment.models import Equipment
from astrophotoflow.modules.data.formats.layout import rgb_channel_first
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
from astrophotoflow.modules.data.media.links import asset_media_base
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval


def _available_asset(session: Session, version_id: str) -> tuple[Asset, AssetVersion]:
    version = session.get(AssetVersion, version_id)
    asset = session.get(Asset, version.asset_id) if version else None
    if asset is None or asset.scope != "shared" or asset.status != "active":
        raise not_found()
    if version.availability != "available" or not version.content_hash or version.byte_size is None:
        raise ApiError(409, "SOURCE_UNAVAILABLE", f"{asset.name} 的原件尚未就绪或已经变化，不能加入画布。", message_key='the_original_for_p0_is_not_ready_or_has_changed_and_cannot_be_added_to_the_', message_params={'p0': asset.name})
    return asset, version


def prepare_canvas_data(database: Database, body: CanvasDataRequest) -> CanvasDataOut:
    with database.read_session() as session:
        if session.get(LibraryEntryRemoval, (body.entry_type, str(body.id))) is not None:
            raise not_found()
        if body.entry_type == "asset":
            asset, version = _available_asset(session, str(body.version_id))
            if asset.id != str(body.id):
                raise not_found()
            return CanvasDataOut(title=asset.name, native_type='APF_FILE_REFERENCE' if (version.scientific_metadata or {}).get('format') == 'other' else 'APF_DATA_REFERENCE', reference=AssetInputReference(
                kind="asset_version", asset_version_id=version.id,
                selection=ScienceSelection(kind="whole_file"),
            ))
        dataset = session.get(Dataset, str(body.id))
        version = session.get(DatasetVersion, str(body.version_id))
        if dataset is None or dataset.status != "active" or version is None or version.dataset_id != dataset.id:
            raise not_found()
        members = session.scalars(select(DatasetMember).where(
            DatasetMember.dataset_version_id == version.id,
        ).order_by(DatasetMember.position)).all()
        indexes = body.member_indexes
        if indexes is not None:
            if not set(indexes).issubset({member.position for member in members}):
                raise ApiError(422, "INVALID_REFERENCE", "所选成员不属于固定图像组版本。", message_key='the_selected_member_does_not_belong_to_the_fixed_image_group_version')
            members = [member for member in members if member.position in indexes]
        if not members:
            raise ApiError(422, "INVALID_REFERENCE", "空图像组不能加入画布。", message_key='an_empty_image_group_cannot_be_added_to_the_canvas')
        kinds = {(_available_asset(session, member.asset_version_id)[1].scientific_metadata or {}).get('format') == 'other' for member in members}
        if len(kinds) != 1:
            raise ApiError(422, 'INVALID_REFERENCE', '文件与科学图像需要通过各自类型的输入端口加入。', message_key='files_and_scientific_images_must_use_their_respective_input_port_types')
        file_group = True in kinds
        return CanvasDataOut(title=f"{dataset.name} · {len(members)} {'个文件' if file_group else '张'}",
            native_type='APF_FILE_REFERENCE' if file_group else 'APF_DATA_REFERENCE', reference=DatasetInputReference(
            kind="dataset_version", dataset_version_id=version.id,
            members=[DatasetInputMember(
                member_index=member.position, asset_version_id=member.asset_version_id,
                selection=ScienceSelection(kind="whole_file"),
            ) for member in members],
        ))




def inspect_canvas_data(database: Database, body: CanvasInspectRequest) -> CanvasInspectOut:
    reference = body.reference
    with database.read_session() as session:
        if reference.kind == "dataset_version":
            fixed = session.get(DatasetVersion, str(reference.dataset_version_id))
            dataset = session.get(Dataset, fixed.dataset_id) if fixed else None
            if dataset is None:
                raise not_found()
            members = session.scalars(select(DatasetMember).where(DatasetMember.dataset_version_id == fixed.id)).all()
            expected = {member.position: member.asset_version_id for member in members}
            indexes = [member.member_index for member in reference.members]
            if indexes != sorted(set(indexes)) or any(expected.get(member.member_index) != str(member.asset_version_id) for member in reference.members):
                raise ApiError(422, "INVALID_REFERENCE", "引用成员与固定图像组版本不匹配。", message_key='referenced_members_do_not_match_the_fixed_image_group_version')
            if body.member_index >= len(reference.members):
                raise ApiError(422, "INVALID_REFERENCE", "当前图片序号超出引用范围。", message_key='the_image_index_is_outside_the_reference_selection')
            current = reference.members[body.member_index]
            version_id, selection = str(current.asset_version_id), current.selection
            title, total = dataset.name, len(reference.members)
        else:
            if body.member_index != 0:
                raise ApiError(422, "INVALID_REFERENCE", "单件素材只有一张。", message_key='a_single_asset_contains_only_one_image')
            version_id, selection = str(reference.asset_version_id), reference.selection
            title, total = None, 1
        version = session.get(AssetVersion, version_id)
        asset = session.get(Asset, version.asset_id) if version else None
        if asset is None or asset.scope != "shared":
            raise not_found()
        selected = session.scalar(select(FitsHduMetadata).where(
            FitsHduMetadata.asset_version_id == version.id, FitsHduMetadata.is_selected.is_(True),
        ))
        hdu = selected if selection.kind == "whole_file" else session.scalar(select(FitsHduMetadata).where(
            FitsHduMetadata.asset_version_id == version.id, FitsHduMetadata.hdu_index == selection.hdu_index,
        ))
        metadata = version.scientific_metadata or {}
        hdu_index = hdu.hdu_index if hdu else 0
        preview = session.scalar(select(Preview).where(
            Preview.asset_version_id == version.id, Preview.hdu_index == hdu_index, Preview.size == "thumbnail",
        ).order_by(Preview.created_at.desc()).limit(1))
        active = session.scalar(select(AssetTaskItem.id).join(AssetTask, AssetTask.id == AssetTaskItem.task_id).where(
            AssetTaskItem.asset_version_id == version.id, AssetTask.status.in_({"queued", "running", "cancelling"}),
        ).limit(1))
        status = preview.status if preview else ("unsupported" if metadata.get("parse_error") else "pending" if active else "not_ready")
        error = preview.error if preview else metadata.get("parse_error")
        if selection.kind == "fits_hdu" and (hdu is None or selected is None or hdu.hdu_index != selected.hdu_index):
            status, error = "unsupported", "所选 HDU 暂无可展示的预览。"
        if status == "generating":
            status = "pending"
        if status == "pending" and version.availability != "available":
            status = "not_ready"
        width, height = None, None
        shape = hdu.shape if hdu else None
        if shape and len(shape) >= 2:
            header = {card["keyword"]: card.get("value") for card in hdu.header_cards}
            if hdu.supported_kind == "rgb" and len(shape) == 3 and not rgb_channel_first(header):
                height, width = shape[-3], shape[-2]
            else:
                height, width = shape[-2], shape[-1]
        equipment = {}
        for kind in ("camera", "filter", "optical_system"):
            equipment_id = (asset_parameters(asset) or {}).get(kind + "_id")
            registered = session.get(Equipment, equipment_id) if equipment_id else None
            snapshot = (asset.equipment_snapshot or {}).get(kind + "_id") or {}
            equipment[kind] = registered.name if registered else snapshot.get("name")
        return CanvasInspectOut(
            title=title or asset.name, total=total, member_index=body.member_index,
            asset_id=asset.id, asset_version_id=version.id, name=asset.name,
            view_base=asset_media_base(asset.id, version.id),
            availability=version.availability, parameters=asset_parameters(asset) or {}, equipment=equipment,
            format=metadata.get("format"), width=width, height=height,
            bitpix=hdu.bitpix if hdu else None, pixel_type=hdu.pixel_type if hdu else None,
            preview_status=status, preview_error=error,
            byte_size=version.byte_size, content_hash=version.content_hash,
            preview_url=f"/astrophotoflow/api/v1/library/assets/{asset.id}/versions/{version.id}/previews/thumbnail" if status == "available" else None,
        )
