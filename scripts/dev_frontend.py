import argparse
import os
import shutil
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import psutil
from watchfiles import DefaultFilter, watch

from astrophotoflow.core.config import ConfigurationError
from astrophotoflow.core.workbench import WorkbenchError, initialize, restart, start, status

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ASSETS = ROOT / ".artifacts/build/frontend"
PYTHON_SOURCE = ROOT / "src/astrophotoflow"


def require_web_url(result):
    if result.state != "completed" or not result.web_url:
        detail = "；".join(result.blockers) or result.detail or result.state
        raise WorkbenchError(f"{result.workspace}：{detail}")
    return result.web_url


def ensure_workbench(config):
    state = status(config)
    if state.ready and state.web_url:
        return state.web_url
    if state.state != "stopped":
        raise WorkbenchError(f"工作台尚未就绪：{state.workspace}；{state.reason or state.state}")
    workspace = config.parent
    if not config.is_file() or not (workspace / "web/index.html").is_file():
        if not (FRONTEND_ASSETS / "index.html").is_file():
            raise WorkbenchError("缺少前端构建产物，请先在仓库根目录运行 pnpm build。")
        initialize(workspace, frontend_assets=FRONTEND_ASSETS, activate=False)
    return require_web_url(start(config))


def vite_environment(config, web_url):
    print(f"Workspace: {config.parent}\nBackend: {web_url}", flush=True)
    return {**os.environ, "DISTRIBUTION": "localhost", "DEV_SERVER_COMFYUI_URL": web_url}


def stop_vite(process):
    if process.poll() is not None:
        return
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        process.wait()
        return
    owned = [*reversed(children), parent]
    for child in owned:
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(owned, timeout=5)
    for child in alive:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    process.wait(timeout=5)
    _, alive = psutil.wait_procs(alive, timeout=5)
    if alive:
        raise WorkbenchError("Vite 子进程未退出，无法确认开发服务器已停止。")


def watch_workbench(config, command, web_url):
    default_filter = DefaultFilter()

    def python_file(change, path):
        return path.endswith(".py") and default_filter(change, path)

    process = subprocess.Popen(command, cwd=ROOT, env=vite_environment(config, web_url))
    try:
        with closing(watch(PYTHON_SOURCE, watch_filter=python_file, rust_timeout=250,
                           yield_on_timeout=True, raise_interrupt=True)) as changes:
            for batch in changes:
                code = process.poll()
                if code is not None:
                    return code
                if not batch:
                    continue
                print("Python 源码有改动，正在重启开发工作台。", flush=True)
                try:
                    next_url = require_web_url(restart(config))
                except (WorkbenchError, ConfigurationError, OSError) as exc:
                    print(f"开发工作台重启未完成：{exc}", file=sys.stderr, flush=True)
                    continue
                print("开发工作台已重启。", flush=True)
                if next_url != web_url:
                    stop_vite(process)
                    web_url = next_url
                    process = subprocess.Popen(command, cwd=ROOT, env=vite_environment(config, web_url))
    except KeyboardInterrupt:
        return 130
    finally:
        stop_vite(process)


def main():
    parser = argparse.ArgumentParser(description="Run Vite against the selected AstroPhotoFlow workspace.")
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--start-workbench", action="store_true", help="Start the development workbench and reload Python on save.")
    arguments, vite_arguments = parser.parse_known_args()
    configured = os.environ.get("ASTROPHOTOFLOW_CONFIG")
    if arguments.workspace:
        config = arguments.workspace.expanduser().resolve() / "config.toml"
    elif configured:
        config = Path(configured).expanduser().resolve()
    else:
        parser.error("请明确指定--workspace或ASTROPHOTOFLOW_CONFIG。")

    pnpm = shutil.which("pnpm")
    if pnpm is None:
        parser.error("找不到 pnpm。")
    command = [pnpm, "--dir", str(ROOT / "frontend"), "dev", *vite_arguments]
    if arguments.start_workbench:
        try:
            return watch_workbench(config, command, ensure_workbench(config))
        except (WorkbenchError, ConfigurationError, OSError, subprocess.TimeoutExpired) as exc:
            parser.exit(1, f"开发工作台：{exc}\n")
    state = status(config)
    if not state.ready or not state.web_url:
        parser.error(f"工作台尚未就绪：{state.workspace}；{state.reason or state.state}")
    return subprocess.call(command, cwd=ROOT, env=vite_environment(config, state.web_url))


if __name__ == "__main__":
    raise SystemExit(main())
