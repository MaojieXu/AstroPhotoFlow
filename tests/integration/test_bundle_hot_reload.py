import os
from pathlib import Path
import subprocess

import pytest


def test_native_bundle_install_edit_remove_without_restarting(tmp_path):
    python = os.environ.get("APF_NATIVE_PYTHON")
    if not python:
        pytest.skip("Set APF_NATIVE_PYTHON to the prepared native interpreter.")
    repo = Path(__file__).resolve().parents[2]
    script = '''import asyncio,json,os,shutil,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,sys.argv[1])
from comfy.cli_args import args
args.cpu=True
import nodes
from aiohttp import web
from astrophotoflow.core.config import Settings
from astrophotoflow.interfaces.native.bundles import catalog as native
from astrophotoflow.interfaces.native.bundles.watcher import watch_bundle_nodes
from astrophotoflow.modules.nodes.public import list_definitions
from importlib.resources import files
workspace=Path(sys.argv[2])
os.environ['APF_WORKSPACE']=str(workspace)
settings=Settings('127.0.0.1',8190,workspace/'data',(),workspace=workspace)
native.load_running_settings=lambda _path:settings
release=json.loads(files('astrophotoflow').joinpath('vendor/bundle-catalog.json').read_text(encoding='utf-8'))['siril']
native.subprocess.run=lambda *a,**kw:SimpleNamespace(returncode=0,stdout=release['manifest']['version_output'])
root=workspace/'software/siril/bundle'
events=[]
notifications=asyncio.Queue()
pending_edits=[]
async def send(name,value):
 events.append(name)
 if pending_edits:
  path,content=pending_edits.pop()
  path.write_text(json.dumps(content),encoding="utf-8")
 notifications.put_nowait(name)
async def scenario():
 server=SimpleNamespace(apf_bundle_lock=asyncio.Lock(),send_json=send,loop=asyncio.get_running_loop(),app=web.Application())
 await native.reload_bundle_nodes(server)
 await notifications.get()
 def write(name,value):
  path=root/name
  path.parent.mkdir(parents=True,exist_ok=True)
  path.write_text(json.dumps(value),encoding='utf-8')
 write('bundle.json',release['manifest'])
 for locale,name in release['manifest'].get('locales',{}).items():write(name,release['localizations'][locale])
 for name,value in zip(release['manifest']['operations'],release['operations'],strict=True):write(name,value)
 for name,value in zip(release['manifest']['nodes'],release['nodes'],strict=True):write(name,value)
 executable=root/release['manifest']['executable']
 executable.parent.mkdir(parents=True,exist_ok=True)
 executable.write_bytes(b'fixture')
 adapter=root/release['manifest']['adapter']
 adapter.parent.mkdir(parents=True,exist_ok=True)
 adapter.write_text('fixture',encoding='utf-8')
 (root.parent/'bundle-lock.json').write_text(json.dumps({'commit':'fixture','bundle_version':release['manifest']['bundle_version']}))
 await native.reload_bundle_nodes(server)
 await notifications.get()
 saved=next(item for item in list_definitions(workspace) if item.definition.execution.operation_id=='autostretch')
 key=saved.native_type
 original=nodes.NODE_CLASS_MAPPINGS[key]
 assert original.GET_SCHEMA().category=='siril'
 assert original.GET_NODE_INFO_V1()['python_module']=='custom_nodes.siril'
 assert json.loads((root.parent/'native-load.json').read_text())['ready']
 watch_bundle_nodes(server)
 operation=root/release['manifest']['operations'][0]
 changed=json.loads(operation.read_text(encoding='utf-8'))
 changed['operation']['parameters'][2]['default']=0.3
 followup=json.loads(json.dumps(changed))
 followup['operation']['parameters'][2]['default']=0.4
 pending_edits.append((operation,followup))
 operation.write_text(json.dumps(changed),encoding='utf-8')
 await asyncio.wait_for(notifications.get(),timeout=10)
 assert nodes.NODE_CLASS_MAPPINGS[key] is not original
 assert nodes.NODE_CLASS_MAPPINGS[key].definition.parameters[2].default==0.3
 assert next(item for item in list_definitions(workspace) if item.definition.execution.operation_id=='autostretch').definition.parameters[2].default==0.3
 await asyncio.wait_for(notifications.get(),timeout=10)
 assert nodes.NODE_CLASS_MAPPINGS[key].definition.parameters[2].default==0.4
 assert next(item for item in list_definitions(workspace) if item.definition.execution.operation_id=='autostretch').definition.parameters[2].default==0.4
 server.app.freeze()
 await server.app.cleanup()
 updated_manifest=dict(release['manifest'],bundle_version='0.3.0-dev.1')
 write('bundle.json',updated_manifest)
 (root.parent/'bundle-lock.json').write_text(json.dumps({'commit':'updated-fixture','bundle_version':'0.3.0-dev.1'}))
 await native.reload_bundle_nodes(server)
 assert json.loads((root.parent/'native-load.json').read_text())['commit']=='updated-fixture'
 assert nodes.NODE_CLASS_MAPPINGS[key].definition.parameters[2].default==0.4
 manifest=dict(updated_manifest,operations=[],nodes=[],output_nodes=[],locales={})
 write('bundle.json',manifest)
 await native.reload_bundle_nodes(server)
 assert key not in nodes.NODE_CLASS_MAPPINGS and list_definitions(workspace)
 science=workspace/'science.fit'
 workflow=workspace/'workflow.json'
 science.write_bytes(b'original')
 workflow.write_text('{}')
 assert root.resolve().is_relative_to(workspace.resolve())
 shutil.rmtree(root)
 await native.reload_bundle_nodes(server)
 assert key not in nodes.NODE_CLASS_MAPPINGS
 assert list_definitions(workspace) and science.read_bytes()==b'original' and workflow.exists()
 assert events==['apf.bundles_changed']*7
 print('BUNDLE_HOT_RELOAD_OK')
asyncio.run(scenario())
'''
    result = subprocess.run([python, "-c", script, str(repo / "engine/ComfyUI"), str(tmp_path)],
        capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(repo / "src")}, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "BUNDLE_HOT_RELOAD_OK" in result.stdout
