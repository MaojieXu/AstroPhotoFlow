"""Build the native workbench frontend in the checkout."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / ".artifacts/build/frontend"


def prepare_output(assets: Path) -> None:
    if assets.parent.resolve() != assets.parent:
        raise RuntimeError(f"Build output parent must be a local directory: {assets.parent}")
    # Older dev builds published a link. Vite must never empty its target.
    if assets.is_junction():
        assets.rmdir()
    elif assets.is_symlink():
        assets.unlink()


def main() -> int:
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise SystemExit("Install the pnpm version pinned in package.json.")
    prepare_output(ASSETS)
    env = {**os.environ, "DISTRIBUTION": "localhost"}
    for command in (
        [sys.executable, "scripts/build_engine.py"],
        [pnpm, "typecheck"],
        [pnpm, "--dir", "frontend", "build"],
    ):
        result = subprocess.run(command, cwd=ROOT, env=env, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
