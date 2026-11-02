import astrophotoflow.modules.software.packages.maintenance as software_packages_maintenance
import astrophotoflow.modules.software.execution.state as software_execution_state
import astrophotoflow.modules.software.execution.runner as software_runner
import astrophotoflow.modules.software.execution.processes as software_processes
import astrophotoflow.modules.software.bundles as software_bundles
import asyncio
import hashlib
import re
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from astrophotoflow.contracts.inputs import ResolvedOutputInput, ScienceSelection
from astrophotoflow.contracts.software import SoftwareInvocation, SoftwarePackageState
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software import public


@pytest.fixture
def configured(tmp_path, bundle_install):
    software_execution_state.CALLS.clear()
    software_packages_maintenance.PACKAGE_LOCKS.clear()
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    bundle_install(settings)
    yield settings
    software_execution_state.CALLS.clear()
    software_packages_maintenance.PACKAGE_LOCKS.clear()


def invocation(settings, count=2):
    run_id, call_id = uuid4(), uuid4()
    inputs = []
    for index in range(count):
        path = settings.workspace / "sources" / str(call_id) / f"original {index}.fit"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes([index + 1]) * 32)
        inputs.append(ResolvedOutputInput(
            kind="run_output", reference_index=0,
            locator={"kind": "run_output", "run_id": run_id, "execution_id": uuid4(), "output_index": 0, "member_index": index},
            read_path=path, format="fits", selection={"kind": "whole_file"},
            byte_size=path.stat().st_size, content_hash="fixture", mtime_ns=path.stat().st_mtime_ns, scientific_metadata={"selected_hdu": 0},
        ))
    return SoftwareInvocation(
        run_id=run_id, node_execution_id="3", call_id=call_id, package_id="siril", version="1.4.4", operation_id="autostretch",
        bundle_commit=public.get_package(settings, "siril").effective_bundle_commit,
        operation_content_token=public.get_operation(settings, "siril", "1.4.4", "autostretch").content_token,
        inputs={"image": inputs}, parameters={"linked": True, "shadowsclip": -2.8, "targetbg": 0, "runtime": "{}"},
        work_directory=settings.workspace / "runs" / str(run_id) / "work" / str(call_id),
    )


def process_factory(monkeypatch, exit_code=0, gated=False):
    created = []

    class Process:
        pid = 123
        returncode = None

        def __init__(self, script):
            self.script = script
            self.pid = 123 + len(created)
            self.gate = asyncio.Event()
            if not gated:
                self.gate.set()

        async def wait(self):
            await self.gate.wait()
            if self.returncode is None:
                targets = re.findall(r'^save "(.+)"$', self.script, flags=re.MULTILINE)
                for target in targets[:1] if exit_code else targets:
                    Path(target).write_bytes(b"complete science candidate")
                self.returncode = exit_code
            return self.returncode

        def terminate(self):
            self.returncode = -15
            self.gate.set()

    async def start(*args, **kwargs):
        assert kwargs["stdout"] is not None and "shell" not in kwargs
        process = Process(Path(args[-1]).read_text(encoding="utf-8"))
        process.executable = str(args[0])
        created.append(process)
        return process

    monkeypatch.setattr(software_runner.asyncio, "create_subprocess_exec", start)
    original_process = software_processes.psutil.Process
    def observed(pid=None):
        process = next((item for item in created if item.pid == pid), None)
        if process is None:
            return original_process(pid)
        return SimpleNamespace(pid=pid, create_time=lambda: float(pid), exe=lambda: process.executable,
                               children=lambda recursive=True: [], is_running=lambda: process.returncode is None)
    monkeypatch.setattr(software_processes.psutil, 'Process', observed)
    return created


def test_one_cli_call_preserves_order_parameters_and_originals(configured, monkeypatch):
    body = invocation(configured)
    hashes = [hashlib.sha256(item.read_path.read_bytes()).hexdigest() for item in body.inputs["image"]]
    created = process_factory(monkeypatch)
    observations = []

    async def observe(value):
        observations.append(value)

    result = asyncio.run(public.invoke_operation(configured, body, observe))
    assert result.state == "completed" and result.exit_code == 0
    assert len(created) == 1 and len(result.outputs["image"]) == 2
    script = created[0].script
    assert script.index("original 0.fit") < script.index("original 1.fit")
    import json
    assert json.loads((body.work_directory / "parameters.json").read_text()) == body.parameters
    assert [row.state for row in observations] == ["starting", "running", "completed"]
    assert observations[-1].active is False
    assert [hashlib.sha256(item.read_path.read_bytes()).hexdigest() for item in body.inputs["image"]] == hashes


def test_partial_nonzero_exit_is_not_reported_as_success(configured, monkeypatch):
    process_factory(monkeypatch, exit_code=9)

    async def observe(_value):
        pass

    result = asyncio.run(public.invoke_operation(configured, invocation(configured), observe))
    assert result.state == "failed" and result.exit_code == 9
    assert result.outputs["image"] == []
    assert result.error.code == "SOFTWARE_EXECUTION_FAILED"


@pytest.mark.parametrize('locale', ['en', 'zh'])
@pytest.mark.parametrize('failure_phase', ['running', 'completed'])
def test_observation_failures_use_localized_messages_and_preserve_diagnostics(configured, monkeypatch, locale, failure_phase):
    import json
    from astrophotoflow.core.localization import error_message
    path = configured.workspace / 'comfyui-user/default/comfy.settings.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'Comfy.Locale': locale}), encoding='utf-8')
    created = process_factory(monkeypatch)
    diagnostic = 'database locked 原始诊断 {unchanged}'
    failed = False
    async def observe(value):
        nonlocal failed
        if value.state == failure_phase and not failed:
            failed = True
            raise OSError(diagnostic)
    result = asyncio.run(public.invoke_operation(configured, invocation(configured), observe))
    key = 'observation_start_failed' if failure_phase == 'running' else 'observation_result_failed'
    assert result.error.code == 'OBSERVATION_FAILED'
    assert result.error.message == error_message(locale, '', key)
    assert result.error.fields == [{'path': 'diagnostic', 'message': diagnostic}]
    assert len(created) == 1


@pytest.mark.parametrize('failure_kind', ['observation', 'processing'])
def test_failure_after_exit_retains_the_observed_exit_code(configured, monkeypatch, failure_kind):
    from astrophotoflow.modules.software.execution import runner
    from astrophotoflow.modules.software.execution.state import ObservationFailed

    created = process_factory(monkeypatch)

    async def fail_after_exit(call, waiting, *_args):
        assert await waiting == 0
        assert call.process.returncode == 0
        if failure_kind == 'observation':
            raise ObservationFailed('record commit failed')
        raise ValueError('result processing failed')

    async def observe(_value):
        pass

    monkeypatch.setattr(runner, 'watch_process', fail_after_exit)
    result = asyncio.run(public.invoke_operation(configured, invocation(configured), observe))
    assert result.exit_code == 0
    assert result.state == ('unknown' if failure_kind == 'observation' else 'failed')
    assert result.error is not None
    assert len(created) == 1


@pytest.mark.parametrize('locale', ['en', 'zh'])
def test_nonzero_exit_preserves_raw_log_with_localized_summary(configured, monkeypatch, locale):
    import json
    from astrophotoflow.core.localization import error_message
    path = configured.workspace / 'comfyui-user/default/comfy.settings.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'Comfy.Locale': locale}), encoding='utf-8')
    process_factory(monkeypatch, exit_code=9)
    diagnostic = 'Siril original log 原文 {value}'
    monkeypatch.setattr(software_bundles, 'failure_reason', lambda *args: diagnostic)
    async def observe(value):
        pass
    result = asyncio.run(public.invoke_operation(configured, invocation(configured), observe))
    assert result.state == 'failed' and result.exit_code == 9
    assert result.error.message == error_message(locale, '', 'software_exit_failed', {'exit_code': 9})
    assert result.error.fields == [{'path': 'software_log', 'message': diagnostic}]


def test_cancel_only_target_call_and_allow_maintenance_while_running(configured, monkeypatch):
    bodies = [invocation(configured, 1), invocation(configured, 1)]
    created = process_factory(monkeypatch, gated=True)

    async def observe(_value):
        pass

    async def scenario():
        tasks = [asyncio.create_task(public.invoke_operation(configured, body, observe)) for body in bodies]
        while len(created) < 2:
            if any(task.done() for task in tasks):
                await asyncio.gather(*tasks)
            await asyncio.sleep(0)
        async with public.maintain_package("siril"):
            assert all(process.returncode is None for process in created)
        result = await public.cancel_operation(bodies[1].call_id)
        assert result.request_state == "sent" and result.stop_state == "stopped"
        assert created[0].returncode is None
        created[0].gate.set()
        first, second = await asyncio.gather(*tasks)
        assert first.state == "completed" and second.state == "cancelled"

    asyncio.run(scenario())


@pytest.mark.parametrize("change", ["token", "parameter", "hdu", "changed", "workdir", 'container'])
def test_rejects_invalid_invocation_before_launch(configured, monkeypatch, change):
    body = invocation(configured, 1)
    launched = process_factory(monkeypatch)
    if change == "token":
        body.operation_content_token = "obsolete"
    elif change == "parameter":
        body.parameters["targetbg"] = 2
    elif change == "hdu":
        body.inputs["image"][0].selection = ScienceSelection(kind="fits_hdu", hdu_index=1)
    elif change == "changed":
        body.inputs["image"][0].read_path.write_bytes(b"changed")
    elif change == 'container':
        body.inputs['image'][0].scientific_metadata = {'selected_hdu': 0, 'hdu_count': 2, 'frame_count': 2}
    else:
        body.work_directory = configured.workspace.parent

    async def observe(_value):
        pass

    with pytest.raises(ApiError):
        asyncio.run(public.invoke_operation(configured, body, observe))
    assert not launched


def test_uninstall_only_removes_program_and_keeps_science_and_definitions(configured):
    protected = [configured.workspace / "data/original.fit", configured.workspace / "nodes/custom.json", configured.workspace / "workflows/saved.json"]
    for path in protected:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"preserve")

    async def scenario():
        package = public.get_package(configured, "siril")
        async with public.maintain_package("siril"):
            result = await public.uninstall_package(configured, "siril", package.package_token)
        assert result.availability == "not_installed"

    asyncio.run(scenario())
    assert not (configured.workspace / "software/siril/app").exists()
    assert all(path.read_bytes() == b"preserve" for path in protected)

@pytest.mark.parametrize("category", ["fits", "xisf", "image", "raw"])
def test_static_image_formats_are_forwarded_to_siril(configured, monkeypatch, category):
    body = invocation(configured, count=1)
    body.inputs["image"][0] = body.inputs["image"][0].model_copy(update={"format": category})
    created = process_factory(monkeypatch)

    async def observe(_value):
        pass

    result = asyncio.run(public.invoke_operation(configured, body, observe))
    assert result.state == "completed"
    assert str(body.inputs["image"][0].read_path).replace("\\", "/") in created[0].script
    assert result.outputs["image"][0].format == "fits"


def test_non_fits_preview_uses_siril_decoder_and_reuses_unstretched_sample(configured, monkeypatch):
    source = configured.data_dir / "objects" / "source.tif"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"original image fixture")
    folder = configured.data_dir / "previews" / "sample"
    folder.mkdir(parents=True)
    scripts = []

    async def start(*args, **kwargs):
        assert Path(args[args.index("-i") + 1]).is_file()
        script = Path(args[-1]).read_text(encoding="utf-8")
        scripts.append(script)
        for target in re.findall(r'^save "(.+)"$', script, flags=re.MULTILINE):
            Path(target).write_bytes(b"Siril output fixture")
        class Process:
            returncode = 0
            async def wait(self):
                return 0
        return Process()

    monkeypatch.setattr(software_runner.asyncio, "create_subprocess_exec", start)
    parameters = SimpleNamespace(linked=True, shadowsclip=-2.8, targetbg=0.25)
    asyncio.run(public.preview_operation(configured, source, folder / str(uuid4()), vars(parameters), package_id="siril", operation_id="autostretch", prepare_sample=True))
    assert "linear.fit" in scripts[0]
    assert (folder / "sample.fit").is_file()
    asyncio.run(public.preview_operation(configured, folder / "sample.fit", folder / str(uuid4()), vars(parameters), package_id="siril", operation_id="autostretch"))
    assert scripts[1].count('save "') == 1
    assert source.read_bytes() == b"original image fixture"


def test_denied_initial_process_identity_never_claims_the_tree_has_stopped(configured,monkeypatch):
    body=invocation(configured)
    created=process_factory(monkeypatch)
    original=software_processes.psutil.Process
    def denied(pid=None):
        if any(process.pid==pid for process in created):raise software_processes.psutil.AccessDenied(pid)
        return original(pid)
    monkeypatch.setattr(software_processes.psutil,'Process',denied)
    observations=[]
    async def observe(value):observations.append(value)
    async def scenario():
        result=await public.invoke_operation(configured,body,observe)
        assert result.state=='unknown'
        assert observations[-1].active is None
        assert public.get_usage('siril')[0].state=='unknown'
        cancelled=await public.cancel_operation(body.call_id)
        assert cancelled.stop_state=='unknown'
    asyncio.run(scenario())
