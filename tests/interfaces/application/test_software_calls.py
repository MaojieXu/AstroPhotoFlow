import asyncio
import json
import os
from uuid import uuid4
import httpx
import pytest
from astrophotoflow.core.config import Settings
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.interfaces.application import software_calls
from astrophotoflow.modules.software.public import read_software_call, save_software_call
from astrophotoflow.modules.software.execution.records import call_record_path
from astrophotoflow.modules.data.public import publish_checked_result, get_checked_result
from astrophotoflow.contracts.results import CheckedResult, CheckedResultPort, CheckedResultMember
from astrophotoflow.modules.software import bundles
from astrophotoflow.contracts.nodes import NodeDefinition
from astrophotoflow.contracts.software import NativeBundleCall
from astrophotoflow.contracts.software_calls import SoftwareCallRecord, SoftwareCallBundle

def make_record(settings, prompt_id, call_id, *, operation_id='autostretch', **changes):
    operation = bundles.operation(settings.workspace, 'siril', operation_id, True, None)
    definition = NodeDefinition.model_validate(next((value for value in bundles.release('siril')['nodes'] if value['execution']['operation_id'] == operation_id)))
    request = NativeBundleCall(prompt_id=prompt_id, call_id=call_id, node_id='3', definition_id=definition.definition_id, definition_token='fixture', inputs={}, parameters={item.name: item.default for item in definition.parameters})
    record = dict(request=request, definition=definition, operation=operation, parameters={item.name: item.default for item in operation.parameters}, bundle=SoftwareCallBundle(version='0.2.0-dev.2', commit='fixture'), output_display='direct', state='starting')
    record.update(changes)
    return SoftwareCallRecord(**record)

@pytest.mark.parametrize('snapshot_state', ['running', 'unknown'])
def test_status_read_during_completion_cannot_overwrite_terminal_facts(tmp_path, monkeypatch, snapshot_state):
    settings = Settings('127.0.0.1', 8190, tmp_path, (), workspace=tmp_path)
    prompt, call = (uuid4(), uuid4())
    starting = make_record(settings, prompt, call, state=snapshot_state)
    completed = make_record(settings, prompt, call, state='completed', result_registered=True)
    save_software_call(settings, prompt, call, starting)
    active = {call: object()}
    original_read = read_software_call
    completed_once = False

    def read_while_owner_finishes(*args):
        nonlocal completed_once
        snapshot = original_read(*args)
        if not completed_once:
            completed_once = True
            save_software_call(settings, prompt, call, completed)
            active.pop(call)
        return snapshot
    monkeypatch.setattr(software_calls, 'read_software_call', read_while_owner_finishes)
    observed = asyncio.run(software_calls.observe_software_call(settings, active, prompt, call))
    assert observed.state == 'completed' and observed.result_registered
    persisted = original_read(settings, prompt, call)
    assert persisted.state == 'completed' and persisted.result_registered

@pytest.mark.skipif(os.name != 'nt', reason='Windows open-reader sharing semantics')
def test_call_record_commit_survives_a_concurrent_windows_reader(tmp_path, monkeypatch):
    from astrophotoflow.core import files as core_files
    settings = Settings('127.0.0.1', 8190, tmp_path, (), workspace=tmp_path)
    prompt, call = (uuid4(), uuid4())
    save_software_call(settings, prompt, call, make_record(settings, prompt, call))
    completed = make_record(settings, prompt, call, state='completed', result_registered=True)
    pauses = []
    with call_record_path(settings, prompt, call).open('rb') as reader:

        def release_reader(delay):
            pauses.append(delay)
            reader.close()
        monkeypatch.setattr(core_files.time, 'sleep', release_reader)
        save_software_call(settings, prompt, call, completed)
    assert pauses == [0.05]
    persisted = read_software_call(settings, prompt, call)
    assert persisted.state == 'completed' and persisted.result_registered

def test_platform_full_graph_snapshot_route_is_removed(tmp_path):
    settings = Settings('127.0.0.1', 8190, tmp_path, (), workspace=tmp_path)
    app = create_app(settings, 'token')
    prompt = uuid4()

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', headers={'Authorization': 'Bearer token'}) as client:
            response = await client.post(f'/internal/native/runs/{prompt}/snapshot', json={'workflow': {'nodes': []}})
            assert response.status_code == 404
    asyncio.run(scenario())
    assert not (settings.workspace / 'runs' / str(prompt) / 'calculation-snapshot.json').exists()

def test_native_call_is_idempotent_and_not_a_public_execution_route(tmp_path, monkeypatch):
    settings = Settings('127.0.0.1', 8190, tmp_path, (), workspace=tmp_path)
    app = create_app(settings, 'token')
    app.state.database = None
    definition = NodeDefinition.model_validate(bundles.release('siril')['nodes'][0])
    operation = bundles.operation(settings.workspace, 'siril', 'autostretch', True, None)
    monkeypatch.setattr(software_calls, '_binding', lambda *_args: (definition, operation, {}))
    from types import SimpleNamespace
    monkeypatch.setattr(software_calls, 'get_definition', lambda *_args: SimpleNamespace(definition=definition))
    monkeypatch.setattr(software_calls, 'get_bundle_metadata', lambda *_args: ({}, [{'operation': {'operation_id': definition.execution.operation_id}, 'automatic_result_preview': True}], {}))
    executed = []

    async def run(_app, _settings, body, *, admission_lock):
        executed.append(body.call_id)
        path = call_record_path(settings, body.prompt_id, body.call_id)
        value = read_software_call(_settings, body.prompt_id, body.call_id)
        value.state = 'completed'
        value.result_registered = True
        save_software_call(_settings, body.prompt_id, body.call_id, value)
    monkeypatch.setattr(software_calls, 'execute_native_call', run)
    body = {'call_id': str(uuid4()), 'prompt_id': str(uuid4()), 'node_id': '3', 'workflow_id': str(uuid4()), 'calculation_signature': 'a' * 64, 'inputs': {definition.inputs[0].name: {'kind': 'asset', 'asset_id': str(uuid4()), 'selection': {'kind': 'whole_file'}}}, 'definition_id': str(uuid4()), 'definition_token': 'test', 'parameters': {'linked': True, 'shadowsclip': -2.8, 'targetbg': 0}}

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            path = '/internal/native/bundles/calls'
            assert (await client.post(path, json=body)).status_code == 401
            headers = {'Authorization': 'Bearer token'}
            assert (await client.post(path, json={**body, 'work_directory': 'C:/arbitrary'}, headers=headers)).status_code == 422
            first = await client.post(path, json=body, headers=headers)
            assert first.status_code == 200
            await asyncio.gather(*app.state.software_calls.values())
            second = await client.post(path, json=body, headers=headers)
            assert second.status_code == 200 and second.json()['state'] == 'completed'
            assert len(executed) == 1
            changed = await client.post(path, json={**body, 'parameters': {**body['parameters'], 'targetbg': 0.4}}, headers=headers)
            assert changed.status_code == 409
    asyncio.run(scenario())
    assert not any(('/internal/native/siril' in path for path in app.openapi()['paths']))
    assert not (settings.workspace / 'runs' / body['prompt_id'] / 'calculation-snapshot.json').exists()

def test_process_completion_is_not_published_before_scientific_output_checks(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from threading import Event
    from types import SimpleNamespace
    from pathlib import Path
    import numpy as np
    from astropy.io import fits
    from astrophotoflow.contracts.inputs import ResolvedInputs, ResolvedOutputInput
    from astrophotoflow.contracts.software import NativeBundleCall, ProducedFile, SoftwareObservation, SoftwareResult
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    definition = NodeDefinition.model_validate(bundles.release('siril')['nodes'][0])
    operation = bundles.operation(settings.workspace, 'siril', 'autostretch', True, None)
    prompt_id, call_id = (uuid4(), uuid4())
    source = tmp_path / 'original.fit'
    fits.writeto(source, np.ones((5, 7), dtype=np.float32))
    body = NativeBundleCall(call_id=call_id, prompt_id=prompt_id, node_id='3', definition_id=definition.definition_id, definition_token='fixed-definition', inputs={'image': {'kind': 'asset', 'asset_id': uuid4(), 'selection': {'kind': 'whole_file'}}}, parameters={item.name: item.default for item in definition.parameters})
    item = ResolvedOutputInput(calibration_status='Unknown', kind='run_output', reference_index=0, locator={'kind': 'run_output', 'run_id': prompt_id, 'execution_id': uuid4(), 'output_index': 0}, read_path=source, format='fits', selection={'kind': 'whole_file'}, byte_size=source.stat().st_size, content_hash='fixture', mtime_ns=source.stat().st_mtime_ns, scientific_metadata={'selected_hdu': 0})
    monkeypatch.setattr(software_calls, 'resolve_canvas_input_groups', lambda *_args, **_kwargs: {'image/0': ResolvedInputs(input_mode='reproducible', items=[item], required_copy_bytes=0, copied_bytes=0)})
    checking, release = (Event(), Event())
    actual_check = software_calls.check_output

    def check(*args, **kwargs):
        checking.set()
        assert release.wait(5)
        return actual_check(*args, **kwargs)
    monkeypatch.setattr(software_calls, 'check_output', check)
    monkeypatch.setattr(software_calls, 'render_output_preview', lambda *_args, **_kwargs: None)

    async def invoke(_settings, invocation, observe):
        work = invocation.work_directory
        work.mkdir(parents=True)
        target = work / 'result.fit'
        fits.writeto(target, np.full((5, 7), 0.25, dtype=np.float32))
        now = datetime.now(timezone.utc)
        await observe(SoftwareObservation(run_id=prompt_id, node_execution_id='3', call_id=call_id, observed_at=now, active=False, runtime_ref=None, state='completed'))
        return SoftwareResult(call_id=call_id, state='completed', started_at=now, ended_at=now, exit_code=0, outputs={'image': [ProducedFile(path=target, format='fits', frame_count=1)]}, log_path=None, error=None)
    monkeypatch.setattr(software_calls, 'invoke_operation', invoke)
    record = SoftwareCallRecord(request=body, state='starting', definition=definition, operation=operation, parameters=body.parameters, bundle=SoftwareCallBundle(version=None, commit=None), output_display='direct')
    path = call_record_path(settings, prompt_id, call_id)
    save_software_call(settings, prompt_id, call_id, record)

    async def scenario():
        task = asyncio.create_task(software_calls.execute_native_call(None, settings, body))
        for _ in range(500):
            if checking.is_set():
                break
            if task.done():
                await task
                raise AssertionError('Output checking did not begin')
            await asyncio.sleep(0.001)
        pending = read_software_call(settings, prompt_id, call_id)
        assert pending.state == 'running' and pending.outputs == []
        release.set()
        await task
        completed = read_software_call(settings, prompt_id, call_id)
        assert completed.state == 'completed' and len(completed.outputs) == 1
        assert get_checked_result(settings, prompt_id, call_id).ports[0].members[0].checked.path.name == 'result.fit'
    try:
        asyncio.run(scenario())
    finally:
        release.set()

def test_completed_json_record_serves_summary_analysis_and_full_file(tmp_path):
    from datetime import datetime, timezone
    from astrophotoflow.contracts.software import SoftwareObservation
    from astrophotoflow.modules.data.public import check_output
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    app = create_app(settings, 'token')
    prompt, call, workflow = (uuid4(), uuid4(), uuid4())
    work = tmp_path / 'runs' / str(prompt) / 'work' / str(call)
    work.mkdir(parents=True)
    analysis = work / 'analysis.json'
    analysis.write_text(json.dumps([{'kind': 'metrics', 'title': 'mean', 'source': 'fixture', 'values': {'mean': 0}}]), encoding='utf-8')
    checked = check_output(settings, run_directory=work, path=analysis, expected_format='other')
    observed = SoftwareObservation(run_id=prompt, node_execution_id='3', call_id=call, observed_at=datetime.now(timezone.utc), active=False, runtime_ref=None, state='completed', log_path=work / 'siril.log')
    record = make_record(settings, prompt, call, operation_id='stat', state='completed', observation=observed, result_registered=True)
    record.request.workflow_id = workflow
    save_software_call(settings, prompt, call, record)
    publish_checked_result(settings, CheckedResult(run_id=prompt, execution_id=call, source_kind='software', ports=[CheckedResultPort(name='analysis', type='APF_ANALYSIS', members=[CheckedResultMember(checked=checked, name=checked.path.name)])]))

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', headers={'Authorization': 'Bearer token'}) as client:
            base = f'/api/v1/runs/{prompt}/calls/{call}'
            summary = await client.get(base)
            assert summary.status_code == 200
            assert summary.json()['workflow_id'] == str(workflow) and summary.json()['observation']['run_id'] == str(prompt)
            values = await client.get(base + '/outputs/0/members/0/analysis')
            assert values.status_code == 200 and values.json()[0]['values']['mean'] == 0
            member = summary.json()['ports'][0]['members'][0]
            assert member['name'] == 'analysis.json' and member['format'] == 'other'
            assert member['view_base'].endswith('/outputs/0/members/0')
            download = await client.get(member['file_url'].removeprefix('/astrophotoflow'))
            assert download.status_code == 200 and download.content == analysis.read_bytes()
    asyncio.run(scenario())

@pytest.mark.asyncio
async def test_checked_presentation_fields_are_shared_by_http_and_mcp(tmp_path, monkeypatch):
    import numpy as np
    from astropy.io import fits
    from fastmcp import Client
    from astrophotoflow.contracts.bundles import AnalysisResult
    from astrophotoflow.contracts.software import SoftwareCallResult
    from astrophotoflow.interfaces.mcp import lifespan
    from astrophotoflow.interfaces.mcp.server import build_tool_catalog
    from astrophotoflow.modules.data.public import check_output, get_result_member
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    app = create_app(settings, 'token')
    prompt, call = (uuid4(), uuid4())
    work = tmp_path / 'runs' / str(prompt) / 'work' / str(call)
    work.mkdir(parents=True)
    image = work / 'image.fit'
    fits.writeto(image, np.full((6, 8), 0.4, dtype=np.float32))
    report = work / 'report.json'
    reports = [AnalysisResult(kind='histogram', title='Histogram', source='fixture', unit='count', output='image', histogram={'channel': 'composite', 'intensity_unit': 'ADU', 'edges': [0.0, 1.0], 'counts': [48]}), AnalysisResult(kind='table', title='Quality', source='fixture', output='image', columns=['Score'], rows=[[5]], row_positions=[{'member_index': 0}])]
    report.write_text(json.dumps([value.model_dump(mode='json') for value in reports]), encoding='utf-8')
    record = make_record(settings, prompt, call, state='completed', result_registered=True)
    record.definition.execution.outputs['report'] = 'report'
    record.operation.outputs[0].role = 'result'
    record.operation.outputs.append(record.operation.outputs[0].model_copy(update={'name': 'report', 'type': 'APF_ANALYSIS', 'formats': ['other'], 'role': None}))
    save_software_call(settings, prompt, call, record)
    publish_checked_result(settings, CheckedResult(run_id=prompt, execution_id=call, source_kind='software', ports=[CheckedResultPort(name='image', type='APF_SCIENCE', members=[CheckedResultMember(checked=check_output(settings, run_directory=work, path=image, expected_format='fits'), name=image.name, display='auto', position_token='fixture-position')]), CheckedResultPort(name='report', type='APF_ANALYSIS', members=[CheckedResultMember(checked=check_output(settings, run_directory=work, path=report, expected_format='other'), name=report.name)])]))
    assert get_result_member(settings, prompt, call, 0, 0)[1].display == 'direct'
    base = f'/api/v1/runs/{prompt}/calls/{call}'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', headers={'Authorization': 'Bearer token'}) as client:
        http_summary = (await client.get(base)).json()
        http_analysis = (await client.get(base + '/outputs/1/members/0/analysis')).json()
    assert http_summary['ports'][0]['data_kind'] == 'image'
    assert http_summary['ports'][0]['role'] == 'result'
    assert http_summary['ports'][0]['members'][0]['position_token'] == 'fixture-position'
    assert http_analysis == [value.model_dump(mode='json') for value in reports]

    class Service:

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def get_run_call(self, *_):
            return SoftwareCallResult.model_validate_json(json.dumps(http_summary))

        def get_run_analysis(self, *_):
            return [AnalysisResult.model_validate(value) for value in http_analysis]
    monkeypatch.setattr(lifespan, 'AssetClient', Service)
    async with Client(build_tool_catalog()) as client:
        ids = {'prompt_id': str(prompt), 'call_id': str(call)}
        summary = await client.call_tool('software_calls_get_call', ids)
        analysis = await client.call_tool('software_calls_analysis', {**ids, 'output_index': 1, 'member_index': 0})
    assert summary.structured_content == http_summary
    assert analysis.structured_content['result'] == http_analysis

def test_recovery_reads_typed_invocation_from_persisted_json_without_reexecution(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from astrophotoflow.contracts.software import SoftwareInvocation, SoftwareObservation
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    prompt, call = (uuid4(), uuid4())
    invocation = SoftwareInvocation(run_id=prompt, node_execution_id='3', call_id=call, package_id='siril', version='1.4.4', operation_id='stat', operation_content_token='fixture', inputs={}, parameters={}, work_directory=tmp_path / 'work')
    observed = SoftwareObservation(run_id=prompt, node_execution_id='3', call_id=call, observed_at=datetime.now(timezone.utc), active=None, runtime_ref=None, state='unknown', log_path=tmp_path / 'work/siril.log')
    path = call_record_path(settings, prompt, call)
    save_software_call(settings, prompt, call, make_record(settings, prompt, call, operation_id='stat', state='unknown', invocation=invocation, observation=observed))
    inspected = []

    async def inspect(_settings, request, previous):
        assert request == invocation and previous == observed
        inspected.append(request.call_id)
        return previous
    monkeypatch.setattr(software_calls, 'inspect_operation', inspect)
    asyncio.run(software_calls.recover_software_calls(settings))
    assert inspected == [call] and read_software_call(settings, prompt, call).state == 'unknown'
