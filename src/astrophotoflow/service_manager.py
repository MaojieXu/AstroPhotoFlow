from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import shutil
import signal
import subprocess
import threading
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from .proxy import ProxyError, _configuration


logger = logging.getLogger("astrophotoflow.extension")


def _service_is_ready(upstream: str, token: str) -> bool:
    request = Request(
        f"{upstream}/api/v1/health",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=0.75) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, URLError, ValueError):
        return False
    return (
        isinstance(payload, dict)
        and payload.get("status") == "ok"
        and payload.get("api_version") == "v1"
        and payload.get("database") == "ready"
        and isinstance(payload.get("schema_revision"), str)
    )


class ServiceManager:
    def __init__(
        self,
        extension_root: Path,
        *,
        startup_timeout: float = 20.0,
        health_interval: float = 5.0,
    ) -> None:
        self._service_project = extension_root.resolve() / "service"
        self._startup_timeout = startup_timeout
        self._health_interval = health_interval
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._process: subprocess.Popen | None = None
        self._owns_process = False
        self._running = False
        self._stopping = False
        self._started = False
        self._error: ProxyError | None = None
        self._health_failures = 0
        self._restart_count = 0
        self._monitor_thread: threading.Thread | None = None

    def start(self) -> bool:
        with self._lock:
            if self._started:
                return self._running
            self._started = True
            try:
                self._start_or_attach()
            except ProxyError as exc:
                self._error = exc
                logger.error("AstroPhotoFlow service start failed: %s", exc.message)
                return False
            self._running = True
            self._error = None
            self._monitor_thread = threading.Thread(
                target=self._monitor,
                name="astrophotoflow-service-monitor",
                daemon=True,
            )
            self._monitor_thread.start()
            return True

    def ensure_available(self) -> None:
        with self._lock:
            exited = (
                self._owns_process
                and self._process is not None
                and self._process.poll() is not None
            )
        if exited:
            self._monitor_once()
        with self._lock:
            if self._running and not self._stopping:
                return
            if self._error is not None:
                raise self._error
            raise ProxyError(
                503,
                "SERVICE_UNAVAILABLE",
                "AstroPhotoFlow 资产服务尚未就绪。",
            )

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            self._stopping = True
            thread = self._monitor_thread
            process = self._process if self._owns_process else None
            self._process = None
            self._owns_process = False
            self._running = False
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)
        if process is not None:
            self._terminate_process(process)

    def _start_or_attach(self) -> None:
        upstream, _allowed_origins, token = _configuration(allow_missing_token=True)
        if token is not None and _service_is_ready(upstream, token):
            self._process = None
            self._owns_process = False
            return

        if os.environ.get("APF_WORKBENCH_MANAGED") == "1":
            raise ProxyError(
                503,
                "SERVICE_UNAVAILABLE",
                "AstroPhotoFlow 工作台未启动资产服务；请先运行 apf start。",
            )

        if not (self._service_project / "pyproject.toml").is_file():
            raise ProxyError(
                503,
                "SERVICE_UNAVAILABLE",
                "未找到 AstroPhotoFlow 独立服务项目。",
            )
        uv = shutil.which("uv")
        if uv is None:
            local_uv = Path.home() / ".local" / "bin" / "uv"
            if local_uv.is_file() and os.access(local_uv, os.X_OK):
                uv = str(local_uv)
        if uv is None:
            raise ProxyError(
                503,
                "SERVICE_UNAVAILABLE",
                "未找到可运行的 uv；请先安装 uv 并准备资产服务依赖。",
            )

        command = [
            uv,
            "run",
            "--project",
            str(self._service_project),
            "--locked",
            "--no-sync",
            "apf-service",
            "serve",
        ]
        try:
            process = subprocess.Popen(
                command,
                cwd=self._service_project.parent,
                start_new_session=(os.name == "posix"),
            )
        except OSError as exc:
            raise ProxyError(
                503,
                "SERVICE_UNAVAILABLE",
                "无法启动 AstroPhotoFlow 资产服务；请检查 ComfyUI 后端日志。",
            ) from exc
        self._process = process
        self._owns_process = True

        deadline = time.monotonic() + self._startup_timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                # Another ComfyUI instance may have started the same service first.
                upstream, _allowed_origins, token = _configuration(allow_missing_token=True)
                if token is not None and _service_is_ready(upstream, token):
                    self._process = None
                    self._owns_process = False
                    return
                raise ProxyError(
                    503,
                    "SERVICE_UNAVAILABLE",
                    f"AstroPhotoFlow 资产服务启动失败（退出码 {process.returncode}）；请查看 ComfyUI 后端日志。",
                )

            upstream, _allowed_origins, token = _configuration(allow_missing_token=True)
            if token is not None and _service_is_ready(upstream, token):
                return
            time.sleep(0.15)

        self._terminate_process(process)
        self._process = None
        self._owns_process = False
        raise ProxyError(
            503,
            "SERVICE_UNAVAILABLE",
            "等待 AstroPhotoFlow 资产服务就绪超时；请检查端口、数据库迁移和 ComfyUI 后端日志。",
        )

    def _monitor(self) -> None:
        while not self._stop_event.wait(self._health_interval):
            self._monitor_once()

    def _monitor_once(self) -> None:
        with self._lock:
            if self._stopping:
                return
            process = self._process
            if self._owns_process and process is not None and process.poll() is not None:
                self._running = False
                self._process = None
                self._owns_process = False
                if self._restart_count >= 1:
                    self._error = ProxyError(
                        503,
                        "SERVICE_UNAVAILABLE",
                        "AstroPhotoFlow 资产服务重启后再次退出；请检查 ComfyUI 后端日志。",
                    )
                    logger.error("%s", self._error.message)
                    return
                self._restart_count += 1
                try:
                    self._start_or_attach()
                except ProxyError as exc:
                    self._error = exc
                    logger.error("AstroPhotoFlow service restart failed: %s", exc.message)
                    return
                self._running = True
                self._error = None
                self._health_failures = 0
                logger.info("AstroPhotoFlow asset service restarted.")
                return

            try:
                upstream, _allowed_origins, token = _configuration(allow_missing_token=True)
                healthy = token is not None and _service_is_ready(upstream, token)
            except ProxyError as exc:
                healthy = False
                self._error = exc

            if healthy:
                recovered = not self._running
                self._running = True
                self._error = None
                self._health_failures = 0
                if recovered:
                    logger.info("AstroPhotoFlow asset service is healthy again.")
                return

            self._health_failures += 1
            if self._health_failures >= 3:
                self._running = False
                if self._error is None:
                    self._error = ProxyError(
                        503,
                        "SERVICE_UNAVAILABLE",
                        "AstroPhotoFlow 资产服务连续未通过健康检查。",
                    )
                logger.warning("%s", self._error.message)

    @staticmethod
    def _terminate_process(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except ProcessLookupError:
                return
            process.wait(timeout=5)
