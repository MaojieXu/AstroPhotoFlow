import argparse
import os
from pathlib import Path
import shutil
import subprocess

from astrophotoflow.core.workbench import status


def main():
    parser = argparse.ArgumentParser(description="Run Vite against the selected AstroPhotoFlow workspace.")
    parser.add_argument("--workspace", type=Path)
    arguments, vite_arguments = parser.parse_known_args()
    state = status(arguments.workspace / "config.toml" if arguments.workspace else None)
    if not state.ready or not state.web_url:
        parser.error(f"工作台尚未就绪：{state.workspace}；{state.reason or state.state}")
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        parser.error("找不到 pnpm。")
    root = Path(__file__).resolve().parents[1]
    environment = {**os.environ, "DEV_SERVER_COMFYUI_URL": state.web_url}
    print(f"Workspace: {state.workspace}\nBackend: {state.web_url}", flush=True)
    return subprocess.call([pnpm, "--dir", str(root / "frontend"), "dev", *vite_arguments], cwd=root, env=environment)


if __name__ == "__main__":
    raise SystemExit(main())
