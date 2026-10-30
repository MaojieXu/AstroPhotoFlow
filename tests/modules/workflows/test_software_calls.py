import asyncio
import json
from uuid import uuid4

import httpx

from astrophotoflow.core.config import Settings
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.workflows import software_calls
from astrophotoflow.modules.software import bundles
from astrophotoflow.contracts.nodes import NodeDefinition


def test_native_call_is_idempotent_and_not_a_public_execution_route(tmp_path, monkeypatch):
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    app = create_app(settings, "token")
    definition = NodeDefinition.model_validate(bundles.release('siril')['nodes'][0])
    operation = bundles.operation(settings.workspace, 'siril', 'autostretch', True, None)
    monkeypatch.setattr(software_calls, "_binding", lambda *_args: (definition, operation, {}))
    executed = []

    async def run(_app, _settings, body):
        executed.append(body.call_id)
        path = software_calls._record_path(settings, body.prompt_id, body.call_id)
        value = json.loads(path.read_text(encoding="utf-8"))
        value["state"] = "completed"
        software_calls._save(path, value)

    monkeypatch.setattr(software_calls, "_run", run)
    body = {"call_id": str(uuid4()), "prompt_id": str(uuid4()), "node_id": "3",
            "reference": {"kind": "asset_version", "asset_version_id": str(uuid4()), "selection": {"kind": "whole_file"}},
            "definition_id": str(uuid4()), "definition_token":"test", "parameters": {"linked": True, "shadowsclip": -2.8, "targetbg": 0}}

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            path = "/internal/native/bundles/calls"
            assert (await client.post(path, json=body)).status_code == 401
            headers = {"Authorization": "Bearer token"}
            assert (await client.post(path, json={**body, "work_directory": "C:/arbitrary"}, headers=headers)).status_code == 422
            first = await client.post(path, json=body, headers=headers)
            assert first.status_code == 200
            await asyncio.gather(*app.state.siril_calls.values())
            second = await client.post(path, json=body, headers=headers)
            assert second.status_code == 200 and second.json()["state"] == "completed"
            assert len(executed) == 1
            changed = await client.post(path, json={**body, "parameters": {**body["parameters"], "targetbg":0.4}}, headers=headers)
            assert changed.status_code == 409
    try:
        asyncio.run(scenario())
        assert not any("/internal/native/siril" in path for path in app.openapi()["paths"])
    finally:
        app.state.database.close()


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
    prompt_id, call_id = uuid4(), uuid4()
    source = tmp_path / 'original.fit'; fits.writeto(source, np.ones((5, 7), dtype=np.float32))
    body = NativeBundleCall(call_id=call_id, prompt_id=prompt_id, node_id='3', definition_id=definition.definition_id,
                            definition_token='fixed-definition', inputs={'image': {'kind': 'asset_version', 'asset_version_id': uuid4(), 'selection': {'kind': 'whole_file'}}},
                            parameters={item.name: item.default for item in definition.parameters})
    item = ResolvedOutputInput(kind='run_output', reference_index=0, locator={'kind': 'run_output', 'run_id': prompt_id, 'node_execution_id': 'source', 'output_index': 0},
                               read_path=source, format='fits', selection={'kind': 'whole_file'}, byte_size=source.stat().st_size,
                               content_hash='fixture', mtime_ns=source.stat().st_mtime_ns, scientific_metadata={'selected_hdu': 0})
    monkeypatch.setattr(software_calls, 'resolve_canvas_inputs', lambda *_args, **_kwargs: ResolvedInputs(
        input_mode='reproducible', items=[item], required_copy_bytes=0, copied_bytes=0))
    checking, release = Event(), Event()
    actual_check = software_calls.check_output

    def check(*args, **kwargs):
        checking.set()
        assert release.wait(5)
        return actual_check(*args, **kwargs)

    monkeypatch.setattr(software_calls, 'check_output', check)
    monkeypatch.setattr(software_calls, 'render_output_preview', lambda *_args, **_kwargs: None)

    async def invoke(_settings, invocation, observe):
        work = invocation.work_directory; work.mkdir(parents=True)
        target = work / 'result.fit'; fits.writeto(target, np.full((5, 7), .25, dtype=np.float32))
        now = datetime.now(timezone.utc)
        await observe(SoftwareObservation(run_id=prompt_id, node_execution_id='3', call_id=call_id, observed_at=now,
                                          active=False, runtime_ref=None, state='completed'))
        return SoftwareResult(call_id=call_id, state='completed', started_at=now, ended_at=now, exit_code=0,
                              outputs={'image': [ProducedFile(path=target, format='fits', frame_count=1)]}, log_path=None, error=None)

    monkeypatch.setattr(software_calls, 'invoke_operation', invoke)
    record = {'request': body.model_dump(mode='json'), 'state': 'starting', 'definition': definition.model_dump(mode='json'),
              'operation': operation.model_dump(mode='json'), 'parameters': body.parameters, 'bundle': {'version': None, 'commit': None},
              'invocation': None, 'observation': None, 'result': None, 'ports': [], 'outputs': [], 'images': [],
              'output_display': 'direct', 'error': None, 'preview_error': None}
    path = software_calls._record_path(settings, prompt_id, call_id)
    software_calls._save(path, record)

    async def scenario():
        task = asyncio.create_task(software_calls._run(SimpleNamespace(state=SimpleNamespace(database=None)), settings, body))
        for _ in range(500):
            if checking.is_set():
                break
            if task.done():
                await task
                raise AssertionError('Output checking did not begin')
            await asyncio.sleep(.001)
        pending = software_calls._read(settings, prompt_id, call_id)
        assert pending['state'] == 'running' and pending['outputs'] == []
        release.set()
        await task
        completed = software_calls._read(settings, prompt_id, call_id)
        assert completed['state'] == 'completed' and len(completed['outputs']) == 1
        assert Path(completed['ports'][0]['files'][0]['path']).name == 'result.fit'

    try:
        asyncio.run(scenario())
    finally:
        release.set()
