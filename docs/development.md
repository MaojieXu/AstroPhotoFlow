# 开发环境

[English](development.en.md) | 中文

开发在 Windows x64 上通过 `scripts/bootstrap.ps1` 固定入口准备：它选择并校验工具，把参数转给 `scripts/dev_prepare.py`（`--watch` 转给 `scripts/dev_frontend.py`），不修改全局 PATH、Python 注册或默认 workspace。其他平台没有验收路径。

## 环境与版本

| 依赖 | 版本 | 说明 |
| --- | --- | --- |
| Python | 3.12 | `pyproject.toml` 要求 `>=3.12`；bootstrap 优先使用本机可用的 3.12，否则安装托管版本 |
| uv | 0.13.5 | Python 依赖与工具链入口 |
| Node.js | `>=26.8.2 <27` | 前端构建与测试 |
| pnpm | 11.13.1 | 由 `package.json` 的 `packageManager` 固定 |

锁文件是根 `uv.lock` 与 `frontend/pnpm-lock.yaml`。根 `package.json` 是任务入口；前端依赖与锁文件在 `frontend`，不在仓库根执行 `pnpm install`。

## 固定入口

Windows x64 用 `scripts/bootstrap.ps1` 作为唯一启动入口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 --workspace .artifacts/workspaces/dev --build --start
```

| 参数 | 作用 |
| --- | --- |
| `--workspace` | 必填；独立 workspace 目录 |
| `--build` | 构建当前源码的前端产物 |
| `--frontend-assets` | 复用已核对的网页产物目录 |
| `--start`、`--stop` | 启动两个服务；只停止该 workspace |
| `--watch --port <端口> --strictPort` | 运行 Vite 热更新 |
| `--service-port`、`--comfyui-port` | 领域服务与 ComfyUI 端口，默认 8190 / 8188 |
| `--runtime-dir`、`--cache-dir` | 私有 runtime 与工具、包缓存目录 |
| `--offline` | 只使用本地缓存，不联网 |
| `--bundle-source`、`--clear-bundle-source` | 绑定或解除开发 Bundle 源码 |

工具缺失时下载固定归档到 `.artifacts/toolchains` 并校验；缓存默认存放在主仓库 `.artifacts/cache`，可用 `--cache-dir` 或环境变量 `ASTROPHOTOFLOW_DEV_CACHE` 覆盖。回执写 `.artifacts/dev-prepare.json`，日志写 `.artifacts/logs/dev-prepare/<run_id>`。

## 常用命令

| 任务 | 命令 |
| --- | --- |
| 安装开发依赖 | `uv sync --locked --extra dev` |
| 准备依赖与 workspace | `pnpm dev:prepare --workspace .artifacts/workspaces/<name> --start` |
| 构建前端产物 | `pnpm build` |
| 前端热更新 | `pnpm build:watch --workspace .artifacts/workspaces/<name> --port 32589 --strictPort` |
| MCP 开发热加载 | `pnpm dev:mcp --workspace .artifacts/workspaces/<name> --port 8765` |
| Python 测试 | `uv run --locked --no-sync pytest -q --basetemp=.artifacts/pytest-<task>` |
| 前端单元测试 | `pnpm test` |
| 浏览器测试 | `pnpm test:browser` |
| 架构边界检查 | `pnpm check:boundaries` |
| 文档门禁 | `pnpm check:docs` |
| 接口生成物 | `pnpm docs:api` |

## 产物与回执

- `.artifacts/build`：前端、引擎与 Python 构建产物；`frontend/build` 是源码，不是产物。
- `.artifacts/dist`：发行物。
- `.artifacts/venvs/dev`、`.artifacts/toolchains`、`.artifacts/managed-python`、`.artifacts/cache`：开发环境与缓存。
- `.artifacts/workspaces/<name>`：独立 workspace，含配置、数据库、对象、预览与运行记录。
- `.artifacts/dev-prepare.json`：最近一次准备的参数、阶段与结果。
- `.artifacts/logs/dev-prepare/<run_id>`：bootstrap 与准备阶段的分阶段日志。

## 调试入口

- 回执的 `completed` 表示准备请求完成，`ready` 表示服务就绪，都不表示页面已展示；页面地址以回执的 `web_url` 为准。
- 浏览器验证用 `APF_WEB_URL` 指向自己的回执地址，用 `APF_TEST_WORKSPACE` 指定自己的 workspace。
- 原生队列与重启场景必须显式设置 `APF_ALLOW_NATIVE_QUEUE=1`、`APF_ALLOW_WORKBENCH_RESTART=1`，未启用记为 skip。
- 并行 pytest 必须各自指定不同的 `--basetemp=.artifacts/pytest-<task>`。
- Python 或服务代码改动后显式重启自己的实例；MCP 热加载不会重启领域服务。
