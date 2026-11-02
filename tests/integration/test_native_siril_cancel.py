"""Real ComfyUI interrupt -> Bundle node -> real Siril process cancellation."""

import hashlib
import json
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx
import numpy as np
import psutil
import pytest
from astropy.io import fits

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.assets import AssetPatch
from astrophotoflow.core.config import load_running_settings


@pytest.mark.skipif(not os.environ.get('APF_TEST_NATIVE_CANCEL_WORKSPACE'), reason='Explicit isolated native cancellation opt-in')
def test_native_interrupt_stops_the_owned_real_siril_process():
    root = Path(__file__).resolve().parents[2]
    workspace = Path(os.environ['APF_TEST_NATIVE_CANCEL_WORKSPACE']).resolve()
    assert workspace == (root / '.artifacts/workspaces/modernization-current').resolve()
    settings = load_running_settings(workspace)
    assert settings.service_url == 'http://127.0.0.1:32590'
    web = 'http://127.0.0.1:32588'
    original = workspace / 'input' / ('g7-native-cancel-' + uuid4().hex + '.fits')
    pixels = np.broadcast_to(np.linspace(0.01, 0.8, 4096, dtype=np.float32), (4096, 4096))
    fits.writeto(original, pixels, fits.Header({'IMAGETYP': 'Light Frame', 'EXPTIME': 10.0}))
    original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    evidence = root / '.artifacts/reports/modernization/g7/native-siril-cancel.json'
    controlled = None
    birth = None
    with AssetClient(workspace / 'config.toml') as client, httpx.Client(trust_env=False, timeout=15, headers={'Origin': web}) as native:
        accepted = client.import_photo(original)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            task = client.get_import_task(str(accepted.task_id))
            if task.status not in {'queued', 'running', 'cancelling'}:
                break
            time.sleep(0.1)
        assert task.status == 'completed', task
        item = task.items[0]
        capability = next(node for node in client.list_nodes('gauss') if node.operation.operation_id == 'gauss')
        assert capability.available
        definition = capability.node.definition
        inputs = {parameter.name: parameter.default for parameter in definition.parameters}
        inputs['runtime'] = json.dumps({'threads': 1})
        inputs['sigma'] = 20.0
        inputs[definition.execution.inputs['image']] = ['1', 0]
        output_name = definition.execution.outputs['image']
        output_index = next(index for index, port in enumerate(definition.outputs) if port.name == output_name)
        reference = {'kind': 'asset_version', 'asset_version_id': str(item.asset_version_id), 'selection': {'kind': 'whole_file'}}
        graph = {
            '1': {'class_type': 'APF_DATA_REFERENCE', 'inputs': {'reference': json.dumps(reference)}},
            '2': {'class_type': capability.node.native_type, 'inputs': inputs},
            '3': {'class_type': 'APF_DATA_REFERENCE', 'inputs': {'reference': '', 'science': ['2', output_index]}},
        }
        queue = native.get(web + '/queue')
        queue.raise_for_status()
        assert queue.json() == {'queue_running': [], 'queue_pending': []}
        response = native.post(web + '/prompt', json={'prompt': graph, 'client_id': str(uuid4())})
        response.raise_for_status()
        prompt_id = response.json()['prompt_id']
        report = {'prompt_id': prompt_id, 'source_version': str(item.asset_version_id), 'original_sha256': original_hash}
        evidence.write_text(json.dumps(report, indent=2), encoding='utf-8')
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                calls = client.list_run_calls(prompt_id, node_id='2')
                call = calls[0] if calls else None
                runtime = call.observation.runtime_ref if call and call.observation else None
                if call and call.state in {'completed', 'failed', 'cancelled', 'unknown'}:
                    pytest.fail(f'Original native call ended before controlled interrupt: {call.model_dump_json()}')
                if runtime and call.observation.active:
                    try:
                        process = psutil.Process(runtime['pid'])
                        if process.create_time() == runtime['create_time'] and Path(process.exe()).resolve() == Path(runtime['executable']).resolve():
                            # Freeze only this validated owned child so a fast finish cannot
                            # turn the cancellation test into an already-completed query.
                            process.suspend()
                            controlled, birth = process, process.create_time()
                            break
                    except psutil.NoSuchProcess:
                        pass
                time.sleep(0.02)
            assert controlled is not None, 'No owned active Siril child was observed; do not resubmit this prompt'
            report['runtime_ref'] = runtime
            report['suspended_for_deterministic_interrupt'] = True
            evidence.write_text(json.dumps(report, indent=2), encoding='utf-8')
            interrupted = native.post(web + '/interrupt', json={'prompt_id': prompt_id})
            interrupted.raise_for_status()
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                current = client.get_run_call(prompt_id, str(call.call_id))
                if current.state in {'cancelled', 'failed', 'completed', 'unknown'} and current.observation and current.observation.active is False:
                    break
                time.sleep(0.1)
            assert current.state == 'cancelled', current
            assert current.observation.active is False and current.observation.exit_code is not None
            report['software_call'] = current.model_dump(mode='json')
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                history = native.get(web + '/history/' + prompt_id).json()
                if prompt_id in history:
                    break
                time.sleep(0.1)
            assert prompt_id in history
            assert any(kind == 'execution_interrupted' for kind, _ in history[prompt_id]['status']['messages'])
            assert hashlib.sha256(original.read_bytes()).hexdigest() == original_hash
            report.update(native_history=history[prompt_id], original_unchanged=True)
            asset = client.get_asset(str(item.asset_id))
            archived = client.update_asset(str(asset.id), AssetPatch(base_revision=asset.revision, status='archived'))
            report['fixture_asset_archived'] = str(archived.id)
            evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        finally:
            if controlled is not None:
                try:
                    if controlled.is_running() and controlled.create_time() == birth:
                        controlled.resume()
                except psutil.NoSuchProcess:
                    pass
