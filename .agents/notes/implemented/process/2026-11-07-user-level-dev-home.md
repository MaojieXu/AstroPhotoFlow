# Agent Note: Move the development environment into a user-level content-addressed home

Status: Implemented

## Problem

开发环境原本都放在 worktree 的 `.artifacts` 下：`toolchains`、`managed-python`、`venvs/dev`、`cache`，而 ComfyUI runtime 在 `%LOCALAPPDATA%/AstroPhotoFlow/runtime`，两个位置各自迁移、没有统一归属。结果是：

- 每个 worktree 都要复制一套工具链、托管 Python 与开发 venv（约 0.2GB + 0.2GB + 0.3GB），runtime 仍是 1.9GB 级；`.artifacts` 累积到 65GB、66 万文件，没有清理入口。
- frontend 构建产物写死在 `.artifacts/build/frontend`，每个 workspace 再把整个产物 `copytree` 成 `web/`（dev workspace 83MB 中 78.4MB 是这份拷贝，12 个 workspace 重复约 0.8GB）。
- runtime 目录名固定为 `native-web-0.1.0`，同一指纹的 runtime 无法并存，也没有引用关系可判断“哪个 workspace 还在使用”。
- 两个常驻服务串行启动，ComfyUI 要等 asset-service 健康后才开始加载。

## Decision

- 开发环境统一放到用户级开发目录：`scripts/dev-home.json` 声明 Windows `%LOCALAPPDATA%\AstroPhotoFlow\dev`、POSIX `~/.local/share/astrophotoflow/dev`，`ASTROPHOTOFLOW_DEV_HOME` 可覆盖。`apf` 运行时通过 `core/workbench/paths.dev_home()` 读取同一模板；wheel 安装后模板不存在时返回 `None`，仍用应用数据目录。
- `scripts/bootstrap.ps1` 在工具准备后把旧 `.artifacts/{cache,toolchains,managed-python,python-bin}` 迁入开发目录（`managed-python` → `python`，`uv*`/`node-*`/`pnpm` → `toolchains`；目标已存在则跳过，旧 junction 先解除）。所有 `UV_*`、`LOCALAPPDATA`、`APPDATA`、`TEMP/TMP` 都指向开发目录。
- `scripts/dev_prepare.py` 用锁文件、基解释器、`sys.platform` 与 checkout 路径算 `python_key`，在 `<home>/venvs/<key[:20]>` 建 venv（每个 worktree 独立，避免 editable 安装指向别的 checkout），`venvs/current` 用 junction 指向当前 checkout 使用的 venv；`UV_PROJECT_ENVIRONMENT` 与 `PATH` 都指向它。依赖 stamp 记录 `python_key` 与前端 key。
- runtime 改为内容寻址：`runtime.runtime_identity()` 读并校验 vendor 归档与 manifest，`runtime_key()` 取指纹（去掉 uv 版本）sha256 前 20 位，`runtime.runtime_directory()` 依次解析 `ASTROPHOTOFLOW_RUNTIME` → `<home>/runtimes/<key>` → 旧默认目录；`prepare_runtime`/`control`/`doctor` 共用该解析，启动记录把 `runtime` 写进 `run/processes.json`。
- 构建产物内容寻址：`scripts/frontend_build_record.py` 构建完成后把产物发布到 `<home>/builds/<output digest[:24]>`，并把 `.artifacts/build/frontend` 换成指向该快照的 junction；workspace 的 `web` 也 junction 到同一快照，来源写 `run/web.json`。
- `runtime.install_frontend()` 只对来自 `builds/<key>` 的产物建链接（junction/symlink，失败回退复制），其他来源（测试、wheel 内的 `package/web`）保持复制语义，避免测试之间共享可变目录。
- 启动改为先依次拉起两个进程并记录，再并行等待健康（0.25s 轮询、90s/180s 各自超时），失败文案保持原样。
- pnpm 安装改用 `--package-import-method=hardlink`，仓库与开发目录同卷时可省磁盘；新增 `core/workbench/gc.py` 与 `apf env gc [--apply] [--older-than-days]`：扫描 `<home>/{venvs,runtimes,builds}`，跳过 `current`、junction、被任一 workspace `run/processes.json` 的 `runtime` 或 `run/web.json` 的 `store` 引用的项与未超龄项，同时列出仓库 `.artifacts` 下旧的工具链/venv/runtime 目录和过期 pytest 目录。

## Alternatives considered

- 只把缓存/_uv_ 移出 worktree、venv 与 runtime 保留：venv 仍占 0.3GB/份，且 runtime 复用不了。
- 把整个 `frontend/node_modules` 或 `web` 做成跨 worktree 共享的可写目录：Node 解析、pnpm 与构建会互相改写，失败时难以定位。
- 直接删除旧 runtime/build 快照：无法区分“仍被运行中 workspace 引用”的目录。
- 沿用串行启动：ComfyUI 冷启动本身就是主要耗时，串行等待 asset-service 健康没有收益。

## Consequences

- 升级后的首次 bootstrap 会迁移旧目录（本机实测 cache/uv 等约 300MB + 托管 Python/工具链约 0.4GB，已在目标存在时跳过）；首次准备还会按新 key 建 venv、runtime 与构建快照。
- 实测（Windows，本机）：主 checkout 热启动 `prepare` 17.7s（runtime 复用 2.9s、启动 11.2s）；此前 18.1s，差异主要在事务性检查与并行启动。新建第二个 workspace 首次 `prepare` 15.3s（runtime 复用 2.9s、启动 10.1s），workspace 磁盘增量约 0.5MB（`web` 为 junction；旧做法复制 78MB）。`apf env gc` dry-run 在仓库 `.artifacts` 报出 2.31GB 可回收旧目录（`.artifacts/local-app-data` 1.95GB、`venvs` 0.31GB、`tmp` 0.06GB），未自动删除。
- 开发目录默认在 `%LOCALAPPDATA%`，与仓库同在 C 盘时 pnpm hardlink 有效；跨卷时 pnpm 会退化，需把 `ASTROPHOTOFLOW_DEV_HOME` 指到与仓库同卷的位置。
- venv key 含 checkout 路径：每个 worktree 独立 venv，缓存与 runtime 跨 worktree 共享。第二个真 worktree 的端到端验收在本机沙箱未完成：沙箱内 Node 子进程 `fs.symlink` 返回 `EPERM`，pnpm 因此退化为 junction 链接，`vue-tsc` 的嵌套依赖解析失败（全新 copy 与 hardlink 安装都如此）；改用 pwsh 建的 symlink 共享主 checkout 的 `node_modules` 时，Node 读取主 checkout 路径又报 `operation not permitted`（沙箱读限制）。同一原因也使把 `%LOCALAPPDATA%` 内容迁入工作区后残留 `Everyone:(DENY)(DC)` 继承 ACL，uv 写解释器缓存报 `os error 5`（对 cache/venvs 执行 `icacls /inheritance:r` 重新授权后可继续）。这些都是沙箱限制，需在真实开发机复验，不是本次代码逻辑。
- `apf env doctor` 增加开发目录与 `venvs/current` 检查；node/pnpm 与 `package.json` 固定版本不一致时提示改走 bootstrap。WSL 适配仍搁置。
