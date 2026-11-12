import json
from pathlib import Path

from astrophotoflow.core import config
from astrophotoflow.core.workbench import doctor


def write_workspace(path: Path, port: int = 31390, web: int = 31388) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "config.toml").write_text(
        f'[server]\nhost = "127.0.0.1"\nport = {port}\n'
        '[storage]\ndata_dir = "data"\n'
        f'[comfyui]\nallowed_origins = ["http://127.0.0.1:{web}"]\n',
        encoding="utf-8",
    )
    return path


def test_version_requirements_handle_ranges_and_exact_pins():
    assert doctor._version_tuple("v26.8.2") == (26, 8, 2)
    assert doctor._version_tuple("no version") is None
    assert doctor._satisfies((26, 8, 2), ">=26.8.2 <27")
    assert not doctor._satisfies((23, 8, 0), ">=26.8.2 <27")
    assert doctor._satisfies((26, 8, 2), ">=26.8.2 <27")
    assert doctor._satisfies((11, 13, 1), "11.13.1")
    assert not doctor._satisfies((9, 10, 0), "11.13.1")


def test_pinned_tools_reads_root_package(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src/astrophotoflow").mkdir(parents=True)
    (repo / "package.json").write_text(
        json.dumps({"packageManager": "pnpm@11.13.1", "engines": {"node": ">=26.8.2 <27"}}), encoding="utf-8"
    )
    assert doctor._pinned_tools(repo) == {"node": ">=26.8.2 <27", "pnpm": "11.13.1"}


def test_workspace_checks_report_recorded_ports(tmp_path, monkeypatch):
    workspace = write_workspace(tmp_path / "workspace")
    run = workspace / "run"
    run.mkdir()
    (run / "processes.json").write_text(
        json.dumps({"workspace": str(workspace), "actual_ports": {"service": 31390, "web": 31388}}), encoding="utf-8"
    )
    monkeypatch.setattr(doctor.app_config, "default_workspace", lambda: workspace)
    checks = {entry["name"]: entry for entry in doctor._workspace_checks(workspace)}
    assert checks["workspace"]["status"] == doctor.OK
    assert checks["workspace-ports"]["status"] == doctor.OK
    assert "31390" in checks["workspace-ports"]["detail"]
    assert checks["default-workspace"]["status"] == doctor.OK


def test_workspace_checks_warn_when_workspace_cannot_be_resolved(monkeypatch):
    def missing_pointer(path=None):
        raise config.ConfigurationError("未设置默认 workspace；请初始化或明确选择配置文件。")

    monkeypatch.setattr(doctor.app_config, "resolve_config_path", missing_pointer)
    checks = {entry["name"]: entry for entry in doctor._workspace_checks(None)}
    assert checks["workspace"]["status"] == doctor.WARN


def test_workspace_checks_fail_when_explicit_workspace_is_broken(monkeypatch):
    def missing_pointer(path=None):
        raise config.ConfigurationError("默认 workspace 无效")

    monkeypatch.setattr(doctor.app_config, "resolve_config_path", missing_pointer)
    checks = {entry["name"]: entry for entry in doctor._workspace_checks(Path("broken"))}
    assert checks["workspace"]["status"] == doctor.FAIL
