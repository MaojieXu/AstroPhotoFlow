"""Opt-in process acceptance; the native lifecycle case uses the planned maintenance window."""
import os
import io
import logging.config
from pathlib import Path
import sqlite3
import socket
import threading
import time
from uuid import uuid4

import httpx
import pytest
from PIL import Image

from astrophotoflow.core import config, workbench
from astrophotoflow.core.database.schema import database_lock, upgrade_database


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
            operation_id = str(uuid4())
            entered = client.post("/internal/maintenance", json={"action": "enter", "operation_id": operation_id})
            assert entered.status_code == 200 and not entered.json()["busy"] and not entered.json()["unknown"]
            for path in ("/prompt", "/api/prompt"):
                blocked = httpx.post(started.web_url + path, json={"prompt": {}}, headers={"Origin": started.web_url}, timeout=10)
                assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "WORKBENCH_MAINTENANCE"
            released = client.post("/internal/maintenance", json={"action": "release", "operation_id": operation_id})
            assert released.status_code == 200 and not released.json()["busy"]
            invalid_prompt = httpx.post(started.web_url + "/prompt", json={"prompt": {}}, headers={"Origin": started.web_url}, timeout=10)
            assert invalid_prompt.status_code == 400
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


@pytest.mark.skipif(not os.environ.get("APF_QA_WORKSPACE_A"), reason="Requires explicit opt-in to real isolated process tests")
def test_start_failure_drains_an_active_import_in_real_domain_process(tmp_path, monkeypatch):
    assert tmp_path.resolve().is_relative_to(Path(".artifacts").resolve())
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "user/config.toml")
    monkeypatch.setattr(logging.config, "fileConfig", lambda *args, **kwargs: None)
    monkeypatch.delenv("APF_WORKSPACE", raising=False)
    monkeypatch.delenv("ASTROPHOTOFLOW_CONFIG", raising=False)
    workspace = tmp_path / "workspace"
    for name in ("web", "data", "logs", "run"):
        (workspace / name).mkdir(parents=True, exist_ok=True)
    (workspace / "web/index.html").write_text("AstroPhotoFlow", encoding="utf-8")
    path = workspace / "config.toml"
    path.write_text('[server]\nhost="127.0.0.1"\nport=33190\n[storage]\ndata_dir="data"\n'
                    '[comfyui]\nallowed_origins=["http://127.0.0.1:33188"]\n', encoding="utf-8")
    settings = config.load_settings(path)
    with database_lock(settings):
        upgrade_database(settings)

    support = tmp_path / "support"
    support.mkdir()
    (support / "sitecustomize.py").write_text(
        "import os, time\n"
        "from pathlib import Path\n"
        "from astrophotoflow.modules.data import ingestion\n"
        "original = ingestion._content_item\n"
        "def held_content(*args, **kwargs):\n"
        "    Path(os.environ['APF_TEST_IMPORT_STARTED']).write_text('started')\n"
        "    while not Path(os.environ['APF_TEST_IMPORT_RELEASE']).exists():\n"
        "        time.sleep(0.02)\n"
        "    result = original(*args, **kwargs)\n"
        "    Path(os.environ['APF_TEST_IMPORT_DONE']).write_text('done')\n"
        "    return result\n"
        "ingestion._content_item = held_content\n", encoding="utf-8",
    )
    started, release, done = (tmp_path / name for name in ("started", "release", "done"))
    buffer = io.BytesIO()
    Image.new("L", (8, 8), 128).save(buffer, format="PNG")
    image = buffer.getvalue()
    original_launch, original_post = workbench._launch, httpx.post
    domain = []
    outcome = {}
    evidence = {}
    thread = None

    def launch(command, cwd, env, log_path):
        nonlocal thread
        if "astrophotoflow.interfaces.http.cli" in command:
            child_env = env.copy()
            child_env["PYTHONPATH"] = str(support) + os.pathsep + child_env["PYTHONPATH"]
            child_env.update({"APF_TEST_IMPORT_STARTED": str(started), "APF_TEST_IMPORT_RELEASE": str(release),
                              "APF_TEST_IMPORT_DONE": str(done)})
            domain.append(original_launch(command, cwd, child_env, log_path))
            return domain[0]

        state = workbench._read_state(workspace)
        token = settings.token_path.read_text(encoding="utf-8").strip()
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(base_url=state["service_url"], headers=headers, timeout=20) as client:
            created = client.post("/api/v1/uploads", json={"files": [{"name": "active.png", "size": len(image)}]})
            assert created.status_code == 202, created.text
            task_id = created.json()["task_id"]
            outcome["task_id"] = task_id
            uploaded = client.put(f"/api/v1/uploads/{task_id}/0", content=image)
            assert uploaded.status_code == 200, uploaded.text

            def start_import():
                try:
                    with httpx.Client(base_url=state["service_url"], headers=headers, timeout=60) as task_client:
                        response = task_client.post(f"/api/v1/uploads/{task_id}/start")
                        outcome["status"] = response.status_code
                except Exception as exc:
                    outcome["error"] = str(exc)

            thread = threading.Thread(target=start_import)
            thread.start()
            deadline = time.monotonic() + 20
            while not started.is_file() and time.monotonic() < deadline:
                time.sleep(0.02)
            assert started.is_file(), outcome
            task = client.get(f"/api/v1/asset-tasks/{task_id}")
            assert task.status_code == 200 and task.json()["status"] == "running", task.text
        raise OSError("simulated native launch failure")

    def shutdown(url, *, headers, timeout):
        response = original_post(url, headers=headers, timeout=timeout)
        if url.endswith("/internal/shutdown"):
            evidence["alive"] = domain[0].poll() is None
            evidence["running_before_release"] = started.is_file() and not done.is_file()
            evidence["recorded"] = bool(workbench._read_state(workspace)["processes"])
            release.touch()
        return response

    monkeypatch.setattr(workbench, "_launch", launch)
    monkeypatch.setattr(workbench.httpx, "post", shutdown)
    try:
        with pytest.raises(workbench.WorkbenchError, match="simulated native launch failure"):
            workbench.start(path)
        assert thread is not None
        thread.join(timeout=30)
        assert not thread.is_alive() and outcome.get("status") == 202, outcome
        assert evidence == {"alive": True, "running_before_release": True, "recorded": True}
        assert done.is_file() and domain[0].poll() == 0
        with sqlite3.connect(settings.database_path) as database:
            status = database.execute("SELECT status FROM asset_task WHERE id = ?", (outcome["task_id"],)).fetchone()
            assets = database.execute("SELECT COUNT(*) FROM asset").fetchone()[0]
        assert status is not None and status[0] == "completed" and assets == 1
        assert workbench._read_state(workspace)["processes"] == []
    finally:
        release.touch()
        if thread is not None:
            thread.join(timeout=30)
        if domain and domain[0].poll() is None:
            token = settings.token_path.read_text(encoding="utf-8").strip()
            service_url = workbench._read_state(workspace)["service_url"]
            original_post(service_url + "/internal/shutdown", headers={"Authorization": f"Bearer {token}"}, timeout=5).raise_for_status()
            domain[0].wait(timeout=30)
