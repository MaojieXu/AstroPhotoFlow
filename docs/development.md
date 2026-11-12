# 开发环境

[English](development.en.md) | 中文

在单个 Git 检出目录开发。安装和启动见 [Quickstart](../README.md#quickstart)。完整工作台在 Windows x64 验收。

## 工具和依赖

| 依赖 | 版本 | 说明 |
| --- | --- | --- |
| Python | 3.12.15 | 由 uv 按 `.python-version` 管理 |
| uv | 0.13.5 | 安装 Python 依赖并在项目环境中运行命令 |
| Node.js | `>=26.8.2 <27` | 前端构建与测试 |
| pnpm | 11.13.1 | 由根 `package.json` 的 `packageManager` 固定 |

`uv.lock` 对应仓库内的 `.venv`，`frontend/pnpm-lock.yaml` 对应 `frontend/node_modules`。pnpm 使用平铺布局，让 Windows 终端在缺少目录符号链接权限时也能解析依赖。包下载缓存由包管理器管理。

## 目录

- `.artifacts/build/frontend` 是网页构建产物，`.artifacts/dist` 是发行物。`frontend/build` 是源码。
- `.artifacts/runtime` 是源码 checkout 的固定 CPU 引擎目录，首次 `apf init` 准备，后续校验并复用。需要隔离引擎时用 `ASTROPHOTOFLOW_RUNTIME` 指定绝对路径。
- `.artifacts/workspaces/dev` 保存日常工作台的配置、数据库、素材和工作流。`apf init` 将网页复制到该 workspace 的 `web`，`--no-activate` 保留默认 workspace 指针。清理构建产物时保留工作台目录。

当前处于数据库 v1 开发期，现有 workspace 内容均为可替换的测试数据。schema 调整直接更新单一初始化基线，按需替换或重建测试 workspace，无需保留旧测试内容或编写旧开发版本的迁移。正式进入数据库 v2 开发时，开始保留 v1 数据并设计、验证升级迁移。这里的 v1／v2 指数据库开发阶段。

修改 ORM 后运行 `pnpm generate:database-baseline`，审查生成的约束，并用 `tests/core/test_image_management_migration.py` 验证新建数据库与 ORM 一致。原地重建前，经 core 控制入口停止目标实例，核实目标绝对路径与清理范围。已确认的 v1 测试 workspace 可按开发任务直接替换；workspace 外部的原始素材仍按原件保护约定处理。

## 常用命令

| 任务 | 命令 |
| --- | --- |
| 停止开发工作台 | `uv run --locked --no-sync apf stop --workspace .artifacts/workspaces/dev` |
| 打开开发工作台 | `pnpm web` |
| 单独启动 Vite | `pnpm build:watch --workspace .artifacts/workspaces/dev --port 32589 --strictPort` |
| MCP 开发热加载 | `pnpm dev:mcp --workspace .artifacts/workspaces/<test> --port 8765` |
| 开发 Bundle 源码 | `uv run --locked --no-sync python scripts/dev_bundle_sources.py --help` |
| Python 测试 | `uv run --locked --no-sync pytest -q --basetemp=.artifacts/pytest-<task>` |
| 安装 Python 测试和打包工具 | `uv sync --locked --extra dev` |
| 前端单元测试 | `pnpm test` |
| 架构边界检查 | `pnpm check:boundaries` |
| 文档门禁 | `pnpm check:docs` |
| 接口生成物 | `pnpm docs:api` |
| 检查开发环境 | `uv run --locked --no-sync apf env doctor --workspace .artifacts/workspaces/dev` |
| 清理过期临时产物 | `uv run --locked --no-sync python scripts/prune_artifacts.py`（加 `--apply` 才删除） |

## Bundle 源码联调

在仓库根目录为已准备的测试 workspace 启用源码发现，再把开发仓库检出到 `bundles/` 的一级子目录。各 checkout 单独管理。

```powershell
uv run --locked --no-sync python scripts/dev_bundle_sources.py --workspace .artifacts/workspaces/bundle-test --repo-bundles
git clone --branch dev https://github.com/MaojieXu/AstroPhotoFlow-Siril.git bundles/siril
```

保存适配器后，下一次执行或预览使用新代码。声明更新后，已打开的页面刷新节点目录。参数或端口定义已变的旧实例显示不可用，从目录重新添加新版。用 `--clear-repo-bundles` 解除目录绑定，或用 `--bundle-source <id>=<路径>` 绑定指定目录。

## 调试

- 实际地址以 `apf start` 或 `apf status` 返回的 `web_url` 为准。实际端口见 workspace 的 `run/processes.json`，首选端口保存在 `config.toml`。
- 浏览器与 MCP 验证使用仓库内独立的测试 workspace。浏览器和并行测试的设置见[测试说明](testing.md)。
- `pnpm web` 打开 Vite 页面并监听平台 Python 源码。工作台忙时终端显示重启受阻的原因，任务结束后可再次保存或显式重启。Ctrl+C 结束 Vite 和监听，工作台服务可用上表的停止命令关闭。
- 更新依赖、引擎或静态网页前先停止自己的实例。单独使用 `pnpm build:watch` 时，Python 变更后显式重启工作台。MCP 热加载只刷新 MCP 进程。
