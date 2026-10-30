import json
import os
import psutil
import pytest
from importlib.resources import files
from astrophotoflow.modules.software import bundles, public
from astrophotoflow.contracts.software import SoftwarePackageState


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
        for name, entry in zip(release['manifest']['operations'], release['operations'], strict=True):
            write(name, entry)
        for name, entry in zip(release['manifest']['nodes'], release['nodes'], strict=True):
            write(name, entry)
        vendor = files('astrophotoflow').joinpath('vendor')
        for field, vendor_name in [('commands', 'siril-1.4.4-commands.json'), ('assessments', 'siril-1.4.4-command-assessments.json')]:
            name = release['manifest'].get(field)
            if name is not None:
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                content = release.get('reference_files', {}).get(name)
                destination.write_bytes(content.encode('utf-8') if content is not None else vendor.joinpath(vendor_name).read_bytes())
        executable = root / release['manifest']['executable']
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b'fixture executable')
        (root / 'adapter').mkdir()
        (root / 'adapter/siril.py').write_text('''from pathlib import Path
import json
from astrophotoflow.contracts.bundles import ProcessPlan
def build_plan(operation_id,sources,parameters,directory,*,preview=False,prepare_sample=False):
    (directory/'parameters.json').write_text(json.dumps(parameters))
    (directory/'siril.ini').write_text('[core]\\n')
    outputs=[directory/('result.fit' if preview else f'autostretch-{i:06d}.fit') for i in range(len(sources))]
    rows=['load "'+p.as_posix()+'"' for p in sources]
    if prepare_sample: rows.append('save "'+(directory/'linear.fit').as_posix()+'"')
    rows.extend('save "'+p.as_posix()+'"' for p in outputs)
    script=directory/'operation.ssf'
    script.write_text('\\n'.join(rows))
    return ProcessPlan(arguments=['-i',str(directory/'siril.ini'),'-s',str(script)],outputs=outputs,output_format='fits',linear_sample=directory/'linear.fit' if prepare_sample else None)
''', encoding='utf-8')
        (root.parent / 'bundle-lock.json').write_text(json.dumps({'commit': 'fixture', 'bundle_version': release['manifest']['bundle_version']}))
        (root.parent / 'native-load.json').write_text(json.dumps({'commit': 'fixture', 'ready': True,
            'pid': os.getpid(), 'create_time': psutil.Process().create_time(), 'nodes': {}}))
        public._write_package_state(settings, 'siril', SoftwarePackageState(
            installed_version='1.4.4', install_path=root/'app', availability='ready', reason=None,
            operation='install', operation_state='completed', phase=None, progress=None,
            last_error=None, node_definition_ids=[]))
        return root
    return install
