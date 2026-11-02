from astrophotoflow.modules.software import metadata as bundle_metadata
import asyncio
import json
from uuid import UUID
import httpx
from astrophotoflow.core.config import Settings
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.software import bundles


def test_http_node_directory_uses_same_definition_parameters_and_help(tmp_path, bundle_install):
    settings = Settings('127.0.0.1', 8190, tmp_path/'data', (), workspace=tmp_path)
    bundle_install(settings)
    definitions = bundles.metadata(settings.workspace, 'siril')[2]
    (tmp_path/'nodes').mkdir()
    definition = definitions[0]
    (tmp_path/'nodes'/f"{definition['definition_id']}.json").write_text(json.dumps(definition))
    app = create_app(settings, 'node-test')
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            assert (await client.get('/api/v1/nodes')).status_code == 401
            headers={'Authorization':'Bearer node-test'}
            values=(await client.get('/api/v1/nodes', headers=headers)).json()
            assert len(values)==1 and values[0]['available']
            assert values[0]['node']['native_type']=='APF_'+UUID(definition['definition_id']).hex
            assert values[0]['operation']['parameters']==values[0]['node']['definition']['parameters']
            assert values[0]['help'] and values[0]['examples']
            assert values[0]['preview']['kind']=='science-image'
            detail=(await client.get('/api/v1/nodes/'+definition['definition_id'], headers=headers)).json()
            assert detail==values[0]
            assert (await client.get('/api/v1/nodes?query=unmatched', headers=headers)).json()==[]
    asyncio.run(scenario())


def test_removed_bundle_operation_keeps_definition_and_reports_missing_capability(tmp_path, bundle_install):
    settings = Settings('127.0.0.1', 8190, tmp_path/'data', (), workspace=tmp_path)
    root = bundle_install(settings)
    definition = bundles.metadata(tmp_path, 'siril')[2][0]
    (tmp_path/'nodes').mkdir()
    saved_path = tmp_path/'nodes'/f"{definition['definition_id']}.json"
    saved_path.write_text(json.dumps(definition), encoding='utf-8')
    manifest = json.loads((root/'bundle.json').read_text(encoding='utf-8'))
    manifest.update(operations=[], nodes=[], output_nodes=[], locales={})
    (root/'bundle.json').write_text(json.dumps(manifest), encoding='utf-8')
    app = create_app(settings, 'node-test')

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', headers={'Authorization': 'Bearer node-test'}) as client:
            response = await client.get('/api/v1/nodes')
            assert response.status_code == 200
            capability = response.json()[0]
            assert not capability['available'] and capability['operation'] is None
            assert capability['reason'] and capability['node']['definition']['definition_id'] == definition['definition_id']
            assert saved_path.exists()
    asyncio.run(scenario())


def test_canvas_graph_write_and_inspect_use_current_target_without_handoff(tmp_path, monkeypatch):
    from uuid import uuid4
    from astrophotoflow.interfaces.http import canvas
    from astrophotoflow.interfaces.application.canvas import CanvasDependencies
    from astrophotoflow.contracts.canvas import CanvasAddResult
    from types import SimpleNamespace
    settings=Settings('127.0.0.1',8190,tmp_path,(),workspace=tmp_path)
    app=create_app(settings,'token')
    forwarded=[]
    async def native(command):
        body=command.model_dump(mode='json')
        forwarded.append(body)
        return CanvasAddResult.model_validate_json(json.dumps({k: body['request'][k] for k in ('operation_id','page_id','workflow_id','graph_id')} | dict(applied=True,node_id=None,error=None,graph={'nodes':[]},content_token='new')))
    app.dependency_overrides[canvas.canvas_dependencies]=lambda:CanvasDependencies(settings,None,SimpleNamespace(send=native))
    body={k:str(uuid4()) for k in ('operation_id','page_id','workflow_id','graph_id')} | dict(content_token='current',edit={'action':'inspect'})
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Authorization':'Bearer token'}) as client:
            result=await client.post('/api/v1/canvas/graph',json=body)
            assert result.status_code==200 and result.json()['graph']=={'nodes':[]}
            write=body | {'edit':{'action':'set_parameter','node_id':4,'name':'targetbg','value':.3}}
            assert (await client.post('/api/v1/canvas/graph',json=write)).status_code==200
            assert len(forwarded)==2
            assert forwarded[-1]['request']['edit']==write['edit']
            assert (await client.post('/api/v1/canvas/graph',json=write,headers={'Authorization':'Bearer wrong'})).status_code==401
            assert len(forwarded)==2
    asyncio.run(scenario())


def test_full_node_catalogue_reads_bundle_metadata_per_package(tmp_path, monkeypatch, bundle_install):
    from uuid import uuid4
    from astrophotoflow.modules.nodes.public import list_nodes
    settings = Settings('127.0.0.1', 8190, tmp_path/'data', (), workspace=tmp_path)
    root = bundle_install(settings)
    template = bundles.metadata(tmp_path, 'siril')[2][0]
    directory = tmp_path/'nodes'; directory.mkdir()
    for index in range(160):
        definition = json.loads(json.dumps(template))
        definition.update(definition_id=str(uuid4()), name=f'Operation {index}', source='custom')
        (directory/(definition['definition_id']+'.json')).write_text(json.dumps(definition), encoding='utf-8')
    reads = []
    original = bundle_metadata.read_bundle
    def read(path):
        reads.append(path)
        return original(path)
    monkeypatch.setattr(bundle_metadata, 'read_bundle', read)
    values = list_nodes(settings)
    assert len(values) == 160 and all(value.available for value in values)
    assert len(reads) <= 8
