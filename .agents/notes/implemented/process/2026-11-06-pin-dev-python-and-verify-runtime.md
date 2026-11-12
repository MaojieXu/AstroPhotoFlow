# Agent Note: Pin the managed development Python and verify the fixed runtime

Status: Implemented

## Problem

开发环境里同时存在两套 3.12 解释器：`scripts/bootstrap.ps1` 优先借用系统 Python（本机是 Anaconda 3.12.4）来创建 `.artifacts/venvs/dev`，而 `apf runtime prepare` 用 uv 托管目录安装 3.12.15 并创建 ComfyUI 的 venv。托管 Python 的目录名从 `cpython-3.12-…` 变成 `cpython-3.12.15-…` 后，旧 venv 内的 trampoline 仍指向不存在的绝对路径；`prepare_cpu_runtime` 的复用判定只检查 `.apf-runtime.json` 指纹、`comfyui-env/Scripts/python.exe` 是否存在和 commit 标记，不实际执行解释器，于是坏环境被当作可复用，启动阶段才以“comfyui 启动失败”暴露。

同一类“状态分散、无人核对”的问题还出现在：启动成功后把实际端口穿过全局 `~/.config` 锁回写进 workspace 的 `config.toml`（实际地址同时存在回执、`run/processes.json` 与配置三处）；已有 workspace 收到不一致的 `--service-port` 时静默忽略；默认 workspace 指针失效时只报“未设置默认 workspace”；没有检查环境与清理过期产物的入口。

## Decision

- `scripts/bootstrap.ps1` 固定 `uv python install --no-registry 3.12.15` + `uv python find 3.12.15`（`UV_PYTHON_PREFERENCE=only-managed`），不再优先系统 Python；已有 `.artifacts/venvs/dev` 的 `pyvenv.cfg` 指向其他解释器时重建；通过 `ASTROPHOTOFLOW_DEV_PYTHON` 把基解释器传给 `scripts/dev_prepare.py`，后者用 `uv sync --python` 该路径。
- `core/workbench/runtime.py` 新增 `probe_python()`：实际执行 `import torch`，成功才返回版本、`base_prefix` 与 torch 版本。runtime 指纹加入 uv 版本，receipt 记录本次探测结果；复用要求指纹、标记、探测三者同时成立及其结果与记录一致。探测失败且不是 reuse-only 时删除 `comfyui-env` 重建；重建后仍失败则明确报“内置解释器无法运行（import torch 失败）”。
- 端口语义改为单向：`config.toml` 是唯一配置来源，已有配置与显式 `--service-port`/`--comfyui-port` 不一致时报错并给出修改方式；启动把实际端口写进 `run/processes.json` 的 `actual_ports`，不再回写 `config.toml`，也不再依赖全局配置锁。
- 默认 workspace 缺失或指向无 `config.toml` 的目录时给出可执行的修复提示（`apf init --workspace …` 或显式 `--workspace` / `ASTROPHOTOFLOW_CONFIG`）；新增 `apf env doctor` 检查解释器、uv/node/pnpm、runtime 指纹与探测、workspace 端口与默认指针；新增 `scripts/prune_artifacts.py`，默认 dry-run，清理过期 tmp、准备日志与 pytest 临时目录。

## Alternatives considered

- 继续“系统 Python 优先、托管兜底”：无法让新机器复现同一环境，也无法解释上次为什么坏。
- 复用判定增加文件时间戳或 `pyvenv.cfg` 文本比较：解释器可能文件仍在但 DLL 依赖缺失，只有实际执行 `import torch` 才能证明可用。
- 保留启动回写 `config.toml`：把运行结果写回用户配置会让“配置”与“最近一次运行”互相覆盖，并迫使启动路径依赖用户级配置锁。
- 为端口冲突只告警不报错：本次评估确认这是静默失效的来源，明确失败更符合仓库“让失败清晰可见”的约定。

## Consequences

- 升级到本次版本后首次准备会重建开发 venv 与 ComfyUI runtime（各一次，依赖缓存命中，预计数十秒到两分钟）；之后恢复复用。运行中的服务必须先 `--stop`，否则 bootstrap 会明确提示 venv 被占用。
- `config.toml` 不再随启动变化；需要实际端口时读回执或 `run/processes.json`。旧 workspace 的 `config.toml` 无需迁移。
- uv 0.13.5 的 `uv python install` 会维护 `managed-python/cpython-3.12-windows-x86_64-none` → `cpython-3.12.15-windows-x86_64-none` 的别名 junction；bootstrap 每次运行都会执行该安装，因此手工删除别名后重启会自动恢复（实测删除后 `comfyui-env/Scripts/python.exe` 立即报 `entity not found`，重启时 bootstrap 重建别名、runtime 探针通过并复用）。`comfyui-env` 的 `base_prefix` 仍记录该别名路径。
- 实测耗时：首次准备（开发 venv + runtime 重建）prepare 68.4s（venv 8.4s、runtime 10.6s、启动 32.4s）；之后热启动 18.1s（runtime 复用 2.7s、启动 11.1s）。
- `apf env doctor` 的 runtime 指纹比较忽略 uv 版本（不同安装的 uv 仍运行同一份固定 runtime），其余字段不一致才报 `fail`；node/pnpm 与 `package.json` 的固定版本不一致时提示改走 bootstrap。
- `apf env doctor` 与 `scripts/prune_artifacts.py` 不改变业务模块；WSL 适配仍搁置，本次只收敛 Windows 开发路径。
