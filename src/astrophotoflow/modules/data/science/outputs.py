from __future__ import annotations
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from astrophotoflow.contracts.assets import OutputRegistration
from astrophotoflow.contracts.common import ErrorDetail
from astrophotoflow.contracts.inputs import CheckedOutput, ScienceFormat, ScienceSelection
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.common import uuid_text
from astrophotoflow.modules.data.files import format_for_path
from astrophotoflow.modules.data.formats.fits import inspect_fits
from astrophotoflow.modules.data.formats.video import first_video_frame
from astrophotoflow.modules.data.formats.xisf import inspect_xisf
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
from astrophotoflow.modules.data.science.files import hash_file, read_hash_and_copy

def fits_frame_hdus(inspected):
    images = [row for row in inspected['hdus'] if row['shape'] and row['hdu_type'] in {'PrimaryHDU', 'ImageHDU', 'CompImageHDU'} and (not ((row.get('name') or '').casefold() == 'iccprofile' and row['bitpix'] == 8 and (len(row['shape']) == 1)))]
    return [row['hdu_index'] for row in images] if all((row['supported_kind'] is not None for row in images)) else []

def check_output(settings: Settings, *, run_directory: Path, path: Path, expected_format: ScienceFormat, allow_empty: bool=False, colour_layout: str | None=None, expected_frames: int | None=None) -> CheckedOutput:
    try:
        root = run_directory.resolve(strict=True)
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ApiError(422, 'OUTPUT_UNAVAILABLE', '输出文件不在本次运行目录内或当前无法读取。', message_key='the_output_file_is_outside_this_run_directory_or_cannot_be_read') from exc
    if not resolved.is_file():
        raise ApiError(422, 'OUTPUT_UNAVAILABLE', '输出位置不是完整文件。', message_key='the_output_location_is_not_a_complete_file')
    actual_format = format_for_path(resolved) or 'other'
    if actual_format != expected_format:
        raise ApiError(422, 'VALIDATION_ERROR', '输出格式与本次运行记录不一致。', message_key='the_output_format_does_not_match_this_run_s_record')
    content_hash, byte_size, mtime_ns = hash_file(resolved)
    if allow_empty and actual_format != 'other':
        raise ApiError(422, 'VALIDATION_ERROR', '科学输出不能声明为空文件。', message_key='scientific_output_must_not_be_declared_as_an_empty_file')
    if byte_size == 0 and (not allow_empty):
        raise ApiError(422, 'OUTPUT_UNAVAILABLE', '输出文件为空。', message_key='the_output_file_is_empty')
    scientific_metadata = {'format': actual_format}
    if colour_layout not in {None, 'planar', 'interleaved'}:
        raise ApiError(422, 'VALIDATION_ERROR', '未知的图像颜色布局。', message_key='unknown_image_color_layout')
    if actual_format == 'fits':
        try:
            inspected = inspect_fits(resolved, colour_layout=colour_layout, verify_span=True)
            scientific_metadata.update(selected_hdu=inspected['selected_hdu'], hdu_count=len(inspected['hdus']))
            scientific_metadata['observed_parameters'] = inspected['parsed_parameters']
            frames = fits_frame_hdus(inspected)
            scientific_metadata['frame_count'] = len(frames) or None
            if len(frames) > 1:
                scientific_metadata['frame_hdus'] = frames
            selected = next((row for row in inspected['hdus'] if row['is_selected']), None)
            if selected is not None:
                scientific_metadata.update({key: selected[key] for key in ('shape', 'bitpix', 'pixel_type', 'bunit')})
            if colour_layout is not None:
                scientific_metadata['colour_layout'] = colour_layout
        except Exception as exc:
            raise ApiError(422, 'OUTPUT_UNAVAILABLE', 'FITS 输出无法完整解析。', message_key='the_fits_output_cannot_be_parsed_completely') from exc
    elif actual_format == 'xisf':
        try:
            scientific_metadata.update(inspect_xisf(resolved))
        except Exception as exc:
            raise ApiError(422, 'OUTPUT_UNAVAILABLE', 'XISF 输出无法完整解析。', message_key='the_xisf_output_cannot_be_parsed_completely') from exc
    elif actual_format == 'video' and resolved.suffix.lower() == '.ser':
        from astrophotoflow.modules.data.formats.ser import ser_info
        info = ser_info(resolved)
        scientific_metadata.update(frame_count=info.count, width=info.width, height=info.height, channels=info.channels, pixel_depth=info.pixel_depth, pixel_type=str(info.dtype))
    if expected_frames is not None and scientific_metadata.get('frame_count') != expected_frames:
        raise ApiError(422, 'OUTPUT_UNAVAILABLE', '完整输出的实际帧数与软件结果不一致。', message_key='the_actual_frame_count_does_not_match_the_software_result')
    checked = CheckedOutput(run_directory=root, path=resolved, format=actual_format, byte_size=byte_size, content_hash=content_hash, checked_at=datetime.now(UTC), scientific_metadata=scientific_metadata, mtime_ns=mtime_ns)
    current_hash, current_size, current_mtime = hash_file(resolved)
    if (current_hash, current_size, current_mtime) != (content_hash, byte_size, mtime_ns):
        raise ApiError(409, 'SOURCE_CHANGED', '输出文件在检查期间发生变化。', message_key='the_output_file_changed_during_validation')
    return checked

def render_output_preview(checked: CheckedOutput, destination: Path, *, selection: ScienceSelection | None=None, max_edge: int, cfa_pattern: str | None=None, auto_stretch: bool=True) -> None:
    from astrophotoflow.modules.data.formats.fits import create_preview
    from astrophotoflow.modules.data.formats.raster import read_raster_preview
    from astrophotoflow.modules.data.formats.raw import read_raw_preview
    from astrophotoflow.modules.data.formats.xisf import read_xisf_preview
    if max_edge < 1:
        raise ApiError(422, 'VALIDATION_ERROR', '预览尺寸必须是正整数。', message_key='preview_dimensions_must_be_positive_integers')
    source = checked.path.resolve(strict=True)
    content_hash, byte_size, _ = hash_file(source)
    if content_hash != checked.content_hash or byte_size != checked.byte_size:
        raise ApiError(409, 'SOURCE_CHANGED', '输出文件在预览生成前发生变化。', message_key='the_output_file_changed_before_preview_generation')
    target = destination.resolve(strict=False)
    if source == target:
        raise ApiError(422, 'VALIDATION_ERROR', '预览不能覆盖科学输出文件。', message_key='a_preview_must_not_overwrite_the_scientific_output_file')
    try:
        if checked.format == 'fits':
            layout = (checked.scientific_metadata or {}).get('colour_layout')
            inspected = inspect_fits(source, cfa_pattern, colour_layout=layout)
            if selection is None or selection.kind == 'whole_file':
                hdu_index = inspected['selected_hdu']
            elif selection.kind == 'fits_hdu':
                hdu_index = selection.hdu_index
            else:
                hdu_index = None
            row = next((item for item in inspected['hdus'] if item['hdu_index'] == hdu_index), None)
            if row is None or row['supported_kind'] is None:
                raise ApiError(422, 'PREVIEW_UNSUPPORTED', 'FITS 输出没有可预览的受支持 HDU。', message_key='the_fits_output_has_no_supported_hdu_for_preview')
            if auto_stretch:
                image, _ = create_preview(source, hdu_index, row['supported_kind'], {'cfa_pattern': cfa_pattern, 'colour_layout': layout}, max_edge)
            else:
                from astrophotoflow.modules.data.media.rendering import direct_fits_image
                image = direct_fits_image(source, hdu_index, max_edge, colour_layout=layout)
        elif checked.format == 'image':
            image, _ = read_raster_preview(source, max_edge=max_edge)
        elif checked.format == 'raw':
            image = read_raw_preview(source, max_edge)
        elif checked.format == 'xisf':
            image, _ = read_xisf_preview(source, max_edge=max_edge)
        elif checked.format == 'video':
            if source.suffix.lower() != '.ser' and shutil.which('ffmpeg') is None:
                raise ApiError(422, 'PREVIEW_DEPENDENCY_UNAVAILABLE', '资产服务未找到 FFmpeg，无法生成视频首帧预览。', message_key='the_asset_service_could_not_find_ffmpeg_to_generate_a_video_first_frame_pre')
            image, _ = first_video_frame(source, max_edge)
        else:
            raise ApiError(422, 'PREVIEW_UNSUPPORTED', f'{checked.format} 输出当前不支持生成预览。', message_key='preview_generation_is_not_supported_for_p0_output', message_params={'p0': checked.format})
    except ApiError:
        raise
    except ImportError as exc:
        raise ApiError(422, 'PREVIEW_DEPENDENCY_UNAVAILABLE', f'生成 {checked.format} 预览所需的解码依赖不可用。', message_key='a_decoder_required_to_generate_a_p0_preview_is_unavailable', message_params={'p0': checked.format}) from exc
    except Exception as exc:
        raise ApiError(422, 'PREVIEW_FAILED', f'输出预览生成失败：{exc}', message_key='output_preview_generation_failed_p0', message_params={'p0': exc}) from exc
    image.thumbnail((max_edge, max_edge))
    part = target.with_name(target.name + '.' + str(uuid4()) + '.part')
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(part, format='JPEG')
        after_hash, after_size, _ = hash_file(source)
        if (after_hash, after_size) != (checked.content_hash, checked.byte_size):
            raise ApiError(409, 'SOURCE_CHANGED', '输出文件在预览生成期间发生变化。', message_key='the_output_file_changed_during_preview_generation')
        os.replace(part, target)
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(422, 'PREVIEW_FAILED', f'输出预览写入失败：{exc}', message_key='could_not_write_the_output_preview_p0', message_params={'p0': exc}) from exc
    finally:
        part.unlink(missing_ok=True)

def output_registration(session: Session, task: AssetTask, created: bool) -> OutputRegistration:
    item = session.scalar(select(AssetTaskItem).where(AssetTaskItem.task_id == task.id).order_by(AssetTaskItem.position).limit(1))
    asset_id = UUID(item.asset_id) if item and item.asset_id else None
    error = task.error or (item.error if item else None)
    error_detail = ErrorDetail.model_validate(error) if error else None
    return OutputRegistration(task_id=UUID(task.id), created=created, task_status=task.status, asset_id=asset_id, content_status=item.content_status if item else 'pending', metadata_status=item.metadata_status if item else 'pending', preview_status=item.preview_status if item else 'pending', error=error_detail)

def register_output(database: Database, settings: Settings, *, task_id: UUID, output: CheckedOutput, name: str | None, provenance: dict | None=None) -> OutputRegistration:
    try:
        relative = output.path.resolve(strict=False).relative_to(output.run_directory.resolve(strict=False)).as_posix()
    except ValueError as exc:
        raise ApiError(422, 'OUTPUT_UNAVAILABLE', '输出文件不在本次运行目录内。', message_key='the_output_file_is_outside_this_run_directory') from exc
    effective_name = name if name is not None else output.path.stem or output.path.name
    from astrophotoflow.contracts.common import check_name
    try:
        effective_name = check_name(effective_name)
    except ValueError as exc:
        raise ApiError(422, 'VALIDATION_ERROR', str(exc), message_key='output_name_invalid', fields=[{'path': 'name', 'message': str(exc)}]) from exc
    task_id_text = str(task_id)
    identity = f'run-output:{relative}:{output.content_hash}'
    with database.read_session() as session:
        existing = session.get(AssetTask, task_id_text)
        if existing is not None:
            report = existing.report or {}
            if not report.get('output_registration') or report.get('output_identity') != identity or report.get('output_name') != effective_name:
                raise ApiError(409, 'TASK_STATE_CONFLICT', 'task_id 已用于不同的素材登记操作。', message_key='task_id_is_already_used_for_a_different_asset_registration_operation')
            return output_registration(session, existing, False)
    current = check_output(settings, run_directory=output.run_directory, path=output.path, expected_format=output.format, colour_layout=(output.scientific_metadata or {}).get('colour_layout'))
    if (current.content_hash, current.byte_size) != (output.content_hash, output.byte_size):
        raise ApiError(409, 'SOURCE_CHANGED', '所选输出在检查后发生变化。', message_key='the_selected_output_changed_after_validation')
    suffix = ''.join(current.path.suffixes[-2:]).lower() if current.path.name.lower().endswith(('.fits.fz', '.fit.fz', '.fts.fz')) else current.path.suffix.lower()
    stored_name = f'0-{uuid4().hex}{suffix}'
    upload_root = settings.data_dir / 'upload-staging' / task_id_text
    source_copy = upload_root / stored_name
    upload_root.mkdir(parents=True, exist_ok=True)
    try:
        copied_hash, copied_size = read_hash_and_copy(current.path, source_copy, lambda: False)
        if copied_hash != current.content_hash or copied_size != current.byte_size:
            raise ApiError(409, 'SOURCE_CHANGED', '输出在复制到素材登记暂存区时发生变化。', message_key='the_output_changed_while_being_copied_to_asset_registration_staging')
        now = datetime.now(UTC)
        output_metadata = output.scientific_metadata or {}
        report = {'output_processing_calibration': output_metadata.get('processing_calibration'), 'output_value_sources': output_metadata.get('value_sources') or {}, 'calibration_status': output_metadata.get('calibration_status', 'Unknown'), 'output_calibration_evidence': output_metadata.get('calibration_evidence') or {'source': 'platform', 'behavior': 'unknown'}, 'output_registration': True, 'output_identity': identity, 'output_name': effective_name, 'output_provenance': provenance, 'output_colour_layout': (current.scientific_metadata or {}).get('colour_layout'), 'upload_source_task_id': task_id_text, 'upload_files': [{'name': current.path.name, 'size': current.byte_size, 'received': current.byte_size, 'stored_name': stored_name}]}
        task = AssetTask(id=task_id_text, status='queued', sources=[], storage_mode='managed', classification=output_metadata.get('classification') or {}, parameters=output_metadata.get('parameters') or {}, import_defaults_snapshot={'parameters': {}, 'classification': {}, 'equipment_snapshots': {snapshot['id']: snapshot for snapshot in (output_metadata.get('equipment_snapshot') or {}).values() if snapshot and snapshot.get('id')}, 'selected_equipment': output_metadata.get('equipment_snapshot') or {}}, notes=None, dataset_name=None, target_dataset_id=None, dataset_base_revision=None, dataset_id=None, enumeration_completed=True, retry_of_task_id=None, report=report, error=None, created_at=now, updated_at=now)
        item = AssetTaskItem(id=str(uuid4()), task_id=task_id_text, root_item_id=str(uuid4()), retry_of_item_id=None, root_id='__upload__', source_path=stored_name, source_identity=identity, position=0, status='queued', content_status='pending', metadata_status='pending', preview_status='pending', asset_id=None, error=None, created_at=now, updated_at=now)
        with database.write_session() as session:
            existing = session.get(AssetTask, task_id_text)
            if existing is not None:
                report = existing.report or {}
                if report.get('output_registration') and report.get('output_identity') == identity and (report.get('output_name') == effective_name):
                    source_copy.unlink(missing_ok=True)
                    return output_registration(session, existing, False)
                raise ApiError(409, 'TASK_STATE_CONFLICT', '登记任务已由另一个请求创建，请查询任务状态。', message_key='another_request_created_the_registration_task_query_the_task_state')
            session.add(task)
            session.add(item)
            session.flush()
            return output_registration(session, task, True)
    except Exception:
        if source_copy.exists():
            source_copy.unlink()
        try:
            upload_root.rmdir()
        except OSError:
            pass
        raise

def get_output_registration(database: Database, settings: Settings, task_id: UUID) -> OutputRegistration:
    with database.read_session() as session:
        task = session.get(AssetTask, uuid_text(task_id))
        if task is None or not (task.report or {}).get('output_registration'):
            raise not_found()
        return output_registration(session, task, False)
