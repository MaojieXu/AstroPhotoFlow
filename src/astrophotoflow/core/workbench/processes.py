from __future__ import annotations

import os
import socket
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx
import psutil

from astrophotoflow.contracts.workbench import ProcessInfo
from astrophotoflow.core import config as app_config

from . import state
from .errors import WorkbenchError


def port_available(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            listener.bind((host, port))
        except OSError:
            return False
    return True


def identify_process(record: dict) -> psutil.Process | None:
    try:
        process = psutil.Process(record["pid"])
        created = process.create_time()
        recovering = "create_time" not in record
        if recovering:
            if not record["launch_started"] - 1.0 <= created <= record["launch_finished"] + 1.0:
                raise WorkbenchError("无法确认待登记进程的启动时间。")
        elif abs(created - record["create_time"]) > 1.0 or os.path.normcase(process.exe()) != os.path.normcase(record["executable"]):
            return None
        if process.cmdline() != record["command"] or process.environ().get("APF_WORKSPACE") != record["workspace"]:
            if recovering:
                raise WorkbenchError("无法确认待登记进程的命令或工作区。")
            return None
        if recovering:
            record["create_time"], record["executable"] = created, process.exe()
        return process if process.is_running() else None
    except psutil.NoSuchProcess:
        return None
    except (psutil.AccessDenied, OSError, KeyError, TypeError, ValueError) as exc:
        raise WorkbenchError("无法确认记录进程的身份。") from exc


def record_process(process, role: str, workspace: Path, command: list[str]) -> dict:
    item = psutil.Process(process.pid)
    value = ProcessInfo(role=role, pid=process.pid, create_time=item.create_time(), executable=item.exe(),
        command=command, started_at=datetime.now(UTC), workspace=str(workspace))
    return value.model_dump(mode='json')


def launch_process(command: list[str], cwd: Path, env: dict, log_path: Path) -> subprocess.Popen:
    with log_path.open("ab") as log:
        kwargs = {"stdin": subprocess.DEVNULL, "stdout": log, "stderr": subprocess.STDOUT, "cwd": str(cwd), "env": env}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        return subprocess.Popen(command, **kwargs)


def stop_processes(config_path: Path, *, control: dict, pending_child=None) -> None:
    workspace = config_path.parent
    raw = state.read_state(workspace)
    pending = control.get("pending_process")
    if pending is not None and pending.get("pid") is None:
        raise WorkbenchError("启动进程身份尚未登记，无法确认是否已停止；请先核对实际进程。")
    native = "effective_settings" in raw or pending is not None or any(
        item["role"] == "comfyui" and "--front-end-root" in item["command"] for item in raw["processes"])
    records = list(raw["processes"])
    if pending is not None and not any(
            item.get("pid") == pending["pid"] and item.get("role") == pending["role"] for item in records):
        records.append(pending)
    for record in reversed(records):
        is_pending_child = (pending_child is not None and pending is not None
                            and record["pid"] == pending["pid"] and record["role"] == pending["role"])
        if is_pending_child and pending_child.poll() is not None:
            process = None
        elif is_pending_child and record["role"] == "asset-service":
            process = pending_child
        elif is_pending_child:
            try:
                process = psutil.Process(pending_child.pid)
            except psutil.NoSuchProcess:
                if pending_child.poll() is None:
                    raise WorkbenchError(f"无法确认启动进程 {pending_child.pid} 已退出。")
                process = None
        else:
            process = identify_process(record)
        if process is None:
            continue
        if native and record["role"] == "asset-service":
            settings = app_config.load_running_settings(workspace)
            token = settings.token_path.read_text(encoding="utf-8").strip()
            httpx.post(settings.service_url + "/internal/shutdown", headers={"Authorization": f"Bearer {token}"}, timeout=5).raise_for_status()
            try:
                process.wait(timeout=30)
            except (psutil.TimeoutExpired, subprocess.TimeoutExpired) as exc:
                raise WorkbenchError("导入或预览仍在排空，进程记录已保留；稍后查询并停止。") from exc
            continue
        family = [process, *process.children(recursive=True)]
        for member in family:
            if member.environ().get("APF_WORKSPACE") != str(workspace):
                raise WorkbenchError(f"进程{member.pid}不属于目标workspace，停止已中止。")
        for member in reversed(family):
            try:
                member.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(family, timeout=10)
        if alive:
            raise WorkbenchError("原生进程尚未退出，保留记录；请查询后再停止。")
    raw["processes"] = []
    if "effective_settings" in raw:
        state.update_running_state(workspace, {"processes": []})
    else:
        state.write_state(workspace, raw)
    control.pop("pending_process", None)
