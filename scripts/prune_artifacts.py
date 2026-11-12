"""Remove scratch outputs under .artifacts; dry-run unless --apply."""

from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / ".artifacts"


def _size(path: Path) -> int:
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def _human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def candidates(now: float) -> list[tuple[Path, str, int]]:
    rules = [(ARTIFACTS / "tmp", 7), (ARTIFACTS / "logs/dev-prepare", 14)]
    found: list[tuple[Path, str, int]] = []
    for base, days in rules:
        if not base.is_dir():
            continue
        cutoff = now - days * 86400
        for path in sorted(base.iterdir()):
            try:
                if path.stat().st_mtime < cutoff:
                    found.append((path, f"超过 {days} 天", _size(path)))
            except OSError:
                continue
    for path in sorted(ARTIFACTS.glob("pytest*")):
        try:
            if path.is_dir() and path.stat().st_mtime < now - 3 * 86400:
                found.append((path, "pytest 临时目录超过 3 天", _size(path)))
        except OSError:
            continue
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="清理 .artifacts 下的临时产物（默认只预览）。")
    parser.add_argument("--apply", action="store_true", help="实际删除；默认只打印候选。")
    args = parser.parse_args()
    if not ARTIFACTS.is_dir():
        print(f"没有 {ARTIFACTS}，无需清理。")
        return 0
    found = candidates(time.time())
    if not found:
        print("没有可清理的临时产物。")
        return 0
    total = 0
    for path, reason, size in found:
        total += size
        print(f"{_human(size):>10}  {path.relative_to(ROOT)}  （{reason}）")
    print(f"合计 {_human(total)}，共 {len(found)} 项。")
    if not args.apply:
        print("预览模式；确认后追加 --apply 删除。")
        return 0
    for path, _reason, _size in found:
        try:
            shutil.rmtree(path) if path.is_dir() else path.unlink()
        except OSError as exc:
            print(f"删除失败：{path}：{exc}")
            return 1
    print(f"已删除 {len(found)} 项，释放 {_human(total)}。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
