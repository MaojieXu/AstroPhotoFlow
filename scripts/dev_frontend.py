import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from dev_prepare import ROOT, environment


def main():
    parser = argparse.ArgumentParser(description="Run Vite against the selected AstroPhotoFlow workspace.")
    parser.add_argument("--workspace", type=Path)
    arguments, vite_arguments = parser.parse_known_args()
    workspace = arguments.workspace.resolve() if arguments.workspace else None
    config = os.environ.get("ASTROPHOTOFLOW_CONFIG")
    if workspace is None and config is None:
        parser.error("请明确指定--workspace或ASTROPHOTOFLOW_CONFIG。")
    workspace = workspace or Path(config).resolve().parent
    env = environment(workspace)
    python = Path(env["UV_PROJECT_ENVIRONMENT"]) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        parser.error("开发依赖尚未准备；请先运行pnpm dev:prepare。")
    if Path(sys.executable).resolve() != python.resolve():
        return subprocess.call([str(python), __file__, *sys.argv[1:]], cwd=ROOT, env=env)
    os.environ.update(env)
    from astrophotoflow.core.workbench import status

    state = status(arguments.workspace / "config.toml" if arguments.workspace else None)
    if not state.ready or not state.web_url:
        parser.error(f"工作台尚未就绪：{state.workspace}；{state.reason or state.state}")
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        parser.error("找不到 pnpm。")
    vite_env = {**os.environ, "DEV_SERVER_COMFYUI_URL": state.web_url}
    print(f"Workspace: {state.workspace}\nBackend: {state.web_url}", flush=True)
    return subprocess.call([pnpm, "--dir", str(ROOT / "frontend"), "dev", *vite_arguments], cwd=ROOT, env=vite_env)


if __name__ == "__main__":
    raise SystemExit(main())
