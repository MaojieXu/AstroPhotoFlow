"""Real scientific executor boundaries; native queue closure has a separate browser test."""

import asyncio
import hashlib
import json
import os
import time
from pathlib import Path
from uuid import uuid4
from dataclasses import dataclass

import blake3
import numpy as np
import pytest
from astropy.io import fits
from pydantic import TypeAdapter

from astrophotoflow.contracts.bundles import AnalysisResult
from astrophotoflow.contracts.inputs import ResolvedOutputInput
from astrophotoflow.contracts.software import SoftwareInvocation, SoftwareResult, SoftwareCancelResult
from astrophotoflow.core.config import load_running_settings
from astrophotoflow.modules.data.public import check_output
from astrophotoflow.modules.software import public

pytestmark = pytest.mark.skipif(not os.environ.get('APF_TEST_SIRIL_SCIENCE_WORKSPACE'), reason='Explicit isolated real Siril opt-in')


@dataclass(frozen=True)
class ScientificRun:
    result: SoftwareResult
    invocation: SoftwareInvocation
    cancellation: SoftwareCancelResult | None = None


@pytest.fixture(scope='module')
def science():
    root = Path(__file__).resolve().parents[2]
    workspace = Path(os.environ['APF_TEST_SIRIL_SCIENCE_WORKSPACE']).resolve()
    assert workspace == (root / '.artifacts/workspaces/modernization-current').resolve()
    settings = load_running_settings(workspace)
    package = public.get_package(settings, 'siril')
    assert package.effective_version == '1.4.4' and package.effective_availability == 'ready'
    directory = workspace / 'input' / ('g7-science-' + uuid4().hex)
    directory.mkdir(parents=True)
    yy, xx = np.mgrid[:128, :128]
    stars = np.full((128, 128), 0.05, dtype=np.float32)
    rng = np.random.default_rng(31)
    centers = []
    while len(centers) < 30:
        y, x = rng.uniform(12, 116, 2)
        if all((y - cy)**2 + (x - cx)**2 > 81 for cy, cx in centers):
            centers.append((y, x))
    for y, x in centers:
        amplitude = rng.uniform(0.15, 0.5)
        sigma = rng.uniform(1.2, 1.8)
        stars += (amplitude * np.exp(-((xx - x)**2 + (yy - y)**2) / (2 * sigma**2))).astype(np.float32)
    stars += rng.normal(0, 0.0001, stars.shape).astype(np.float32)
    paths = []
    for index, shift in enumerate(((0, 0), (1, 2), (-1, 1), (2, -1))):
        path = directory / f'light-{index}.fits'
        fits.writeto(path, np.roll(stars, shift, axis=(0, 1)), fits.Header({'IMAGETYP': 'Light Frame', 'EXPTIME': 10.0}))
        paths.append(path)
    masters = {}
    for name, value in [('bias', 0.01), ('dark', 0.005), ('flat', 1.0)]:
        path = directory / (name + '.fits')
        fits.writeto(path, np.full_like(stars, value), fits.Header({'IMAGETYP': 'Master ' + name, 'EXPTIME': 10.0}))
        masters[name] = path
    originals = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in [*paths, *masters.values()]}
    report = root / '.artifacts/reports/modernization/g7'

    def invoke(operation_id, supplied, *, parameters=None, runtime=None, cancel_when_started=False, observe_seqprofile_unknown=False):
        run_id, call_id = uuid4(), uuid4()
        operation = public.get_operation(settings, 'siril', '1.4.4', operation_id)
        values = {parameter.name: parameter.default for parameter in operation.parameters}
        values.update(parameters or {})
        if 'runtime' in values:
            values['runtime'] = json.dumps({'threads': 2, **(runtime or {})})
        inputs = {}
        for name, files in supplied.items():
            inputs[name] = [ResolvedOutputInput(
                kind='run_output', reference_index=0,
                locator={'kind': 'run_output', 'run_id': run_id, 'execution_id': uuid4(), 'output_index': 0, 'member_index': index},
                read_path=path, format='fits', selection={'kind': 'whole_file'}, byte_size=path.stat().st_size,
                content_hash='blake3:' + blake3.blake3(path.read_bytes()).hexdigest(), mtime_ns=path.stat().st_mtime_ns,
                scientific_metadata={'selected_hdu': 0},
            ) for index, path in enumerate(files)]
        invocation = SoftwareInvocation(run_id=run_id, call_id=call_id, node_execution_id='science-boundary',
            package_id='siril', version='1.4.4', operation_id=operation_id, operation_content_token=operation.content_token,
            bundle_commit=package.effective_bundle_commit, development_source=package.development_source,
            inputs=inputs, parameters=values, work_directory=workspace / 'runs' / str(run_id) / 'work' / str(call_id))
        observations = []
        cancellation = None

        async def observe(value):
            nonlocal cancellation
            observations.append(value)
            if cancel_when_started and cancellation is None and value.active and value.runtime_ref:
                cancellation = await public.cancel_operation(call_id)

        result = asyncio.run(public.invoke_operation(settings, invocation, observe))
        (report / f'siril-science-{operation_id}-{call_id}.json').write_text(json.dumps({
            'boundary': 'direct scientific executor, not a native graph run',
            'invocation': invocation.model_dump(mode='json'), 'result': result.model_dump(mode='json'),
            'last_observation': observations[-1].model_dump(mode='json') if observations else None,
            'cancellation': cancellation.model_dump(mode='json') if cancellation else None,
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        if observe_seqprofile_unknown and result.state == 'unknown':
            assert operation_id == 'seqprofile'
            assert result.exit_code == 0 and result.error is None
            assert observations[-1].active is True and observations[-1].runtime_ref
            later=[]
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                observation=asyncio.run(public.inspect_operation(settings,invocation,observations[-1]))
                later.append(observation.model_dump(mode='json'))
                if observation.active is False:
                    break
                time.sleep(0.1)
            (report/f'siril-science-{operation_id}-{call_id}-stop-observations.json').write_text(
                json.dumps(later,ensure_ascii=False,indent=2),encoding='utf-8')
            assert observation.active is False
            pytest.xfail('Siril1.4.4 Windows seqprofile: parent exited 0 while tracked Python children remained active; original unknown retained, later stop verified without replay')
        assert observations[-1].active is False
        return ScientificRun(result, invocation, cancellation)

    yield settings, paths, masters, invoke
    assert {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in originals} == originals


def assert_images(settings, result, invocation, count):
    assert result.state == 'completed' and result.exit_code == 0, result.error
    assert len(result.outputs['image']) == count
    for output in result.outputs['image']:
        checked = check_output(settings, run_directory=invocation.work_directory, path=output.path, expected_format='fits')
        assert checked.byte_size > 0
        pixels = fits.getdata(output.path)
        assert pixels.shape == (128, 128) and np.isfinite(pixels).all()


def test_real_calibration(science):
    settings, paths, masters, invoke = science
    run = invoke('calibrate_single', {'image': [paths[0]], **{name: [path] for name, path in masters.items()}}, parameters={'bias_mode': 'image'})
    result, invocation = run.result, run.invocation
    assert_images(settings, result, invocation, 1)
    expected = fits.getdata(paths[0]) - 0.015
    np.testing.assert_allclose(fits.getdata(result.outputs['image'][0].path), expected, atol=2e-6)


def test_real_registration_stack_and_rejection_maps(science):
    settings, paths, _, invoke = science
    run = invoke('register', {'image': paths})
    registered, registration = run.result, run.invocation
    assert_images(settings, registered, registration, 4)
    run = invoke('stack', {'image': [file.path for file in registered.outputs['image']]},
        parameters={'rejection_maps': 'separate', 'force_32bit': True})
    stacked, stacking = run.result, run.invocation
    assert_images(settings, stacked, stacking, 1)
    assert len(stacked.outputs['rejection_maps']) == 2
    for item in stacked.outputs['rejection_maps']:
        assert np.isfinite(fits.getdata(item.path)).all()


def test_real_single_frame_sequence_and_analysis(science):
    settings, paths, _, invoke = science
    run = invoke('seqstat', {'image': [paths[0]]})
    result, invocation = run.result, run.invocation
    assert_images(settings, result, invocation, 1)
    assert len(result.outputs['analysis']) == 1
    analysis = TypeAdapter(list[AnalysisResult]).validate_json(result.outputs['analysis'][0].path.read_bytes())
    assert any(panel.rows for panel in analysis)


def test_real_compressed_output(science):
    settings, paths, _, invoke = science
    run = invoke('autostretch', {'image': [paths[0]]}, runtime={'compression': {'enabled': True, 'type': 'gzip2', 'quantisation': 0}})
    result, invocation = run.result, run.invocation
    assert_images(settings, result, invocation, 1)
    assert result.outputs['image'][0].path.name.endswith('.fit.fz')


def test_real_siril_process_cancellation(science):
    _, paths, _, invoke = science
    run = invoke('autostretch', {'image': paths * 25}, cancel_when_started=True)
    assert run.cancellation is not None
    assert run.cancellation.request_state == 'sent'
    assert run.cancellation.stop_state == 'stopped'
    assert run.result.state == 'cancelled'
    assert run.result.exit_code is not None
    assert all(not files for files in run.result.outputs.values())


def test_real_missing_starnet_dependency_is_not_an_empty_success(science):
    _, paths, _, invoke = science
    run = invoke('starnet', {'image': [paths[0]]})
    assert run.result.state == 'failed'
    assert run.result.exit_code != 0 and run.result.error is not None
    diagnostic = ' '.join(field['message'] for field in run.result.error.fields).lower()
    assert 'starnet' in diagnostic
    assert all(not files for files in run.result.outputs.values())


def test_real_seqprofile_records_its_actual_outcome_without_masking_failure(science):
    settings, paths, _, invoke = science
    run = invoke('seqprofile', {'image': [paths[0]]}, observe_seqprofile_unknown=True)
    if run.result.state != 'completed':
        assert run.result.exit_code is not None and run.result.exit_code != 0
        assert run.result.error is not None
        pytest.xfail(f'Siril1.4.4 Windows seqprofile: actual exit {run.result.exit_code}; report and original log retained')
    assert_images(settings, run.result, run.invocation, 1)
    panels = TypeAdapter(list[AnalysisResult]).validate_json(run.result.outputs['analysis'][0].path.read_bytes())
    assert any(panel.rows for panel in panels)
