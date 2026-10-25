# 开发与配置

需要 Python 3.12、Node.js 22.13+、Corepack 和 uv。根 `uv.lock`、`pnpm-lock.yaml` 管理现有版本；开发环境统一为 `.artifacts/venvs/dev`。

## 依赖、构建与测试

在仓库根 PowerShell 执行：

```powershell
corepack pnpm install --frozen-lockfile
corepack pnpm build
$env:UV_PROJECT_ENVIRONMENT = "$PWD/.artifacts/venvs/dev"
uv sync --locked --extra dev --python 3.12
uv run --locked --no-sync pytest -q
corepack pnpm test
```

## 应用配置

- `.env.example`：提交的本机环境模板；复制为 `.env` 后使用，实际 `.env` 不提交。
- `config.example.toml`：仓库根运行配置模板。开发实例使用 `.artifacts/workspaces/dev/config.toml`，端口为 31388/31390，数据目录 `data` 相对该 TOML 文件解析。
- `.env` 保存 `ASTROPHOTOFLOW_CONFIG` 和输出编码；端口、数据目录、来源与素材根目录只写在 TOML 中。
- 服务令牌仍由程序生成到 workspace/data/service.token，不复制进 dotenv 或 Git。

配置由 `astrophotoflow.config` 统一解析。顺序为显式路径、ASTROPHOTOFLOW_CONFIG、active-workspace 指针、用户默认配置。选定配置无效会失败，不静默切换 workspace。现有回环地址、端口、素材根目录和字段约束保持有效。

首次准备开发 workspace：

```powershell
Copy-Item .env.example .env
uv run --locked --no-sync --env-file .env apf init --workspace .artifacts/workspaces/dev --service-port 31390 --comfyui-port 31388 --frontend-assets build/frontend
```

初始化会准备固定的 CPU runtime。开发源码通过 --frontend-assets 显式提供构建资源；发行 wheel 已自带资源。插件及资源位于当前 workspace 内，后续重新构建可同步到该目录：

```powershell
$assets = Join-Path $PWD '.artifacts/workspaces/dev/comfyui-data/custom_nodes/AstroPhotoFlow/assets'
New-Item -ItemType Directory -Force $assets | Out-Null
Copy-Item build/frontend/astrophotoflow.js,build/frontend/astrophotoflow.css $assets
```

其他 worktree 使用各自的环境、workspace 和端口。CPU runtime 已准备时，在初始化命令中添加 `--reuse-runtime --no-activate`，启动时添加 `--no-activate`，即可复用 CPU 依赖且不修改用户默认 workspace。并发数通过 TOML 的 `[ingestion]` 配置，`file_workers` 默认 2，`preview_workers` 默认 1。

本机开发 workspace 已准备后，日常命令为：

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$PWD/.artifacts/venvs/dev"
uv run --locked --no-sync --env-file .env apf start
uv run --locked --no-sync --env-file .env apf status
uv run --locked --no-sync --env-file .env apf stop
```

uv 选择项目环境发生在 dotenv 注入前，所以 UV_PROJECT_ENVIRONMENT 要在启动 uv 前设置，不能仅放入 `.env`。上面的命令同时适用于本机示例和文档中的测试；测试命令不加载开发 `.env`，避免混入真实运行配置。

## MCP 与共享环境

本机 AstroPhotoFlow MCP 注册使用开发环境内的 uv.exe，工作目录切到仓库根，以 `run --locked --no-sync --env-file <绝对.env路径> apf mcp` 启动。注册条目只注入 UV_PROJECT_ENVIRONMENT，不再固定另一份 ASTROPHOTOFLOW_CONFIG 或旧 PYTHONPATH。修改应用路径时只改 `.env`，重新连接该 MCP 后生效。

前端代理、CLI、MCP、后端与工作台读取同一 TOML。当前默认 workspace 指针也指向开发实例。VS Code 本机默认解释器和已有 Black/Pylint 工具使用同一开发环境；编辑器个人设置不进入 Git。

## 发行与目录规则

```powershell
uv run --locked --no-sync python scripts/build_release.py
uv run --locked --no-sync python scripts/verify_distribution.py
```

源码在 src/astrophotoflow，测试在 tests，维护脚本在 scripts。前端输出 build/frontend，Python 中间产物 build/python，发行物 dist，新报告与临时目录 .artifacts。实际运行配置、数据库及真实样本不进入发行包；sdist 包含配置示例和已构建前端资源。

旧 service/、test/ 运行目录退役后不再作为启动入口。原始 Astro Dataset 保持原位，独立 RAW/HEIF 样本集中在 tests/data/reference-samples。完整安装和 workspace 迁移说明见[工作台使用](workbench.md)，当前状态见[开发上下文](current-context.md)。

设置记录的搜索、筛选、批量回收、恢复、永久删除预览和设备快照规则见[设置记录管理](settings-management.md)。

- [最终 bug 修复与设备资料解耦验收](final-bugfix-acceptance.md)
