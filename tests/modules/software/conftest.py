import json
import os

import psutil
import pytest

import astrophotoflow.modules.software.packages.state as software_packages_state
from astrophotoflow.contracts.software import SoftwarePackageState
from astrophotoflow.modules.software import bundles


@pytest.fixture(autouse=True)
def synthetic_catalog(synthetic_bundle_catalog):
    """Historical test identifiers are labels, not the real Siril release content."""


@pytest.fixture
def bundle_install():
    def install(settings):
        release = bundles.release('siril')
        root = settings.workspace / 'software/siril/bundle'
        root.mkdir(parents=True)
        def write(name, value):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding='utf-8')
        write('bundle.json', release['manifest'])
        for locale, name in release['manifest'].get('locales', {}).items():
            write(name, release['localizations'][locale])
        for name, entry in zip(release['manifest']['operations'], release['operations'], strict=True):
            write(name, entry)
        for name, entry in zip(release['manifest']['nodes'], release['nodes'], strict=True):
            write(name, entry)
        for field in ('commands', 'assessments'):
            name = release['manifest'].get(field)
            if name is not None:
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(release['reference_files'][name], encoding='utf-8')
        executable = root / release['manifest']['executable']
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b'fixture executable')
        (root / 'adapter').mkdir()
        (root / 'adapter/siril.py').write_text('''from pathlib import Path
import json
from astrophotoflow.contracts.bundles import NamedProcessPlan, ProcessOutput, BundleFile, BundleProgress
def build_plan(operation_id,sources,parameters,directory,*,preview=False,prepare_sample=False,**options):
    sources = sources["image"]
    (directory/'parameters.json').write_text(json.dumps(parameters))
    (directory/'siril.ini').write_text('[core]\\n')
    outputs=[directory/('result.fit' if preview else f'autostretch-{i:06d}.fit') for i in range(len(sources))]
    rows=['load "'+p.as_posix()+'"' for p in sources]
    if prepare_sample: rows.append('save "'+(directory/'linear.fit').as_posix()+'"')
    rows.extend('save "'+p.as_posix()+'"' for p in outputs)
    script=directory/'operation.ssf'
    script.write_text('\\n'.join(rows))
    return NamedProcessPlan(arguments=['-i',str(directory/'siril.ini'),'-s',str(script)],temporary_directory=directory/'tmp',outputs={'image': ProcessOutput(files=[BundleFile(path=p,format='fits') for p in outputs])},linear_sample=directory/'linear.fit' if prepare_sample else None)
def parse_result(*args): pass
def parse_progress(text): return BundleProgress()
def parse_failure(log_path): return log_path.read_text(errors='replace')
''', encoding='utf-8')
        (root.parent / 'bundle-lock.json').write_text(json.dumps({'commit': 'fixture', 'bundle_version': release['manifest']['bundle_version']}))
        (root.parent / 'native-load.json').write_text(json.dumps({'commit': 'fixture', 'ready': True,
            'pid': os.getpid(), 'create_time': psutil.Process().create_time(), 'nodes': {}}))
        software_packages_state.write_package_state(settings, 'siril', SoftwarePackageState(
            installed_version='1.4.4', install_path=root/'app', availability='ready', reason=None,
            operation='install', operation_state='completed', phase=None, progress=None,
            last_error=None, node_definition_ids=[]))
        return root
    return install
