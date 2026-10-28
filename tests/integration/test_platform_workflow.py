"""Opt-in native acceptance. Run only in the planned shared-runtime maintenance window."""
import os
from pathlib import Path
import socket

import httpx
import pytest

from astrophotoflow.core import config, workbench


@pytest.mark.skipif(not os.environ.get("APF_QA_WORKSPACE_A"), reason="Requires the M1 maintenance window and prepared isolated W1/W2")
def test_native_workspace_lifecycle_and_configuration_adoption():
    first = Path(os.environ["APF_QA_WORKSPACE_A"]).resolve()
    second = Path(os.environ["APF_QA_WORKSPACE_B"]).resolve()
    allowed = Path(".artifacts/workspaces").resolve()
    assert first.is_relative_to(allowed) and second.is_relative_to(allowed)
    assert first != second and first.name != "dev" and second.name != "dev"
    a, b = first / "config.toml", second / "config.toml"
    before_default = config.CONFIG_PATH.read_bytes() if config.CONFIG_PATH.is_file() else None
    preferred = workbench._load_config(a)[3]
    try:
        other = workbench.start(b)
        assert other.state == "completed"
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", preferred))
            occupied.listen()
            started = workbench.start(a)
            assert started.state == "completed" and started.web_url != f"http://127.0.0.1:{preferred}"
            assert started.web_url != other.web_url and started.service_url != other.service_url
            assert workbench.status(a).ready and workbench.status(b).ready
            reused = workbench.start(a)
            assert reused.reused and reused.web_url == started.web_url
        state = config.get_configuration(a)
        assert state.saved.service_port == state.effective.service_port
        target_workers = state.effective.file_workers + 1
        changed = config.save_configuration(a, state.saved.model_copy(update={"file_workers": target_workers}), state.config_token)
        assert changed.restart_required and changed.effective.file_workers != target_workers
        adopted = config.load_running_settings(first)
        token = adopted.token_path.read_text(encoding="utf-8").strip()
        with httpx.Client(base_url=started.service_url, headers={"Authorization": f"Bearer {token}"}, timeout=10) as client:
            queued = client.post("/api/v1/uploads", json={"files": [{"name": "m1-pending.png", "size": 10}]})
            assert queued.status_code == 202
            rejected = workbench.restart(a)
            assert rejected.state == "rejected" and rejected.blockers
            assert workbench.status(b).ready
            failed = client.post(f"/api/v1/uploads/{queued.json()['task_id']}/fail")
            assert failed.status_code == 200
        restarted = workbench.restart(a)
        assert restarted.state == "completed"
        current = config.get_configuration(a)
        assert current.effective.file_workers == target_workers and not current.restart_required
        assert workbench.status(b).ready
    finally:
        workbench.stop(a)
        workbench.stop(b)
    assert workbench.status(a).state == "stopped" and workbench.status(b).state == "stopped"
    current_default = config.CONFIG_PATH.read_bytes() if config.CONFIG_PATH.is_file() else None
    assert current_default == before_default
