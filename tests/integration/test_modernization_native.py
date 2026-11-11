"""Opt-in native queue checks against the Goal's isolated synthetic workspace."""
import hashlib
import json
import os
import time
from pathlib import Path
from uuid import UUID, uuid4
import httpx
import pytest
from astrophotoflow.contracts.assets import AssetPage
from astrophotoflow.core.config import load_running_settings

@pytest.mark.skipif(not os.environ.get('APF_MODERNIZATION_WORKSPACE'), reason='Requires the isolated modernization preview')
def test_native_data_prompt_without_saved_workflow():
    root = Path(__file__).resolve().parents[2]
    workspace = Path(os.environ['APF_MODERNIZATION_WORKSPACE']).resolve()
    assert workspace == (root / '.artifacts/workspaces/modernization-current').resolve()
    settings = load_running_settings(workspace)
    web = 'http://127.0.0.1:32588'
    assert settings.service_url == 'http://127.0.0.1:32590'
    auth = {'Authorization': 'Bearer ' + settings.token_path.read_text().strip()}
    native = {'Origin': web}
    report_path = root / '.artifacts/reports/modernization/g6/unnamed-draft-native-final.json'
    with httpx.Client(trust_env=False, timeout=10) as client:
        response = client.get(settings.service_url + '/api/v1/library/assets', params={'limit': 1}, headers=auth)
        response.raise_for_status()
        asset = AssetPage.model_validate_json(response.content).items[0]
        assert asset is not None and asset.storage_mode == 'managed'
        source = (settings.data_dir / asset.storage_location).resolve()
        assert source.is_relative_to(workspace) and source.suffix.lower() == '.fits'
        original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        queue = client.get(web + '/queue', headers=native)
        queue.raise_for_status()
        assert queue.json() == {'queue_running': [], 'queue_pending': []}
        reference = {'kind': 'asset', 'asset_id': str(asset.id), 'selection': {'kind': 'whole_file'}}
        graph = {'1': {'class_type': 'APF_DATA_REFERENCE', 'inputs': {'reference': json.dumps(reference)}}}
        accepted = client.post(web + '/prompt', headers=native, json={'prompt': graph, 'client_id': str(uuid4()), 'extra_data': {}})
        accepted.raise_for_status()
        reply = accepted.json()
        assert not reply.get('node_errors')
        prompt_id = reply['prompt_id']
        UUID(prompt_id)
        report = {'accepted': reply, 'submitted_without_workflow_or_snapshot': True, 'source_sha256': original_hash}
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        deadline = time.monotonic() + 50
        while time.monotonic() < deadline:
            response = client.get(web + '/history/' + prompt_id, headers=native)
            response.raise_for_status()
            history = response.json()
            if prompt_id in history:
                break
            time.sleep(0.25)
        else:
            pytest.fail(f'Native prompt {prompt_id} is not terminal; inspect that identity before any further submission')
        item = history[prompt_id]
        report['history'] = item
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        assert item['status']['status_str'] == 'success', item['status']
        result = item['outputs']['1']['apf_data'][0]
        assert result['state'] == 'completed' and result['workflow_id'] is None
        assert result['output']['run_id'] == prompt_id
        assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
        assert not (workspace / 'runs' / prompt_id / 'calculation-snapshot.json').exists()
        response = client.get(settings.service_url + f"/api/v1/data-nodes/{prompt_id}/{result['execution_id']}", headers=auth)
        response.raise_for_status()
        assert response.json()['output'] == result['output']
        report.update(data_result=response.json(), source_unchanged=True, full_snapshot_absent=True)
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
