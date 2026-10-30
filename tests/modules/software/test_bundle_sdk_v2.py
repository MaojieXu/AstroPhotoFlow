import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from astrophotoflow.contracts.bundles import AnalysisResult, BundleFile, BundleManifest, NamedProcessPlan, ProcessOutput
from astrophotoflow.contracts.software import SoftwareObservation
from astrophotoflow.modules.software import bundles, public


def test_named_result_collection_parses_files_and_rejects_outside_paths(tmp_path, monkeypatch):
    workspace = tmp_path / 'workspace'
    root = workspace / 'software/siril/bundle'; root.mkdir(parents=True)
    (root.parent / 'bundle-lock.json').write_text('{"commit":"fixture-v2"}', encoding='utf-8')
    manifest = BundleManifest.model_validate({**bundles.release('siril')['manifest'], 'host_api': 2})
    monkeypatch.setattr(bundles, 'metadata', lambda *_args: (manifest, [], []))
    work = workspace / 'runs/work'; work.mkdir(parents=True)
    image = work / 'result.fit'; image.write_bytes(b'candidate scientific output')
    analysis = work / 'analysis.json'
    parsed = []

    def parse(operation_id, directory, plan, log):
        parsed.append(operation_id)
        value = AnalysisResult(kind='metrics', title='noise', source='test program', values={'noise': 0})
        analysis.write_text(json.dumps([value.model_dump(mode='json')]), encoding='utf-8')

    monkeypatch.setattr(bundles, '_adapter', lambda *_args: SimpleNamespace(parse_result=parse))
    plan = NamedProcessPlan(arguments=['operation'], temporary_directory=work / 'tmp', outputs={
        'image': ProcessOutput(files=[BundleFile(path=image, format='fits')]),
        'analysis': ProcessOutput(files=[BundleFile(path=analysis, format='other')]),
    })
    result = bundles.collect_result(workspace, 'siril', 'measure', plan, work, work / 'process.log')
    assert parsed == ['measure']
    assert result.outputs['image'][0].path == image
    assert json.loads(analysis.read_text(encoding='utf-8'))[0]['values']['noise'] == 0
    outside = workspace / 'outside.txt'; outside.write_text('protected', encoding='utf-8')
    plan.outputs['image'] = ProcessOutput(files=[BundleFile(path=outside, format='other')])
    with pytest.raises(ValueError, match='escapes'):
        bundles.collect_result(workspace, 'siril', 'measure', plan, work, work / 'process.log')


@pytest.mark.parametrize('reused_child', [False, True])
def test_cancel_observes_only_the_owned_process_family(tmp_path, monkeypatch, reused_child):
    call_id = uuid4()
    executable = str(tmp_path / 'owned-program.exe')
    terminated = []

    class Process:
        def __init__(self, pid, created):
            self.pid, self.created, self.alive = pid, created, True
        def create_time(self):
            return self.created
        def exe(self):
            return executable
        def is_running(self):
            return self.alive
        def children(self, recursive=True):
            return [] if reused_child else [child]
        def terminate(self):
            terminated.append(self.pid)
            self.alive = False

    parent, child, unrelated = Process(9101, 1), Process(9102, 3 if reused_child else 2), Process(9103, 9)
    processes = {item.pid: item for item in [parent, child, unrelated]}
    monkeypatch.setattr(public.psutil, 'Process', lambda pid: processes[pid])
    monkeypatch.setattr(public.psutil, 'wait_procs', lambda _processes, timeout: ([], []))

    class Handle:
        pid = parent.pid
        returncode = None
        def terminate(self):
            parent.terminate()
            self.returncode = -15
        async def wait(self):
            return self.returncode

    observation = SoftwareObservation(run_id=uuid4(), node_execution_id='3', call_id=call_id,
        observed_at=datetime.now(timezone.utc), state='running', active=True,
        runtime_ref={'pid': parent.pid, 'create_time': 1, 'executable': executable})
    call = public._Call(SimpleNamespace(call_id=call_id), observation, process=Handle())
    if reused_child:
        call.descendants[child.pid] = 2
    monkeypatch.setitem(public._CALLS, call_id, call)
    result = asyncio.run(public.cancel_operation(call_id))
    assert result.request_state == 'sent' and result.stop_state == 'stopped'
    assert parent.pid in terminated
    assert unrelated.alive and unrelated.pid not in terminated
    assert child.alive is reused_child
    assert (child.pid in terminated) is not reused_child
