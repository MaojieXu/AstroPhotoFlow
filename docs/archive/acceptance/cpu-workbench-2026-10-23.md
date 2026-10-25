# CPU 本地工作台包验收记录（2026-10-23）

## 初次验收的分支和发行文件（历史记录）

- 分支：`feature/bundle`；基线提交：`c8366e640eeab97f3336a6b3c12c80678a235f69`。本轮未提交、未推送。
- 产品：`astrophotoflow 0.1.0`，CLI 入口 `apf`。
- Windows 原生 release build wheel：`dist/windows-final-20261023/astrophotoflow-0.1.0-py3-none-any.whl`，13,388,087 bytes。
- Windows 原生 sdist：`dist/windows-final-20261023/astrophotoflow-0.1.0.tar.gz`，13,526,823 bytes。构建脚本在同一次运行里由 sdist 重建 wheel。
- 使用说明：[CPU本地工作台快速开始.md](CPU本地工作台快速开始.md)；构建入口：[build_release.py](../scripts/build_release.py)。
- 固定 ComfyUI 源码位于包内 `astrophotoflow/vendor/comfyui-0.42.0.zip`，13,415,862 bytes。来源清单记录 `Comfy-Org/ComfyUI`、提交 `1a82e6d01f395b43275c77acd289af1eb7090bb9`、ComfyUI 0.42.0、前端包 1.57.1；SHA-256 `95b5146939bcb4c33d17334001698beec5c88b83493beb13a8ba75a86e033967`。上游 LICENSE 保留在归档内。

## 本轮实际验证

- Windows 原生 Node 23.8.0、Corepack/pnpm 11.13.1 下，release 脚本成功执行锁文件安装、`vue-tsc --noEmit`、Vite 构建、sdist 和 wheel 生成；sdist 重建 wheel 也通过。
- Windows Python 3.12.14 隔离 venv 中通过 uv 安装发行 wheel；另一 Python 3.12.15 venv 中通过 pip 安装 wheel。安装后入口从源码目录外启动。
- Windows 原生 `apf init --workspace test\workspace --service-port 18190 --comfyui-port 18188` 成功；再次执行 init 保留现有 workspace。ComfyUI 0.42.0 使用 CPU `torch 2.14.1+cpu`、`torchvision 0.29.1+cpu`、前端包 1.57.1，Comfy Python 为 3.12.15。日志显示设备 CPU，CUDA 不可用，未下载模型。uv 管理的 Python 不进入 PATH 或 Windows Python 注册表。
- Windows `apf start/status/stop` 通过。重复 start 保持同一组资产服务和 ComfyUI PID；stop 将这两个进程停掉。端口 18192 的独立监听进程令 start 明确非零失败；它在冲突和工作台 stop 后仍可连接，确认启动器未自动换端口或停止无关进程。
- 搬迁后运行 `apf start --workspace test\workspace-moved` 会更新当前 workspace 指针；不传 workspace 的 `status` 和 `task` 随后都读取迁移后位置。
- Windows CLI 以流式方式导入本地 FITS 副本，大小 46,823,040 bytes，任务完成。MCP SDK 2.3.0 的 Windows `Client(StdioServerParameters(...))` 真实 stdio 调用列出工具、查询任务/资产、设置 `exposure_seconds=0` 和 `gain=0`、修改曝光值、显式 null 清空，并确认旧 revision 返回 `is_error=true`、`REVISION_CONFLICT` 和 request ID。Windows CLI 参数选项也完成零值、修改及 `--clear`。搬迁后资产最终 revision 为 9，`AssetVersion` 数量为 1。
- Windows Codex 当前配置已启用 `astrophotoflow`；通过真实 Codex MCP `get_asset` 调用查询 `549ba287-a458-48d6-abd5-ef3bd8771ce4` 成功，返回 `heart_nebula`、`status=active`、revision 9，当前曝光参数为 12.5 秒。
- ComfyUI 首页、扩展 JS 地址和 AstroPhotoFlow 代理健康路由均通过 HTTP 200。代理健康路由返回 `database=ready` 和 revision `0005_dataset_removal_version_snapshot`。
- 2026-10-24 复查时，工作台原为 partial（ComfyUI 已停止）；清理残留状态并重启后，`apf status` 为 running，ComfyUI 首页与扩展 JS 地址均返回 HTTP 200。
- 停止 workspace 后将整个 `test\workspace` 复制到 `test\workspace-moved`，从新位置重新启动。数据库、托管 FITS 和预览继续可读；托管图片位置为相对路径 `data/objects/.../source.fit`，缩略预览 HTTP 200（image/jpeg，4,589 bytes）。
- Linux 隔离回归：`uv run --project . --locked --extra test pytest -q tests/test_bundle_config.py tests/test_proxy.py tests/test_service_manager.py`，12 passed。历史资产管理验收继承既有记录，不重跑。
- 测试素材、workspace、uv venv、令牌和运行日志均未加入 Git 或发行包。原始素材文件只读，未使用或迁移旧预览数据库和 Siril 数据库。`.gitignore` 保留指定 Astro Dataset 规则并新增 `/test/workspace/`。

## 初次验收记录中的待办（已由后续收尾完成）

上面的初次记录当时尚未确认前端手动刷新。后续通过真实 Codex MCP 完成了新图导入、查询、参数修改和显式 `null` 清空，并在 ComfyUI 扩展中分别手动刷新确认。迁移后的最终 workspace 是 `test\workspace-moved`；初次验收记录的其余历史数据未被覆盖。具体调用和观察结果见本页“收尾补验与交付”及 [结构化收尾证据](CPU本地工作台收尾证据_2026-10-23.json)。

## 2026-10-23 Windows 工作区环境重建

本轮以当前 Windows checkout 为源码，重新安装前端依赖、准备原生 Python 环境并重建发行包。原 `service/.venv` 指向 Linux Python，已备份至 `.venv/backups/service-linux-20261023`；新的 `service/.venv` 使用 Windows CPython 3.12.15，通过 `uv sync --project service --locked --python 3.12 --extra test` 安装。

- 产品构建及安装环境：`.venv/windows-rebuild-20261023`，Windows CPython 3.12.15。
- 前端：`corepack pnpm install --frozen-lockfile --force`、`corepack pnpm run build` 和 `corepack pnpm test` 通过；本轮 **74 passed / 12 files**。
- 后端定向回归：`python -m pytest service/tests/test_bundle_config.py service/tests/test_proxy.py service/tests/test_service_manager.py -q`，本轮 **12 passed**。首次 Windows 执行复现了测试夹具把反斜杠直接写入 TOML、使用 `/tmp` 路径和固定 POSIX 启动断言的问题；仅修正这些跨平台夹具及断言后通过。
- 产品环境 `python -m pip check` 通过。源码、服务和受管理 ComfyUI 的 Python 缓存已用 Windows Python 强制重新编译。
- 在重建的产品环境执行 `python -m build --outdir dist/windows-rebuild-20261023`，生成 sdist 后从该 sdist 重建 wheel；旧发行产物保留。
- 新 wheel：`dist/windows-rebuild-20261023/astrophotoflow-0.1.0-py3-none-any.whl`，13,388,087 bytes，SHA-256 为 `1c2aeb5abe4d1f5059ddf4b5aa3091912c6e1fe63f3389b21e1c08d28c4f7b63`。
- 新 sdist：`dist/windows-rebuild-20261023/astrophotoflow-0.1.0.tar.gz`，13,526,853 bytes。
- 新 wheel 已通过 uv 安装到产品环境；在源码目录外确认服务模块及 Alembic 资源来自 `site-packages`。
- 当前项目 `test/workspace` 已初始化并后台启动，ComfyUI 为 `http://127.0.0.1:18188/`，资产服务端口为 18190。旧测试工作台停止后，其两个监听端口均已关闭；新工作台启动后首页、扩展 JS/CSS 和代理健康接口均为 HTTP 200，数据库 revision 为 `0005_dataset_removal_version_snapshot`。
- HTTP 提供的 JS/CSS 与本轮源码构建结果、新 wheel 内资源逐字节一致。
- 使用新产品环境中的 MCP SDK 从源码目录外启动 stdio MCP，成功发现五个工具，并调用 `get_asset` 取得 `heart_nebula`、revision 9、曝光 12.5 秒，`is_error=false`。当时真实 Codex MCP 也已连接；这段是初次验收记录，不替代后续单图闭环记录。

本段记载的前端手动刷新在初次验收时仍待完成；后续补验结果如下。

## 收尾补验与交付

### 真实 Codex MCP 单图闭环

- 使用真实 Codex MCP `import_photo` 导入 `tests\data\Astro_Dataset\extracted\47 Tucanae (also designated as NGC 104 and Caldwell 106)\c546e85f-13c7-4a41-80d6-a8b2b90c311a\Karl - result_3570s.fit`。文件大小为 95,892,480 bytes；原素材保持只读，导入由服务托管副本。
- `import_photo` 返回 task `6857772a-3d5c-4a67-a3ff-f350770ebbde`。随后用真实 Codex MCP `get_import_task` 查询，状态 `completed`，1 项成功、0 项失败；同一项生成 asset `f0f90f4c-f111-411a-991d-02c06232086f`，版本 `916e7fe6-003f-4d13-a6dc-2d22d70137ea`，托管内容 95,892,480 bytes，availability `available`。
- 对同一 asset 的真实 Codex MCP `get_asset` 初始查询为 revision 1、`exposure_seconds=30.0`。`update_asset_parameters` 以 `base_revision=1` 写入 `42.5`，返回 revision 2；再以 `base_revision=2` 显式发送 `exposure_seconds: null`，返回 revision 3。再次 `get_asset` 确认参数为 `null`、原图仍 available，内容 hash 为 `blake3:25a381709ea7f0506cea6d6a5731dba9ac9e4f9c61f36d4d50b69376f6938570`。
- ComfyUI AstroPhotoFlow 扩展中手动刷新后，修改状态显示 `42.5 s`；清空后手动刷新显示 `—`。历史资产 `heart_nebula` 仍显示 `12.5 s`。

### 进程生命周期、workspace 搬迁和 workflow

- 对原 workspace 重复执行 `apf start --workspace test\workspace` 时，PID 始终为 32520 和 17504；命令返回“已在运行”，没有新增进程。之后 `apf stop --workspace test\workspace` 后 `status` 为 `stopped`、processes 为空，18188/18190 均无监听。
- 在 `apf start --workspace test\workspace-moved` 的进程记录中，父 PID 与监听 PID 不同；通过 psutil 确认监听进程分别是被记录进程的 uv Python 子进程。对迁移 workspace 执行 `stop` 后，父 PID、子 PID 均不存在且两个端口均关闭；没有把 Windows venv 启动器的父子 PID 差异误判为孤儿进程。
- ComfyUI 原生空白 workflow `AstroPhotoFlow Migration Check`（workflow id `f3a9a097-8376-46df-817a-5bbb410145c8`）已保存到 `comfyui-user\default\workflows\AstroPhotoFlow Migration Check.json`。停止写入后将 `test\workspace` 完整复制到 `test\workspace-moved`；15 个文件、143,811,296 bytes 的 SHA-256 清单逐项一致。原 workspace 保留。
- 对迁移副本使用显式 `--workspace test\workspace-moved` 和 `ASTROPHOTOFLOW_CONFIG` 路径运行 `apf init/start`。CLI 查询确认新 asset revision 3 和 `exposure_seconds=null`；原图仍 available。ComfyUI 进程重启、浏览器整页重载后，workflow 标题恢复为 `AstroPhotoFlow Migration Check`；扩展重新手动刷新后仍显示迁移资产曝光 `—` 与历史资产 `12.5 s`。
- 最终 `apf status`（不传 `--workspace`）为 `running`，默认 workspace 指向 `test\workspace-moved`。当前受管 PID 为 66052 和 48704；重复 start 保持同一 PID。CLI 启动命令已退出后，工作台继续运行；随后真实 Codex MCP `get_asset` 再次成功读到迁移后的 asset revision 3。现有 Codex MCP 配置未修改、未重复注册。

### Windows CPU 依赖与 Codex 配置

- 新增 `src\astrophotoflow\vendor\comfyui-0.42.0-windows-py312.lock`，锁定固定 ComfyUI 0.42.0 requirements 在 Windows x64/Python 3.12 的 83 个依赖版本。torch 和 torchvision 不在该锁中，初始化仍通过 `https://download.pytorch.org/whl/cpu` 安装 `2.14.1+cpu` 和 `0.29.1+cpu`。
- `workbench.py` 在 Windows 初始化时实际读取随 wheel/sdist 打包的锁；非 Windows 仍使用该 ComfyUI 源码的 requirements。对当前 Comfy Python 执行 `uv pip install --dry-run -r ...lock` 为 `Checked 83 packages`、`Would make no changes`；从新 wheel 执行 `apf init --workspace test\workspace-moved ...` 时分别检查 CPU 组件 2 个包与锁内 83 个包，均无版本变更。`uv pip show` 确认 ComfyUI frontend 1.57.1、torch `2.14.1+cpu`、torchvision `0.29.1+cpu`。
- 新 wheel/sdist 位于 `dist\windows-closure-20261023`。wheel 包含锁文件，不含 `__pycache__`/`.pyc`；构建和源码外安装后初始化通过。
- `apf mcp-config --workspace test\workspace-moved` 现在只输出官方 `codex mcp add ...` PowerShell 命令，不再输出不符合 Codex TOML schema 的 `mcpServers` JSON。快速开始指引已同步；当前已工作的 Codex MCP 连接保留不动。
- 结构化结果见 [CPU 本地工作台收尾证据](CPU本地工作台收尾证据_2026-10-23.json)。初次 Windows 前端 74 项和后端 12 项测试仍按前文作为历史证据引用，本节的新增证据为真实 MCP 调用、前端交互、迁移、启动/停止与新 wheel 初始化检查。
