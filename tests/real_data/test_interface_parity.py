"""Real HTTP handlers, typed client, MCP protocol and generated CLI commands."""

import asyncio
import json

from fastmcp import Client

from astrophotoflow.interfaces.cli import generated
from astrophotoflow.interfaces.mcp import lifespan
from astrophotoflow.interfaces.mcp.server import build_tool_catalog


def test_http_cli_mcp_cross_writes_and_revision_errors(real_library, imported_group, real_http, real_client_factory, monkeypatch, capsys):
    asset = real_library.assets(imported_group)[0]
    monkeypatch.setattr(lifespan, 'AssetClient', real_client_factory)
    server = build_tool_catalog()
    monkeypatch.setattr(generated, 'CLIENT_SPEC', server)
    generated.app([
        'call-tool', 'data_assets_update', '--asset-id', asset.id,
        '--expected-revision', str(asset.revision),
        '--changes', json.dumps({'calibration_status': 'UnCalibrated', 'calibration_reason': 'CLI authored declaration.'}),
    ], exit_on_error=False)
    cli_receipt = json.loads(capsys.readouterr().out)
    assert cli_receipt['asset']['calibration_status'] == 'UnCalibrated'
    response = real_http.get(f'/api/v1/library/assets/{asset.id}')
    assert response.status_code == 200
    updated = response.json()
    assert updated['calibration_evidence']['reason'] == 'CLI authored declaration.'

    async def edit_and_read():
        async with Client(server) as client:
            changed = await client.call_tool('data_assets_update', {
                'asset_id': asset.id, 'expected_revision': updated['revision'], 'changes': {'name': 'MCP current image'},
            })
            location = await client.call_tool('data_library_location', {'entry_type': 'asset', 'entry_id': asset.id})
            stale = await client.call_tool('data_assets_update', {
                'asset_id': asset.id, 'expected_revision': asset.revision, 'changes': {'name': 'Stale edit'},
            }, raise_on_error=False)
            return changed, location, stale

    changed, location, stale = asyncio.run(edit_and_read())
    assert changed.structured_content['asset']['name'] == 'MCP current image'
    assert location.structured_content['files'][0]['calibration_status'] == 'UnCalibrated'
    assert stale.is_error
    error = json.loads(next(content.text for content in stale.content if getattr(content, 'text', None)))
    assert error['error']['code'] == 'REVISION_CONFLICT'
    http_error = real_http.patch(f'/api/v1/library/assets/{asset.id}', json={'expected_revision': asset.revision, 'changes': {'name': 'Stale edit'}})
    assert http_error.status_code == 409
    assert http_error.json()['error']['code'] == error['error']['code']
    current = real_http.get(f'/api/v1/library/assets/{asset.id}').json()
    assert current['name'] == 'MCP current image'
