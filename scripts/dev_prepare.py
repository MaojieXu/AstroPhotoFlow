from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
_record_spec = importlib.util.spec_from_file_location('frontend_build_record', Path(__file__).with_name('frontend_build_record.py'))
frontend_build_record = importlib.util.module_from_spec(_record_spec)
_record_spec.loader.exec_module(frontend_build_record)


def main_checkout() -> Path:
    git_dir = ROOT / '.git'
    if git_dir.is_file():
        git_dir = (ROOT / git_dir.read_text(encoding='utf-8').strip().removeprefix('gitdir: ')).resolve()
    common_file = git_dir / 'commondir'
    return (git_dir / common_file.read_text().strip()).resolve().parent if common_file.is_file() else ROOT


def environment(workspace: Path, cache: Path | None = None, runtime: Path | None = None) -> dict[str, str]:
    artifacts = ROOT / ".artifacts"
    cache = cache or Path(os.environ.get("ASTROPHOTOFLOW_DEV_CACHE", artifacts / "cache"))
    env = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(artifacts / "venvs/dev"),
           "UV_CACHE_DIR": str(cache / "uv"), "UV_PYTHON_INSTALL_DIR": str(artifacts / "managed-python"),
           "UV_PYTHON_BIN_DIR": str(artifacts / "python-bin"), "UV_PYTHON_INSTALL_REGISTRY": "0",
           "LOCALAPPDATA": str(artifacts / "local-app-data"), "APPDATA": str(artifacts / "app-data"),
           "TEMP": str(artifacts / "tmp"), "TMP": str(artifacts / "tmp"),
           "ASTROPHOTOFLOW_RUNTIME": str(runtime or artifacts / "local-app-data/AstroPhotoFlow/runtime/native-web-0.1.0"),
           "ASTROPHOTOFLOW_CONFIG": str(workspace / "config.toml"),
           "DISTRIBUTION": "localhost",
           "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    env["PATH"] = str(artifacts / ("venvs/dev/Scripts" if os.name == "nt" else "venvs/dev/bin")) + os.pathsep + env["PATH"]
    git_dir = ROOT / ".git"
    if git_dir.is_file():
        git_dir = (ROOT / git_dir.read_text(encoding="utf-8").strip().removeprefix("gitdir: ")).resolve()
    common = (git_dir / (git_dir / "commondir").read_text().strip()).resolve() if (git_dir / "commondir").is_file() else git_dir
    count = int(env.get("GIT_CONFIG_COUNT", "0"))
    for offset, directory in enumerate((ROOT, common.parent)):
        env[f"GIT_CONFIG_KEY_{count + offset}"] = "safe.directory"
        env[f"GIT_CONFIG_VALUE_{count + offset}"] = directory.as_posix()
    env["GIT_CONFIG_COUNT"] = str(count + 2)
    return env


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending.replace(path)


def fingerprint(paths: list[Path], versions: list[str]) -> str:
    digest = hashlib.sha256("\n".join(versions).encode())
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def frontend_matches(source: Path, installed: Path) -> bool:
    if not source.is_dir() or not installed.is_dir():
        return False
    source_files = {path.relative_to(source) for path in source.rglob("*") if path.is_file()}
    installed_files = {path.relative_to(installed) for path in installed.rglob("*") if path.is_file()}
    return source_files == installed_files and all(
        (source / path).read_bytes() == (installed / path).read_bytes() for path in source_files
    )


def prepare(report: dict) -> int:
    parser = argparse.ArgumentParser(description="Prepare this Worktree; build and start only when requested.")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--runtime-dir", type=Path, help="Use a private runtime below this worktree .artifacts")
    parser.add_argument("--frontend-assets", type=Path)
    parser.add_argument("--build", action="store_true", help="Build the current source instead of requiring existing assets")
    parser.add_argument("--start", action="store_true", help="Also prepare the CPU runtime and start the two services")
    parser.add_argument("--stop", action="store_true", help="Stop only this workspace through core control")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument('--bundle-source', action='append', default=[], metavar='PACKAGE=PATH')
    parser.add_argument('--clear-bundle-source', action='append', default=[], metavar='PACKAGE')
    parser.add_argument("--service-port", type=int, default=8190)
    parser.add_argument("--comfyui-port", type=int, default=8188)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    if not workspace.is_relative_to(ROOT / ".artifacts/workspaces"):
        parser.error("开发workspace必须位于本Worktree的.artifacts/workspaces下。")
    if sys.version_info[:2] != (3, 12):
        parser.error("请使用Python 3.12执行开发准备入口。")
    if not (1 <= args.service_port <= 65535 and 1 <= args.comfyui_port <= 65535) or args.service_port == args.comfyui_port:
        parser.error("两个服务需要不同的1–65535端口。")
    if args.build and args.frontend_assets:
        parser.error("--build和--frontend-assets只能选择一个。")
    if args.stop and (args.start or args.build or args.frontend_assets):
        parser.error("--stop不能同时准备或启动预览。")
    if args.stop and (args.bundle_source or args.clear_bundle_source):
        parser.error('--stop cannot change Bundle source bindings.')
    runtime = args.runtime_dir.resolve() if args.runtime_dir else None
    if runtime is not None and not runtime.is_relative_to((ROOT / ".artifacts").resolve()):
        parser.error("Private Feature runtime must remain below this worktree .artifacts")
    env = environment(workspace, args.cache_dir.resolve() if args.cache_dir else None, runtime)
    if args.offline:
        env["UV_OFFLINE"] = "1"
    for name in ("LOCALAPPDATA", "APPDATA", "TEMP", "UV_PYTHON_BIN_DIR"):
        Path(env[name]).mkdir(parents=True, exist_ok=True)
    report.update({"workspace": str(workspace), "config_path": env["ASTROPHOTOFLOW_CONFIG"],
              "runtime_path": env["ASTROPHOTOFLOW_RUNTIME"],
              "python": str(Path(env["UV_PROJECT_ENVIRONMENT"]) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")),
              "cache_dir": str(Path(env["UV_CACHE_DIR"]).parent)})
    logs = ROOT / ".artifacts/logs/dev-prepare" / report["run_id"]
    logs.mkdir(parents=True, exist_ok=True)

    def run(name: str, command: list[str]) -> str:
        stage = {"name": name, "log": str(logs / f"{name}.log")}
        report["stages"].append(stage)
        print(f"{name}…", file=sys.stderr, flush=True)
        clock = time.perf_counter()
        try:
            with Path(stage["log"]).open("w", encoding="utf-8") as log:
                result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                        stderr=log, text=True, encoding="utf-8", check=False)
                log.write(result.stdout)
            stage["exit_code"] = result.returncode
        except OSError as exc:
            Path(stage["log"]).write_text(str(exc), encoding="utf-8")
            stage.update(exit_code=None, error=str(exc))
            raise
        finally:
            stage["elapsed_seconds"] = round(time.perf_counter() - clock, 3)
        if result.returncode:
            raise RuntimeError(f"{name}失败（{result.returncode}），日志：{stage['log']}")
        return result.stdout

    def skip(name: str) -> None:
        report["stages"].append({"name": name, "reused": True, "elapsed_seconds": 0})

    try:
        tools = {name: shutil.which(name, path=env["PATH"]) for name in ("uv", "node", "pnpm")}
        missing = [name for name, path in tools.items() if path is None]
        if missing:
            raise RuntimeError("PATH中缺少工具：" + ", ".join(missing))
        versions = {name: run(name + "-version", [path, "--version"]).strip() for name, path in tools.items()}
        node = tuple(int(part) for part in versions["node"].removeprefix("v").split("."))
        if not (node >= (26, 8, 2) and node < (27,)) or versions["pnpm"] != "11.13.1":
            raise RuntimeError("需要Node >=26.8.2 <27和pnpm 11.13.1。")
        tracked = run("source", ["git", "ls-files", "-z"]).split("\0")
        report.update(head=run("head", ["git", "rev-parse", "HEAD"]).strip(),
                      dirty=bool(run("changes", ["git", "status", "--porcelain"]).strip()), tools=versions)
        cli = [report["python"], "-m", "astrophotoflow.cli"]
        if args.stop:
            report["preview"] = json.loads(run("stop", cli + ["stop", "--workspace", str(workspace)]))
            report["completed"] = report["preview"]["state"] == "completed"
            return 0 if report["completed"] else 1
        assets = args.frontend_assets.resolve() if args.frontend_assets else ROOT / ".artifacts/build/frontend"
        if args.build and not args.frontend_assets:
            candidate = main_checkout() / '.artifacts/build/frontend'
            if frontend_build_record.matches(candidate, ROOT, report['head'], versions['node'], versions['pnpm'], env):
                assets = candidate
                args.build = False
                report['frontend_reuse'] = str(candidate)
        if (args.start or args.frontend_assets) and not args.build:
            manifest = assets / "build-manifest.json"
            if not (assets / "index.html").is_file() or not manifest.is_file():
                raise RuntimeError("缺少已构建网页；指定--frontend-assets或显式使用--build。")
            built = json.loads(manifest.read_text(encoding="utf-8"))
            if built["commit"] != report["head"] or built.get("distribution") != "localhost":
                raise RuntimeError("网页产物SHA或发行类型不匹配；请提供同基点本地产物或使用--build。")
        stamp_path = ROOT / ".artifacts/dev-dependencies.json"
        stamps = json.loads(stamp_path.read_text(encoding="utf-8")) if stamp_path.is_file() else {}
        python_key = fingerprint([ROOT / name for name in ("uv.lock", "pyproject.toml", "setup.py")],
                                 [sys.version, sys._base_executable, sys.platform])
        inputs = [ROOT / name for name in tracked if name.startswith("frontend/") and
                  (name.endswith("/package.json") or name in {"frontend/pnpm-lock.yaml", "frontend/pnpm-workspace.yaml"}
                   or name.startswith("frontend/patches/"))]
        frontend_key = fingerprint(inputs, [versions["node"], versions["pnpm"], sys.platform])
        active = False
        config = workspace / "config.toml"
        if config.is_file() and Path(report["python"]).is_file():
            state = json.loads(run("workspace-state", cli + ["status", "--workspace", str(workspace)]))
            report["ready"] = state["ready"]
            if state.get("state") in {"unknown", "starting", "stopping"}:
                raise RuntimeError("workspace状态未知或控制操作尚未完成；先查询状态，不要重复准备。")
            active = bool(state["processes"])
            if active:
                same_assets = frontend_matches(assets, workspace / "web")
                if (not state["ready"] or args.build or stamps.get("python") != python_key
                        or stamps.get("frontend") != frontend_key or ((args.start or args.frontend_assets) and not same_assets)):
                    raise RuntimeError("workspace仍在运行且需要修改环境或网页；先用--stop停止自己的实例。")
        if stamps.get("python") == python_key and Path(report["python"]).is_file():
            skip("python-dependencies")
        else:
            stamps.pop("python", None)
            write_json(stamp_path, stamps)
            run("python-dependencies", [tools["uv"], "sync", "--locked", "--extra", "dev", "--python", sys._base_executable])
            stamps["python"] = python_key
            write_json(stamp_path, stamps)
        if stamps.get("frontend") == frontend_key and (ROOT / "frontend/node_modules/.modules.yaml").is_file():
            skip("frontend-dependencies")
        else:
            stamps.pop("frontend", None)
            write_json(stamp_path, stamps)
            command = [tools["pnpm"], "--dir", "frontend", "install", "--frozen-lockfile", "--ignore-scripts",
                       "--store-dir", str(Path(env["UV_CACHE_DIR"]).parent / "pnpm"), "--package-import-method=copy"]
            if args.cache_dir or os.environ.get("ASTROPHOTOFLOW_DEV_CACHE"):
                command.extend(["--cache-dir", str(Path(env["UV_CACHE_DIR"]).parent / "pnpm-metadata")])
            if args.offline:
                command.append("--offline")
            run("frontend-dependencies", command)
            stamps["frontend"] = frontend_key
            write_json(stamp_path, stamps)
        if args.build:
            run("build", [tools["pnpm"], "build"])
            report["dirty"] = bool(run("built-changes", ["git", "status", "--porcelain"]).strip())
        if args.start:
            report["runtime"] = json.loads(run("runtime", cli + ["runtime", "prepare", *(["--reuse-only"] if active else [])]))
        command = cli + ["workspace", "create", "--workspace", str(workspace), "--service-port", str(args.service_port),
                         "--comfyui-port", str(args.comfyui_port)]
        if args.start or args.build or args.frontend_assets or report.get('frontend_reuse'):
            manifest = json.loads((assets / "build-manifest.json").read_text(encoding="utf-8"))
            report["frontend"] = {"assets": str(assets), **manifest}
            if args.build or not frontend_matches(assets, workspace / "web"):
                command.extend(["--frontend-assets", str(assets)])
        report["workspace_result"] = json.loads(run("workspace", command))
        command = [report['python'], str(ROOT / 'scripts/dev_bundle_sources.py'), '--workspace', str(workspace)]
        for source in args.bundle_source:
            command.extend(['--bundle-source', source])
        for package_id in args.clear_bundle_source:
            command.extend(['--clear-bundle-source', package_id])
        report['development_sources'] = json.loads(run('bundle-sources', command))
        if any(value['state'] == 'failed' for value in report['development_sources'].values()):
            raise RuntimeError('Development Bundle generation failed; inspect development_sources in the receipt.')
        if args.start:
            report["preview"] = json.loads(run("start", cli + ["start", "--workspace", str(workspace)]))
            report["ready"] = report["preview"]["state"] == "completed"
            if not report["ready"]:
                raise RuntimeError("启动未完成，请根据回执查询状态，不要重复启动。")
        report["completed"] = True
        return 0
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        report.update(completed=False, error=str(exc))
        print(str(exc), file=sys.stderr)
        return 1


def main() -> int:
    if any(argument in {"-h", "--help"} for argument in sys.argv[1:]):
        return prepare({})
    receipt = ROOT / ".artifacts/dev-prepare.json"
    run_id = os.environ.get("ASTROPHOTOFLOW_DEV_PREPARE_RUN_ID")
    report = {}
    if run_id and receipt.is_file():
        previous = json.loads(receipt.read_text(encoding="utf-8-sig"))
        if previous.get("run_id") == run_id:
            report = previous
    report.update(run_id=report.get("run_id", uuid4().hex),
                  started_at=report.get("started_at", datetime.now(UTC).isoformat()),
                  arguments=sys.argv[1:], completed=False, ready=False)
    report.setdefault("stages", [])
    write_json(receipt, report)
    started = time.perf_counter()
    try:
        return prepare(report)
    except SystemExit as exc:
        report.update(completed=False, error=f"参数校验失败（{exc.code}）")
        return int(exc.code or 0)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        report.update(completed=False, error=str(exc))
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        finished = datetime.now(UTC)
        report.update(finished_at=finished.isoformat(),
                      prepare_elapsed_seconds=round(time.perf_counter() - started, 3),
                      elapsed_seconds=round((finished - datetime.fromisoformat(report["started_at"])).total_seconds(), 3))
        write_json(receipt, report)
        print(json.dumps({**report, "receipt": str(receipt)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
