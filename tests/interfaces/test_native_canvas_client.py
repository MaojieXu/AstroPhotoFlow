import asyncio
from uuid import uuid4

import httpx
import pytest

from astrophotoflow.core.errors import ApiError
from astrophotoflow.interfaces.native.client import NativeClient


def test_native_canvas_reuses_the_owner_client_and_validates_json_ids():
    operation,page,workflow,graph=uuid4(),uuid4(),uuid4(),uuid4()
    seen=[]
    def serve(request):
        seen.append(request)
        return httpx.Response(200,json={'operation_id':str(operation),'page_id':str(page),'workflow_id':str(workflow),'graph_id':str(graph),'applied':None,'node_id':None,'error':None})
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as http:
            client=NativeClient(http,'http://native','secret')
            assert (await client.receipt(operation)).operation_id==operation
            assert (await client.receipt(operation)).applied is None
            assert not http.is_closed
            assert 'secret' not in repr(client)
        assert http.is_closed
    asyncio.run(scenario())
    assert len(seen)==2 and all(request.headers['authorization']=='Bearer secret' for request in seen)


@pytest.mark.parametrize('reply',[httpx.Response(200,json={}),httpx.Response(200,text='not json'),httpx.Response(503,json={})])
def test_native_malformed_reply_is_unknown_and_never_replayed(reply):
    seen=[]
    def serve(request):seen.append(request);return reply
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as http:
            with pytest.raises(ApiError) as error:
                await NativeClient(http,'http://native','token').list_pages()
            assert error.value.status_code==503 and error.value.code=='CANVAS_CONNECTION_UNKNOWN'
    asyncio.run(scenario());assert len(seen)==1


def test_native_structured_conflict_and_field_diagnostics_are_preserved():
    async def scenario():
        response=httpx.Response(409,json={'error':{'code':'CANVAS_TARGET_CHANGED','message':'Changed','fields':[{'path':'content_token','message':'Stale'}]}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _request:response)) as http:
            with pytest.raises(ApiError) as error:
                await NativeClient(http,'http://native','token').list_pages()
            assert error.value.code=='CANVAS_TARGET_CHANGED' and error.value.fields==[{'path':'content_token','message':'Stale'}]
    asyncio.run(scenario())


def test_unknown_canvas_write_is_never_replayed_and_queries_the_original_receipt():
    from astrophotoflow.contracts.canvas import CanvasGraphRequest, NativeCanvasGraphCommand
    operation,page,workflow,graph=uuid4(),uuid4(),uuid4(),uuid4()
    command=NativeCanvasGraphCommand(request=CanvasGraphRequest(operation_id=operation,page_id=page,workflow_id=workflow,graph_id=graph,
        content_token='fixed',edit={'action':'delete_node','node_id':'1'}))
    seen=[]
    def serve(request):
        seen.append(request)
        if request.method=='POST':raise httpx.ReadTimeout('Reply lost',request=request)
        return httpx.Response(200,json={'operation_id':str(operation),'page_id':str(page),'workflow_id':str(workflow),'graph_id':str(graph),'applied':None,'node_id':None,'error':None})
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as http:
            client=NativeClient(http,'http://native','token')
            with pytest.raises(ApiError) as error:await client.send(command)
            assert error.value.code=='CANVAS_CONNECTION_UNKNOWN'
            assert (await client.receipt(operation)).applied is None
    asyncio.run(scenario())
    assert [request.method for request in seen]==['POST','GET']
    assert seen[1].url.path.endswith('/requests/'+str(operation))
