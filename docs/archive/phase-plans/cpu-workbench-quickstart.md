# AstroPhotoFlow CPU 本地工作台快速开始

此工作台面向 Windows x64、Python 3.12 和 CPU。pip/uv 安装不需要 Node.js 或 Git；`apf init` 会在 `%LOCALAPPDATA%\AstroPhotoFlow\runtime\` 准备固定版本的 ComfyUI、独立 CPU venv 和依赖。ComfyUI 依赖使用随包提供的 Windows/Python 3.12 锁文件；PyTorch 和 torchvision 使用固定版本的 CPU wheel。uv 管理的 Python 位于 `%APPDATA%\uv\python\`；工作台不改系统 PATH 或 Python 注册表。ComfyUI 不会下载模型。

## 安装

在 Windows PowerShell 中进入仓库根目录；下面示例的 wheel 位于 `dist\windows-closure-20261023`。使用 pip：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install .\dist\windows-closure-20261023\astrophotoflow-0.1.0-py3-none-any.whl
```

或使用 uv：

```powershell
uv venv --python 3.12 .venv
uv pip install --python .\.venv\Scripts\python.exe .\dist\windows-closure-20261023\astrophotoflow-0.1.0-py3-none-any.whl
```

## 初始化和启动

初始化时指定 workspace 路径和隔离端口。省略 `--workspace` 时，`apf init` 会交互询问路径。可重跑 init；已有配置和数据不会被覆写。

```powershell
.\.venv\Scripts\apf.exe init --workspace .\test\workspace --service-port 18190 --comfyui-port 18188
.\.venv\Scripts\apf.exe start --workspace .\test\workspace
.\.venv\Scripts\apf.exe status --workspace .\test\workspace
```

工作台数据位于 workspace：`data\astrophotoflow.sqlite3`、托管原图和预览、`input`、`output`、`logs`、`context`、`comfyui-user`。配置中的数据根相对 `config.toml`，整份 workspace 可在停止后搬迁。运行环境和 ComfyUI 源码位于 LocalAppData，不随 workspace 搬迁。

ComfyUI 前端地址为 `http://127.0.0.1:18188/`。加载 AstroPhotoFlow 扩展后，在“天文”侧栏打开工作区；外部 MCP/CLI 改动后点击现有刷新按钮。

当前验收数据位于 `test\workspace-moved`；新 workspace 可从 `test\workspace` 开始。

停止工作台：

```powershell
.\.venv\Scripts\apf.exe stop --workspace .\test\workspace
```

## CLI 导入与参数编辑

```powershell
$env:ASTROPHOTOFLOW_CONFIG = (Resolve-Path .\test\workspace\config.toml).Path
.\.venv\Scripts\apf.exe import-photo .\photo.fit
.\.venv\Scripts\apf.exe task <task-id>
.\.venv\Scripts\apf.exe assets list
.\.venv\Scripts\apf.exe assets get <asset-id>
.\.venv\Scripts\apf.exe assets parameters <asset-id> --base-revision 1 --exposure-seconds 0
.\.venv\Scripts\apf.exe assets parameters <asset-id> --base-revision 2 --clear exposure_seconds
```

参数 PATCH 只包含命令行里指定的字段；`--clear` 显式清空一个字段，未提供字段保持原值。成功响应返回新的 revision，应使用它进行下一次更新。revision 冲突会失败退出，不会自动覆盖。

## Codex MCP

打印包含绝对命令路径和 workspace 配置的官方 Codex 注册命令：

```powershell
.\.venv\Scripts\apf.exe mcp-config --workspace .\test\workspace
```

若 Codex 尚未注册此服务器，在 PowerShell 执行输出的官方 `codex mcp add ...` 命令。已连接时不要重复注册；不要手动覆盖其他 MCP 配置或凭据。工具包括单照片导入、任务查询、资产列表/单项查询和参数 PATCH。MCP 通过流式文件上传，不把照片编码成 base64。MCP 进程不会初始化 workspace，也不控制工作台生命周期。

## 搬迁 workspace

先执行 `apf stop --workspace .\test\workspace`，再复制整个 workspace 文件夹到新位置。启动和 CLI 操作都显式传入新位置，例如：

```powershell
.\.venv\Scripts\apf.exe start --workspace .\test\workspace-moved
$env:ASTROPHOTOFLOW_CONFIG = (Resolve-Path .\test\workspace-moved\config.toml).Path
.\.venv\Scripts\apf.exe assets list
```

ComfyUI 原生 workflow 保存在 `comfyui-user\default\workflows`，随 workspace 一起搬迁。不要只复制 SQLite 主文件；整个目录含数据库 WAL 状态、托管原图、预览、令牌和工作流设置。若 Codex MCP 要改用新 workspace，重新运行 `apf mcp-config --workspace .\test\workspace-moved`，只在确有需要时执行输出的 `codex mcp add` 命令；既有连接不会自动跟随 workspace 移动。
