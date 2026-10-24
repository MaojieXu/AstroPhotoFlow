from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def main() -> None:
    corepack = shutil.which("corepack.cmd" if os.name == "nt" else "corepack") or shutil.which("corepack")
    node = shutil.which("node") or shutil.which("node.exe")
    if corepack is None or node is None:
        raise SystemExit("Frontend release build requires Node.js and Corepack for the pnpm version pinned in frontend/package.json.")
    frontend = ROOT / "frontend"
    env = os.environ.copy()
    env["CI"] = "true"
    subprocess.run([corepack, "pnpm", "install", "--frozen-lockfile"], cwd=frontend, env=env, check=True)
    subprocess.run([corepack, "pnpm", "run", "build"], cwd=frontend, env=env, check=True)
    shutil.rmtree(DIST, ignore_errors=True)
    subprocess.run([sys.executable, "-m", "build", str(ROOT)], check=True)
    artifacts = sorted(DIST.glob("astrophotoflow-0.1.0*"))
    if not any(path.suffix == ".whl" for path in artifacts) or not any(path.name.endswith(".tar.gz") for path in artifacts):
        raise SystemExit("Python build did not produce both the wheel and sdist.")
    for artifact in artifacts:
        print(f"{artifact.name}: {artifact.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
