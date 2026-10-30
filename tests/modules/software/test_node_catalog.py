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
    try:
        asyncio.run(scenario())
    finally:
        app.state.database.close()


def test_removed_bundle_operation_keeps_definition_and_reports_missing_capability(tmp_path, bundle_install):
    settings = Settings('127.0.0.1', 8190, tmp_path/'data', (), workspace=tmp_path)
    root = bundle_install(settings)
    definition = bundles.metadata(tmp_path, 'siril')[2][0]
    (tmp_path/'nodes').mkdir()
    saved_path = tmp_path/'nodes'/f"{definition['definition_id']}.json"
    saved_path.write_text(json.dumps(definition), encoding='utf-8')
    manifest = json.loads((root/'bundle.json').read_text(encoding='utf-8'))
    manifest.update(operations=[], nodes=[], output_nodes=[])
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
    try:
        asyncio.run(scenario())
    finally:
        app.state.database.close()


def test_canvas_graph_write_and_inspect_use_current_target_without_handoff(tmp_path, monkeypatch):
    from uuid import uuid4
    from astrophotoflow.modules.workflows import canvas
    settings=Settings('127.0.0.1',8190,tmp_path,(),workspace=tmp_path)
    app=create_app(settings,'token')
    forwarded=[]
    async def native(request, method, path, body):
        forwarded.append(body)
        return {k: body['request'][k] for k in ('operation_id','page_id','workflow_id','graph_id')} | dict(applied=True,node_id=None,error=None,graph={'nodes':[]},content_token='new')
    monkeypatch.setattr(canvas,'_native',native)
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
    try:
        asyncio.run(scenario())
    finally:
        app.state.database.close()
