"""Platform contracts use synthetic packages, versions and named ports."""
import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from astrophotoflow.contracts.bundles import BundleFile, BundleManifest, NamedProcessPlan, ProcessOutput
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software import bundles
from astrophotoflow.modules.software.execution import preview as previews
from astrophotoflow.modules.software.packages.catalog import get_command_catalog


@pytest.fixture
def sample_package(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[2] / 'fixtures/bundles/catalog.json'
    release = copy.deepcopy(json.loads(source.read_text(encoding='utf-8'))['siril'])
    release['manifest'].update(package_id='sample-tool', software_version='7.8.9')
    for operation in release['operations']:
        operation['operation'].update(package_id='sample-tool', version='7.8.9')
    for node in release['nodes']:
        node['execution']['package_id'] = 'sample-tool'
    entry = release['operations'][0]
    entry['operation']['inputs'][0]['name'] = 'source'
    entry['operation']['outputs'][0]['name'] = 'rendered'
    entry['preview'].update(input='source', output='rendered')
    path = tmp_path / 'catalog.json'

    def save():
        path.write_text(json.dumps({'sample-tool': release}), encoding='utf-8')
    save()
    monkeypatch.setenv('ASTROPHOTOFLOW_BUNDLE_CATALOG', str(path))
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    return settings, release, save


def test_commands_follow_bundle_identity_and_arbitrary_assessments(sample_package):
    settings, release, save = sample_package
    rows = get_command_catalog('sample-tool', '7.8.9', settings)
    assert rows[0].assessment == {'fixture': True}
    assert get_command_catalog('sample-tool', '7.8.9') == rows
    with pytest.raises(ApiError) as mismatch:
        get_command_catalog('sample-tool', '1.4.4', settings)
    assert mismatch.value.status_code == 404
    release['manifest']['assessments'] = None
    save()
    assert get_command_catalog('sample-tool', '7.8.9')[0].assessment == {}
    release['manifest']['commands'] = None
    save()
    with pytest.raises(ApiError) as missing:
        get_command_catalog('sample-tool', '7.8.9')
    assert missing.value.status_code == 404


def test_command_reference_uses_effective_installed_version(sample_package, tmp_path, monkeypatch):
    settings, release, _ = sample_package
    manifest = BundleManifest.model_validate({**release['manifest'], 'software_version': '8.0.0'})
    for name, text in release['reference_files'].items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    monkeypatch.setattr(bundles, 'metadata', lambda *_: (manifest, [], []))
    monkeypatch.setattr(previews.development, 'source_root', lambda *_: tmp_path)
    assert get_command_catalog('sample-tool', '8.0.0', settings)[0].command == 'fixture'
    with pytest.raises(ApiError):
        get_command_catalog('sample-tool', '7.8.9', settings)


def test_preview_ports_come_from_bundle_and_reject_missing_output(sample_package):
    settings, release, save = sample_package
    preview = previews.get_preview_definition(settings, 'sample-tool', 'autostretch')
    assert (preview.input, preview.output) == ('source', 'rendered')
    release['operations'][0]['preview']['output'] = 'missing'
    save()
    with pytest.raises(ValueError, match='input and output'):
        previews.get_preview_definition(settings, 'sample-tool', 'autostretch')


def test_immutable_snapshot_can_identify_a_sole_output_without_guessing_its_name(sample_package):
    settings, release, save = sample_package
    entry = release['operations'][0]
    del entry['preview']['output']
    save()
    assert previews.get_preview_definition(settings, 'sample-tool', 'autostretch').output == 'rendered'
    entry['operation']['outputs'].append({**entry['operation']['outputs'][0], 'name': 'secondary'})
    save()
    with pytest.raises(ValueError, match='input and output'):
        previews.get_preview_definition(settings, 'sample-tool', 'autostretch')


def test_retired_sample_caches_keep_directory_ownership_without_reusing_them(tmp_path):
    from astrophotoflow.modules.data.media.ownership import owned_preview_locations
    folder = tmp_path / 'previews' / 'retired'
    folder.mkdir(parents=True)
    (folder / 'manifest.json').write_text('{}', encoding='utf-8')
    (folder / 'old.fit').write_bytes(b'cached')
    row = SimpleNamespace(size='retired-sample-kind', storage_path='previews/retired/manifest.json')
    paths = owned_preview_locations(row, SimpleNamespace(data_dir=tmp_path))
    assert {Path(path).name for path in paths} == {'manifest.json', 'old.fit'}


@pytest.mark.parametrize('outside', [False, True])
def test_adapter_cannot_escape_preview_work_directory(sample_package, monkeypatch, outside):
    from astrophotoflow.modules.software.bundles import adapter
    settings, release, _ = sample_package
    work = settings.workspace / 'preview'
    manifest = BundleManifest.model_validate(release['manifest'])
    monkeypatch.setattr(adapter.development, 'source_root', lambda *_: settings.workspace)
    monkeypatch.setattr(adapter.development, 'identity', lambda *_: {'commit': 'fixture'})
    monkeypatch.setattr(adapter.development, 'content_fingerprint', lambda *_: 'fixture')
    monkeypatch.setattr(adapter, 'metadata', lambda *_: (manifest, [], []))
    target = settings.workspace / 'outside.fit' if outside else work / 'rendered.fit'
    plan = NamedProcessPlan(arguments=[], outputs={'rendered': ProcessOutput(files=[BundleFile(path=target, format='fits')])}, temporary_directory=work / 'tmp')
    monkeypatch.setattr(adapter, 'load_adapter', lambda *_: SimpleNamespace(build_plan=lambda *_args, **_kwargs: plan))
    if outside:
        with pytest.raises(ValueError, match='escapes'):
            adapter.adapter_plan(settings.workspace, 'sample-tool', 'autostretch', {}, {}, work)
    else:
        assert adapter.adapter_plan(settings.workspace, 'sample-tool', 'autostretch', {}, {}, work) == plan


@pytest.mark.parametrize('outcome', ['completed', 'source-changed', 'cancelled', 'missing-output'])
def test_preview_execution_uses_named_ports_and_preserves_source(sample_package, monkeypatch, outcome):
    settings, _release, _ = sample_package
    directory = settings.data_dir / 'previews' / 'sample' / str(uuid4())
    source = settings.workspace / 'original.tif'
    source.write_bytes(b'original')
    observed = []
    monkeypatch.setattr(previews, 'get_package', lambda *_: SimpleNamespace(effective_availability='ready', effective_reason=None))
    monkeypatch.setattr(previews.development, 'source_root', lambda *_: settings.workspace)

    def build(_workspace, _package, _operation, sources, parameters, work, **options):
        observed.append((sources, options))
        target = work / 'rendered.fit'
        return NamedProcessPlan(arguments=[], temporary_directory=work / 'tmp',
            outputs={} if outcome == 'missing-output' else {'rendered': ProcessOutput(files=[BundleFile(path=target, format='fits')])})
    monkeypatch.setattr(bundles, 'adapter_plan', build)
    process = SimpleNamespace(returncode=None)
    stopped = []

    def terminate():
        stopped.append(True)
        process.returncode = -1

    async def wait():
        if outcome == 'cancelled' and process.returncode is None:
            raise asyncio.CancelledError()
        if outcome == 'source-changed':
            source.write_bytes(b'changed source')
        (directory / 'rendered.fit').write_bytes(b'output')
        process.returncode = 0
        return 0
    process.wait, process.terminate = wait, terminate

    async def spawn(*_args, **_kwargs):
        return process
    monkeypatch.setattr(previews.asyncio, 'create_subprocess_exec', spawn)

    async def run():
        call = previews.preview_operation(settings, source, directory, {}, package_id='sample-tool', operation_id='autostretch', prepare_sample=True)
        if outcome == 'source-changed':
            with pytest.raises(ApiError) as error:
                await call
            assert error.value.code == 'SOURCE_CHANGED'
        elif outcome == 'cancelled':
            with pytest.raises(asyncio.CancelledError):
                await call
            assert stopped
        elif outcome == 'missing-output':
            with pytest.raises(ValueError, match='exactly one'):
                await call
        else:
            assert (await call).name == 'rendered.fit'
            assert source.read_bytes() == b'original'
    asyncio.run(run())
    assert observed[0][0] == {'source': [source]}
