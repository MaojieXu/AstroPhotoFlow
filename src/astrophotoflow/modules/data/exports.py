"""Explicit full-result export jobs and receipts; no workflow re-execution."""
import hashlib
import json
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
from uuid import UUID, uuid5

from filelock import FileLock
from astrophotoflow.contracts.data_nodes import ExportRequest
from astrophotoflow.contracts.inputs import CheckedOutput
from astrophotoflow.contracts.media import MediaSelection
from astrophotoflow.core.errors import ApiError, not_found
from .image_formats import EXTENSIONS, read_image, read_display_image, convert_pixels, write_image, verify_image
from .science_inputs import check_output, register_output, get_output_registration
from .ingestion import process_task


class ExportCancelled(Exception): pass


class DataExports:
    def __init__(self, database, settings, workers):
        self.database, self.settings, self.workers = database, settings, workers
        self.pool = ThreadPoolExecutor(max_workers=settings.file_workers, thread_name_prefix='data-export')
        self.lock = Lock()
        self.active = {}
        self.root = settings.data_dir / 'exports'
        self.root.mkdir(parents=True, exist_ok=True)
        # A previous process cannot finish these operations. Observe and never replay them.
        for path in self.root.glob('*/receipt.json'):
            record = json.loads(path.read_text(encoding='utf-8'))
            if record['state'] in {'queued', 'running', 'cancelling'}:
                record['state'] = 'interrupted'
                self._save(path.parent, record)

    def _directory(self, request_id):
        return self.root / str(UUID(str(request_id)))

    @staticmethod
    def _save(directory, record):
        path = directory / 'receipt.json'
        part = directory / 'receipt.part'
        part.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        part.replace(path)

    def get(self, request_id):
        path = self._directory(request_id) / 'receipt.json'
        if not path.is_file(): raise not_found()
        with self.lock:
            record = json.loads(path.read_text(encoding='utf-8'))
        return {key: value for key, value in record.items() if key not in {'request', 'fingerprint', 'sources'}}

    def existing(self, body):
        path = self._directory(body.request_id) / 'receipt.json'
        if not path.is_file(): return None
        with self.lock: record = json.loads(path.read_text(encoding='utf-8'))
        fingerprint = hashlib.sha256(json.dumps(body.model_dump(mode='json', exclude_unset=True), sort_keys=True).encode()).hexdigest()
        if record['fingerprint'] != fingerprint:
            raise ApiError(409, 'EXPORT_REQUEST_CONFLICT', 'request_id already belongs to a different export.')
        return self.get(body.request_id)

    def submit(self, body, members):
        directory = self._directory(body.request_id)
        directory.mkdir(parents=True, exist_ok=True)
        request = body.model_dump(mode='json', exclude_unset=True)
        fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        with FileLock(str(directory / 'request.lock')):
            path = directory / 'receipt.json'
            if path.exists():
                previous = json.loads(path.read_text(encoding='utf-8'))
                if previous['fingerprint'] != fingerprint:
                    raise ApiError(409, 'EXPORT_REQUEST_CONFLICT', 'request_id already belongs to a different export.')
                return self.get(body.request_id)
            selected = []
            for index in body.member_indexes:
                if index >= len(members):
                    raise ApiError(422, 'INVALID_REFERENCE', 'Selected export member is outside the completed result.')
                selected.append({'index': index, **members[index]})
            if body.target == 'local':
                destination = Path(body.destination)
                if not destination.is_absolute():
                    raise ApiError(422, 'INVALID_DESTINATION', 'Choose an absolute local destination.')
                if len(selected) > 1 and not destination.is_dir():
                    raise ApiError(422, 'INVALID_DESTINATION', 'Multiple members require an existing destination folder.')
                resolved = destination.resolve()
                if resolved == self.settings.data_dir.resolve() or self.settings.data_dir.resolve() in resolved.parents:
                    raise ApiError(422, 'ORIGINAL_PROTECTED', 'Local exports cannot write into managed library storage.')
            record = {'request_id': str(body.request_id), 'state': 'queued', 'request': request,
                      'fingerprint': fingerprint, 'sources': selected, 'results': [], 'error': None,
                      'source': body.source.model_dump(mode='json'), 'target': body.target,
                      'member_indexes': body.member_indexes,
                      'destination': body.destination, 'settings': body.settings.model_dump(mode='json')}
            with self.lock:
                self._save(directory, record)
                event = Event()
                self.active[str(body.request_id)] = event
            self.pool.submit(self._execute, directory, record, body, event)
        return self.get(body.request_id)

    def cancel(self, request_id):
        identity = str(UUID(str(request_id)))
        with self.lock:
            event = self.active.get(identity)
            if event is None:
                raise ApiError(409, 'EXPORT_NOT_ACTIVE', 'This export is not active; inspect the existing receipt.')
            event.set()
            directory = self._directory(identity)
            record = json.loads((directory / 'receipt.json').read_text(encoding='utf-8'))
            if record['state'] in {'queued', 'running'}:
                record['state'] = 'cancelling'
                self._save(directory, record)
        return self.get(request_id)

    @staticmethod
    def _copy(source, destination, checkpoint):
        # Exclusive creation protects both existing files and races after the chooser closes.
        with destination.open('xb') as output:
            owned = os.fstat(output.fileno())
            try:
                with source.open('rb') as stream:
                    while chunk := stream.read(8 * 1024**2):
                        checkpoint()
                        output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            except BaseException:
                output.close()
                current = destination.stat()
                if (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino): destination.unlink()
                raise

    def _execute(self, directory, record, body, event):
        def checkpoint():
            if event.is_set(): raise ExportCancelled()
        def save():
            with self.lock:
                if event.is_set() and record['state'] in {'queued', 'running'}: record['state'] = 'cancelling'
                self._save(directory, record)
        record['state'] = 'running'
        save()
        try:
            for position, member in enumerate(record['sources']):
                checkpoint()
                pixels = None
                folder = directory / f'member-{position:06}'
                result = {'member_index': member['index'], 'state': 'running'}
                record['results'].append(result)
                save()
                try:
                    frozen = CheckedOutput.model_validate_json(json.dumps(member['checked']))
                    current = check_output(self.settings, run_directory=frozen.run_directory, path=frozen.path, expected_format=frozen.format,
                                           colour_layout=(frozen.scientific_metadata or {}).get('colour_layout'))
                    if current.content_hash != frozen.content_hash:
                        raise ApiError(409, 'SOURCE_CHANGED', 'Complete source changed after export selection.')
                    folder.mkdir(exist_ok=True)
                    if body.settings.format == 'original':
                        converted = current.path
                        output_format = current.format
                        suffix = ''.join(current.path.suffixes[-2:]) if current.path.name.lower().endswith(('.fits.fz', '.fit.fz', '.fts.fz')) else current.path.suffix
                        verification = {'copied_original': True}
                    else:
                        selected = body.selections.get(str(member['index']))
                        if selected is None:
                            selected = MediaSelection.model_validate(member.get('selection') or {})
                        result['selection'] = selected.model_dump(mode='json', exclude={'consumer_id', 'generation', 'playback_key', 'proxy'})
                        if body.settings.conversion == 'display':
                            pixels = read_display_image(current.path, current.format, selected, folder, current.scientific_metadata)
                            header = None
                            if current.format in {'fits', 'xisf'}:
                                _, header = read_image(current.path, current.format, selected, folder)
                        else:
                            pixels, header = read_image(current.path, current.format, selected, folder)
                        checkpoint()
                        pixels = convert_pixels(pixels, body.settings, folder / 'converted.npy', checkpoint)
                        suffix = EXTENSIONS[body.settings.format]
                        converted = folder / ('complete' + suffix)
                        write_image(converted, pixels, header, body.settings)
                        checkpoint()
                        verification = verify_image(converted, pixels, body.settings)
                        output_format = {'tiff': 'image', 'png': 'image', 'jpeg': 'image'}.get(body.settings.format, body.settings.format)
                    checkpoint()
                    # Full verification also rejects a source replacement made during conversion.
                    after = check_output(self.settings, run_directory=frozen.run_directory, path=frozen.path, expected_format=frozen.format,
                                         colour_layout=(frozen.scientific_metadata or {}).get('colour_layout'))
                    if after.content_hash != frozen.content_hash:
                        raise ApiError(409, 'SOURCE_CHANGED', 'Source changed while converting the complete image.')
                    if body.target == 'library':
                        checked = check_output(self.settings, run_directory=converted.parent, path=converted, expected_format=output_format,
                                               colour_layout='planar' if body.settings.format == 'fits' and len(verification.get('shape', [])) == 3 else (current.scientific_metadata or {}).get('colour_layout') if body.settings.format == 'original' else None)
                        task_id = uuid5(body.request_id, f'member:{member["index"]}')
                        accepted = register_output(self.database, self.settings, task_id=task_id, output=checked,
                                                   name=body.name if len(record['sources']) == 1 else f'{body.name or "Data"} {position + 1:04}',
                                                   provenance={'source': body.source.model_dump(mode='json'), 'member_index': member['index'],
                                                               'source_hash': frozen.content_hash, 'selection': result.get('selection'), 'settings': body.settings.model_dump(mode='json')})
                        result['registration_task_id'] = str(task_id)
                        save()
                        if accepted.task_status in {'queued', 'running'}:
                            process_task(self.database, self.settings, str(task_id), self.workers)
                        registration = get_output_registration(self.database, self.settings, task_id)
                        result['registration'] = registration.model_dump(mode='json')
                        if registration.content_status != 'available':
                            raise ApiError(422, 'REGISTRATION_FAILED', 'Inspect registration_task_id; do not repeat this export or upstream processing.')
                    else:
                        destination = Path(body.destination)
                        target = destination / f'{position + 1:04}-{body.name or "Data"}{suffix}' if len(record['sources']) > 1 else destination
                        if body.name is not None and (Path(body.name).name != body.name or '/' in body.name or '\\' in body.name):
                            raise ApiError(422, 'INVALID_NAME', 'Export name cannot contain a directory component.')
                        expected_suffixes = {suffix.lower()}
                        if suffix.lower() in {'.tif', '.tiff'}: expected_suffixes |= {'.tif', '.tiff'}
                        if suffix.lower() in {'.jpg', '.jpeg'}: expected_suffixes |= {'.jpg', '.jpeg'}
                        if suffix.lower() == '.fits': expected_suffixes |= {'.fit', '.fts'}
                        if not any(target.name.lower().endswith(extension) for extension in expected_suffixes):
                            raise ApiError(422, 'INVALID_EXTENSION', 'Destination extension must match the selected format.')
                        result['path'] = str(target)
                        save()
                        expected_copy = check_output(self.settings, run_directory=converted.parent, path=converted, expected_format=output_format,
                                                     colour_layout=(current.scientific_metadata or {}).get('colour_layout') if body.settings.format == 'original' else 'planar' if body.settings.format == 'fits' and len(verification.get('shape', [])) == 3 else None)
                        self._copy(converted, target, checkpoint)
                        exported = check_output(self.settings, run_directory=target.parent, path=target, expected_format=output_format,
                                                colour_layout=(current.scientific_metadata or {}).get('colour_layout') if body.settings.format == 'original' else 'planar' if body.settings.format == 'fits' and len(verification.get('shape', [])) == 3 else None)
                        if exported.content_hash != expected_copy.content_hash:
                            raise ApiError(409, 'SOURCE_CHANGED', 'Local copy did not match the validated complete file. Inspect this failed destination before continuing.')
                        result.update(byte_size=exported.byte_size, content_hash=exported.content_hash)
                    result.update(state='completed', verification=verification, settings=body.settings.model_dump(mode='json'))
                except ExportCancelled:
                    result['state'] = 'cancelled'
                    raise
                except Exception as exc:
                    result.update(state='failed', error={'code': getattr(exc, 'code', 'EXPORT_FAILED'), 'message': str(exc)})
                finally:
                    pixels = None  # release converted memmaps before deleting private scratch files on Windows
                    if folder.is_dir() and folder.resolve().is_relative_to(self.root.resolve()):
                        for scratch in folder.iterdir():
                            if scratch.is_file() and scratch.resolve().is_relative_to(folder.resolve()):
                                try: scratch.unlink()
                                except OSError: logging.getLogger(__name__).exception('Could not release export scratch file %s', scratch)
                save()
            record['state'] = 'completed' if all(item['state'] == 'completed' for item in record['results']) else 'completed_with_errors'
        except ExportCancelled:
            record['state'] = 'cancelled'
        except Exception as exc:
            record['state'], record['error'] = 'failed', str(exc)
        finally:
            try: save()
            finally:
                with self.lock: self.active.pop(str(body.request_id), None)

    def close(self):
        with self.lock:
            for event in self.active.values(): event.set()
        self.pool.shutdown(wait=True)


def select_export_destination(settings, body, cancelled):
    from .local_selection import select_local_paths, LocalSelectionBusy
    from astrophotoflow.core.config import ConfigurationError
    import subprocess
    name = body.suggested_name
    if Path(name).name != name or '/' in name or '\\' in name:
        raise ApiError(422, 'INVALID_NAME', 'Suggested filename cannot contain directory components.')
    try:
        paths = select_local_paths('save' if body.mode == 'file' else 'folder', settings.workspace, cancelled,
                                   suggested_name=name)
    except LocalSelectionBusy as exc:
        raise ApiError(409, 'LOCAL_PICKER_BUSY', str(exc)) from exc
    except (OSError, ConfigurationError, subprocess.SubprocessError) as exc:
        raise ApiError(503, 'LOCAL_PICKER_UNAVAILABLE', str(exc)) from exc
    return str(paths[0]) if paths else None
