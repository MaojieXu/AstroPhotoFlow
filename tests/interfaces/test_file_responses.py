import asyncio
import pytest
from astrophotoflow.interfaces.http.responses import LeasedFileResponse

@pytest.mark.parametrize('failure', [None, OSError, asyncio.CancelledError])
def test_file_delivery_releases_lease_on_completion_disconnect_and_cancel(tmp_path, failure):
    path = tmp_path / 'result.bin'
    path.write_bytes(b'checked-result')
    released, delivered = ([], [])
    response = LeasedFileResponse(path, lambda: released.append(True), media_type='application/octet-stream')

    async def receive():
        return {'type': 'http.request', 'body': b''}

    async def send(message):
        if message['type'] == 'http.response.body':
            if failure:
                raise failure()
            delivered.append(message['body'])

    async def deliver():
        await response({'type': 'http', 'method': 'GET', 'headers': [], 'extensions': {}, 'asgi': {'version': '3.0', 'spec_version': '2.4'}}, receive, send)
    if failure:
        with pytest.raises(failure):
            asyncio.run(deliver())
    else:
        asyncio.run(deliver())
        assert b''.join(delivered) == b'checked-result'
    assert released == [True]
