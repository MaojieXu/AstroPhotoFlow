import json
from unittest.mock import Mock
from uuid import uuid4

import pytest

from astrophotoflow.contracts.workbench import WorkbenchResult
from astrophotoflow.interfaces.cli import local
from astrophotoflow.interfaces.cli.main import app


@pytest.mark.parametrize(
    ("state", "web_url", "reused", "interactive", "browser_result"),
    [
        ("completed", "http://127.0.0.1:8188", False, True, None),
        ("completed", "http://127.0.0.1:8188", True, True, True),
        ("completed", "http://127.0.0.1:8189", False, True, True),
        ("completed", "http://127.0.0.1:8189", False, False, None),
        ("completed", "http://127.0.0.1:8189", False, False, False),
        ("completed", "http://127.0.0.1:8189", False, False, OSError()),
        ("failed", None, False, True, True),
    ],
)
def test_start_keeps_json_and_reports_the_ready_web_url(
    monkeypatch, capsys, tmp_path, state, web_url, reused, interactive, browser_result
):
    receipt = WorkbenchResult(
        operation_id=uuid4(), action="start", state=state, workspace=str(tmp_path),
        config_path=str(tmp_path / "config.toml"), reused=reused, web_url=web_url,
        service_url=None, detail=None, blockers=[], log_path=None,
    )
    start = Mock(return_value=receipt)
    browser = Mock(side_effect=browser_result) if isinstance(browser_result, OSError) else Mock(return_value=browser_result)
    monkeypatch.setattr(local.workbench, "start", start)
    monkeypatch.setattr(local.sys.stderr, "isatty", lambda: interactive)
    monkeypatch.setattr(local.webbrowser, "open", browser)
    args = ["start", "--workspace", str(tmp_path)]
    if browser_result is not None:
        args.append("--open")

    with pytest.raises(SystemExit) as exc:
        app(args, exit_on_error=False)
    assert exc.value.code == (1 if state == "failed" else 0)

    start.assert_called_once_with(tmp_path / "config.toml")
    captured = capsys.readouterr()
    assert json.loads(captured.out) == receipt.model_dump(mode="json")
    if web_url and interactive:
        assert captured.err == f"工作台已就绪：{web_url}\n"
    elif browser_result is False or isinstance(browser_result, OSError):
        assert captured.err == f"无法自动打开浏览器，请手动访问：{web_url}\n"
    else:
        assert captured.err == ""
    if web_url and browser_result is not None:
        browser.assert_called_once_with(web_url)
    else:
        browser.assert_not_called()
