import astrophotoflow.modules.software.packages.state as software_packages_state
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

import blake3
import numpy as np
import pytest
from astropy.io import fits

from astrophotoflow.contracts.inputs import ResolvedOutputInput
from astrophotoflow.contracts.software import SoftwareInvocation, SoftwarePackageState
from astrophotoflow.core.config import Settings
from astrophotoflow.modules.software import public


def test_real_native_category_paths_and_legacy_category():
    python = os.environ.get('APF_NATIVE_PYTHON')
    if not python:
        pytest.skip('Set APF_NATIVE_PYTHON to the prepared ComfyUI interpreter.')
    repo = Path(__file__).resolve().parents[2]
    script = '''import sys
sys.path.insert(0, sys.argv[1])
from comfy.cli_args import args
args.cpu = True
from astrophotoflow.interfaces.native.bundles.node import BundleNode
import math
assert math.isnan(BundleNode.fingerprint_inputs())
assert BundleNode.APF_AUTOMATIC_RESULT is False
from astrophotoflow.contracts.nodes import NodeDefinition
from astrophotoflow.contracts.software import SoftwareOperation
from astrophotoflow.modules.software.metadata import catalog
release = catalog()['siril']
raw = release['nodes'][0]
operation = SoftwareOperation.model_validate(dict(release['operations'][0]['operation'], ready=True, reason=None, content_token=''))
legacy = type('LegacyCategoryNode', (BundleNode,), {'definition': NodeDefinition.model_validate(raw), 'operation': operation})
assert legacy.GET_SCHEMA().category == 'siril'
definition = NodeDefinition.model_validate(dict(raw, category=['stretch-color', 'automatic-stretch'], name='Auto Stretch (autostretch)'))
current = type('CategorizedNode', (BundleNode,), {'definition': definition, 'operation': operation, 'search_aliases': ('Auto Stretch (autostretch)', '自动拉伸（autostretch）', 'autostretch')})
schema = current.GET_SCHEMA()
assert schema.category == 'siril/stretch-color/automatic-stretch'
assert schema.node_id == legacy.GET_SCHEMA().node_id
assert schema.display_name == 'Auto Stretch (autostretch)'
assert '自动拉伸（autostretch）' in schema.search_aliases
assert [port.id for port in schema.inputs] == [port.id for port in legacy.GET_SCHEMA().inputs]
'''
    result = subprocess.run([python, '-c', script, str(repo / 'engine/ComfyUI')],
                            env={**os.environ, 'PYTHONPATH': str(repo / 'src')}, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr


def test_real_native_v3_siril_schema():
    python = os.environ.get("APF_NATIVE_PYTHON")
    if not python:
        pytest.skip("Set APF_NATIVE_PYTHON to the prepared ComfyUI interpreter for this real native check.")
    repo = Path(__file__).resolve().parents[2]
    script = '''import sys,json
sys.path.insert(0, sys.argv[1])
from comfy.cli_args import args
args.cpu=True
from astrophotoflow.interfaces.native.bundles.node import BundleNode
from importlib.resources import files
catalog=lambda:json.loads(files('astrophotoflow').joinpath('vendor/bundle-catalog.json').read_text(encoding='utf-8'))
from astrophotoflow.contracts.nodes import NodeDefinition
from astrophotoflow.contracts.software import SoftwareOperation
SirilAutostretchNode=type("TestBundleNode",(BundleNode,),{"definition":NodeDefinition.model_validate(catalog()["siril"]["nodes"][0]),"output_node":True,"operation":SoftwareOperation.model_validate({**catalog()["siril"]["operations"][0]["operation"], "content_token":"fixture", "ready":True})})
schema=SirilAutostretchNode.GET_SCHEMA()
import asyncio
from types import SimpleNamespace
import astrophotoflow.interfaces.native.bundles.node as adapter
SirilAutostretchNode.hidden=SimpleNamespace(extra_pnginfo=None)
sessions=[]
async def request(session, method, path, body=None):
    assert session._loop is asyncio.get_running_loop() and not session.closed
    sessions.append(session)
    return {"state":"completed","images":[],"outputs":[{}],"preview_error":None,"ports":[],"operation":{"package_id":"siril","version":"1.4.4","operation_id":"autostretch"},"bundle":{"version":"0.1.2-dev.1","commit":"test"}}
adapter._request=request
adapter.get_executing_context=lambda:SimpleNamespace(prompt_id="00000000-0000-4000-8000-000000000001",node_id="65",list_index=0)
for _ in range(2):
    asyncio.run(SirilAutostretchNode.execute(image={},linked=False,shadowsclip=-2.8,targetbg=0.25))
assert len(sessions)==2 and sessions[0] is not sessions[1] and all(session.closed for session in sessions)
print("APF_SCHEMA="+json.dumps({"id":schema.node_id,"inputs":SirilAutostretchNode.INPUT_TYPES(),"outputs":SirilAutostretchNode.RETURN_TYPES,"object_info":SirilAutostretchNode.GET_NODE_INFO_V1()}))
'''
    env = {**os.environ, "PYTHONPATH": str(repo / "src")}
    result = subprocess.run([python, "-c", script, str(repo / "engine/ComfyUI")], capture_output=True, text=True, env=env, timeout=120)
    assert result.returncode == 0, result.stderr
    line = next(line for line in result.stdout.splitlines() if line.startswith("APF_SCHEMA="))
    schema = json.loads(line.removeprefix("APF_SCHEMA="))
    assert schema["id"] == "APF_169de0837f814cdea3295541ecacf463"
    assert schema["inputs"]["required"]["image"][0] == "APF_SCIENCE"
    shadows = schema["inputs"]["required"]["shadowsclip"][1]
    assert shadows["min"] < -1e100 and shadows["max"] > 1e100
    background = schema["inputs"]["required"]["targetbg"][1]
    assert background["min"] == 0 and background["max"] == 1
    assert schema["outputs"] == ["APF_SCIENCE"]
    assert schema["object_info"]["python_module"] == "custom_nodes.astrophotoflow"
    assert schema["object_info"]["python_module"].split(".")[0] == "custom_nodes"


def test_real_siril_autostretch_two_members_and_original_integrity(tmp_path):
    source_app = os.environ.get("APF_TEST_SIRIL_BUNDLE")
    if not source_app:
        pytest.skip("Set APF_TEST_SIRIL_BUNDLE to a verified complete bundle checkout.")
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    bundle = tmp_path / "software/siril/bundle"
    shutil.copytree(source_app, bundle, ignore=shutil.ignore_patterns(".git"))
    app = bundle / "app"
    import psutil
    commit = subprocess.check_output(['git', '-c', 'safe.directory=' + str(Path(source_app).resolve()), '-C', source_app, 'rev-parse', 'HEAD'], text=True).strip()
    manifest = json.loads((bundle / 'bundle.json').read_text(encoding='utf-8'))
    (bundle.parent/"bundle-lock.json").write_text(json.dumps({"commit":commit,"bundle_version":manifest['bundle_version']}))
    (bundle.parent/"native-load.json").write_text(json.dumps({"commit":commit,"ready":True,"pid":os.getpid(),"create_time":psutil.Process().create_time()}))
    software_packages_state.write_package_state(settings, "siril", SoftwarePackageState(
        installed_version="1.4.4", install_path=app, availability="ready", reason=None,
        operation="install", operation_state="completed", phase=None, progress=None, last_error=None, node_definition_ids=[],
    ))
    prepared = public.prepare_package(settings, "siril")
    assert prepared.package.availability == "ready"
    run_id, call_id = uuid4(), uuid4()
    inputs, hashes = [], []
    for index in range(2):
        path = tmp_path / f"original-{index}.fit"
        pixels = np.linspace(0.001 + index * 0.001, 0.05, 1024, dtype=np.float32).reshape(32, 32)
        fits.writeto(path, pixels)
        hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
        inputs.append(ResolvedOutputInput(
            kind="run_output", reference_index=0,
            locator={"kind": "run_output", "run_id": run_id, "execution_id": uuid4(), "output_index": 0, "member_index": index},
            read_path=path, format="fits", selection={"kind": "whole_file"}, byte_size=path.stat().st_size,
            content_hash="blake3:" + blake3.blake3(path.read_bytes()).hexdigest(), mtime_ns=path.stat().st_mtime_ns,
            scientific_metadata={"selected_hdu": 0},
        ))
    from types import SimpleNamespace
    from astrophotoflow.contracts.data_nodes import NativeDataExecute
    from astrophotoflow.contracts.inputs import OutputLocator
    from astrophotoflow.modules.data.public import execute_data_node, data_execution_directory, resolve_result_inputs
    data_id = uuid4()
    data_directory = data_execution_directory(settings, run_id, data_id)
    data_directory.mkdir(parents=True)
    for index, original in enumerate(inputs):
        np.save(data_directory / f'input-{index:06}.npy', fits.getdata(original.read_path), allow_pickle=False)
    data_result = execute_data_node(None, settings, NativeDataExecute(run_id=run_id, execution_id=data_id,
                               node_id='source-data', image_count=2, input_dtype='float32'))
    data_inputs, supporting = resolve_result_inputs(settings,run_id,data_result.output,'APF_SCIENCE')
    assert len(data_inputs) == 2 and not supporting
    data_hashes = [hashlib.sha256(item.read_path.read_bytes()).hexdigest() for item in data_inputs]
    body = SoftwareInvocation(
        run_id=run_id, call_id=call_id, node_execution_id="3", package_id="siril", version="1.4.4", operation_id="autostretch",
        operation_content_token=public.get_operation(settings, "siril", "1.4.4", "autostretch").content_token,
        bundle_commit=prepared.package.bundle_commit, inputs={"image": data_inputs},
        parameters={**{parameter.name: parameter.default for parameter in public.get_operation(settings, "siril", "1.4.4", "autostretch").parameters},
                    "linked": True, "shadowsclip": -2.8, "targetbg": 0.25},
        work_directory=tmp_path / "runs" / str(run_id) / "work" / str(call_id),
    )
    observations = []

    async def observe(value):
        observations.append(value)

    result = asyncio.run(public.invoke_operation(settings, body, observe))
    assert result.state == "completed", result.log_path.read_text(encoding="utf-8", errors="replace")
    assert result.exit_code == 0 and len(result.outputs["image"]) == 2
    assert [item.path.relative_to(body.work_directory).as_posix() for item in result.outputs["image"]] == ["member-000000/result.fit", "member-000001/result.fit"]
    for output in result.outputs["image"]:
        with fits.open(output.path) as hdus:
            assert hdus[0].data.shape == (32, 32) and np.isfinite(hdus[0].data).all()
    assert [hashlib.sha256(item.read_path.read_bytes()).hexdigest() for item in inputs] == hashes
    assert [hashlib.sha256(item.read_path.read_bytes()).hexdigest() for item in data_inputs] == data_hashes
    assert observations[-1].active is False
