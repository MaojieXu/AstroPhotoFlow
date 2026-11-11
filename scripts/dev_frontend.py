import argparse
import os
import shutil
import subprocess
from pathlib import Path

from astrophotoflow.core.workbench import status

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="Run Vite against the selected AstroPhotoFlow workspace.")
    parser.add_argument("--workspace", type=Path)
    arguments, vite_arguments = parser.parse_known_args()
    configured = os.environ.get("ASTROPHOTOFLOW_CONFIG")
    if arguments.workspace:
        config = arguments.workspace.expanduser().resolve() / "config.toml"
    elif configured:
        config = Path(configured).expanduser().resolve()
    else:
        parser.error("请明确指定--workspace或ASTROPHOTOFLOW_CONFIG。")

    state = status(config)
    if not state.ready or not state.web_url:
        parser.error(f"工作台尚未就绪：{state.workspace}；{state.reason or state.state}")
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        parser.error("找不到 pnpm。")
    vite_env = {**os.environ, "DISTRIBUTION": "localhost", "DEV_SERVER_COMFYUI_URL": state.web_url}
    print(f"Workspace: {state.workspace}\nBackend: {state.web_url}", flush=True)
    return subprocess.call([pnpm, "--dir", str(ROOT / "frontend"), "dev", *vite_arguments], cwd=ROOT, env=vite_env)


if __name__ == "__main__":
    raise SystemExit(main())
