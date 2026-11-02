"""Opt-in check of the pinned framework's real stdio development reloader."""

import asyncio
import json
import os
import sys
from pathlib import Path

import psutil
import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport


@pytest.mark.skipif(os.environ.get('APF_TEST_MCP_RELOAD') != '1', reason='Explicit isolated process opt-in')
def test_official_reload_restarts_the_actual_catalog_and_allows_reconnection(tmp_path):
    root = Path(__file__).resolve().parents[3]
    workspace = root / '.artifacts/workspaces/modernization-current'
    script = tmp_path / 'reload_catalog.py'
    template = '''import os
from astrophotoflow.interfaces.mcp.server import build_tool_catalog
def factory():
    server = build_tool_catalog()
    @server.tool
    def reload_probe() -> dict[str, int]:
        return {"value": VALUE, "pid": os.getpid()}
    return server
'''
    script.write_text(template.replace('VALUE', '1'), encoding='utf-8')
    executable = str(Path(sys.executable).with_name('fastmcp.exe' if os.name == 'nt' else 'fastmcp'))
    arguments = ['run', str(script) + ':factory', '--reload',
                 '--reload-dir', str(tmp_path), '--skip-env', '--no-banner']
    env = {'ASTROPHOTOFLOW_CONFIG': str(workspace / 'config.toml'), 'PYTHONUTF8': '1',
           'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH']}

    def transport(*, reload=True):
        args = arguments if reload else ['run', str(script) + ':factory', '--no-reload', '--skip-env', '--no-banner']
        return StdioTransport(command=executable, args=args, cwd=str(root), env=env)

    def stop_development_watcher():
        spec = str(script) + ':factory'
        owned = {}
        for process in psutil.Process().children(recursive=True):
            try:
                command = process.cmdline()
                if '--reload' in command and spec in command:
                    for child in [process, *process.children(recursive=True)]:
                        owned[child.pid] = (child, child.create_time())
            except psutil.NoSuchProcess:
                continue
        for process, birth in reversed(list(owned.values())):
            try:
                if process.is_running() and process.create_time() == birth:
                    process.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs([process for process, _ in owned.values()], timeout=5)
        assert not alive, 'Owned development watcher must not outlive the test'

    async def scenario():
        async with Client(transport(), timeout=15, init_timeout=15) as client:
            try:
                tools = await client.list_tools()
                assert len(tools) == 98
                before = (await client.call_tool('reload_probe', {})).structured_content
                assert before['value'] == 1
                original = psutil.Process(before['pid'])
                birth = original.create_time()
                script.write_text(template.replace('VALUE', '2') + '\n# Updated development source\n', encoding='utf-8')
                deadline = asyncio.get_running_loop().time() + 15
                while asyncio.get_running_loop().time() < deadline:
                    try:
                        if not original.is_running() or original.create_time() != birth:
                            break
                    except psutil.NoSuchProcess:
                        break
                    await asyncio.sleep(0.1)
                else:
                    pytest.fail('Pinned FastMCP did not restart the original server after a source edit')
                # --reload is an interactive developer watcher, not a one-shot MCP
                # process: stop that owned tree before closing its inherited pipes.
            finally:
                stop_development_watcher()
        # Reconnect explicitly; the product does not promise transparent stdio sessions.
        async with Client(transport(reload=False), timeout=15, init_timeout=15) as client:
            after = (await client.call_tool('reload_probe', {})).structured_content
            assert after['value'] == 2
            assert before['pid'] != after['pid']
        (root / '.artifacts/reports/modernization/g7/mcp-real-reload.json').write_text(
            json.dumps({'before': before, 'after': after, 'catalog_tools_with_probe': len(tools),
                        'original_server_exited_before_disconnect': True, 'explicit_reconnect': True,
                        'development_watcher_stopped_explicitly': True}, indent=2),
            encoding='utf-8',
        )

    asyncio.run(scenario())
