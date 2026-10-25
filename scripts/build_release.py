from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def main() -> None:
    corepack = shutil.which("corepack.cmd" if os.name == "nt" else "corepack") or shutil.which("corepack")
    node = shutil.which("node") or shutil.which("node.exe")
    if corepack is None or node is None:
        raise SystemExit("Frontend release build requires Node.js and Corepack for the pnpm version pinned in package.json.")
    env = os.environ.copy()
    env["CI"] = "true"
    subprocess.run([corepack, "pnpm", "install", "--frozen-lockfile"], cwd=ROOT, env=env, check=True)
    subprocess.run([corepack, "pnpm", "run", "build"], cwd=ROOT, env=env, check=True)
    subprocess.run([sys.executable, "-m", "build", "--installer", "uv", str(ROOT)], check=True)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    artifacts = sorted(DIST.glob(f"{project['name']}-{project['version']}*"))
    if not any(path.suffix == ".whl" for path in artifacts) or not any(path.name.endswith(".tar.gz") for path in artifacts):
        raise SystemExit("Python build did not produce both the wheel and sdist.")
    for artifact in artifacts:
        print(f"{artifact.name}: {artifact.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
