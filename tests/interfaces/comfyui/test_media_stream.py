import asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from astrophotoflow.comfyui import proxy

def test_media_proxy_forwards_ranges_and_headers_without_waiting_for_whole_body(monkeypatch):

    async def run():
        finish = asyncio.Event()
        seen = {}

        async def stream(request):
            seen.update(request.headers)
            response = web.StreamResponse(status=206, headers={'Content-Type': 'video/mp4', 'Content-Length': '9', 'Content-Range': 'bytes 10-18/100', 'Accept-Ranges': 'bytes', 'ETag': '"fixed-original"', 'Set-Cookie': 'must-not-forward=1'})
            await response.prepare(request)
            await response.write(b'first')
            await finish.wait()
            await response.write(b'last')
            await response.write_eof()
            return response
        upstream_app = web.Application()
        upstream_app.router.add_get('/api/v1/library/assets/{asset_id}/previews/viewer/{key}/video', stream)
        upstream = TestClient(TestServer(upstream_app))
        await upstream.start_server()
        monkeypatch.setattr(proxy, '_configuration', lambda: (str(upstream.make_url('')).rstrip('/'), {'http://local-preview'}, 'server-token'))
        public_app = web.Application()
        routes = web.RouteTableDef()
        proxy.register_proxy_routes(routes)
        public_app.add_routes(routes)
        public = TestClient(TestServer(public_app))
        await public.start_server()
        try:
            response = await public.get('/astrophotoflow/api/v1/library/assets/a/previews/viewer/key/video', headers={'Origin': 'http://local-preview', 'Range': 'bytes=10-18', 'If-Range': '"fixed-original"', 'Cookie': 'private=1'})
            assert response.status == 206
            assert await asyncio.wait_for(response.content.readexactly(5), 2) == b'first'
            assert not finish.is_set()
            assert response.headers['Content-Range'] == 'bytes 10-18/100'
            assert response.headers['Accept-Ranges'] == 'bytes'
            assert 'Set-Cookie' not in response.headers
            assert seen['Range'] == 'bytes=10-18'
            assert seen['If-Range'] == '"fixed-original"'
            assert seen['Authorization'] == 'Bearer server-token'
            assert 'Cookie' not in seen
            finish.set()
            assert await response.read() == b'last'
        finally:
            finish.set()
            await public.close()
            await upstream.close()
    asyncio.run(run())
