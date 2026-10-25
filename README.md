# AstroPhotoFlow

本地天文素材工作台，使用 ComfyUI 承载界面，提供素材／数据集、项目、设备和拍摄配置管理，以及 CPU 工作台、CLI 和初版 MCP。

当前支持分阶段异步导入、资料编辑、筛选排序、100 px 缩略图与按需1080 px大图、组／照片回收站、设备组合／拍摄预设，以及固定版本校准关联。Agent、外部软件节点、完整工作流管理和结果比较属于后续开发范围。[文档索引](docs/README.md)区分当前实现、冻结需求与历史记录。

## 源码开发

需要 Python 3.12、Node.js 22.13+、Corepack 和 uv；在仓库根执行：

```powershell
corepack pnpm install --frozen-lockfile
corepack pnpm build
$env:UV_PROJECT_ENVIRONMENT = "$PWD/.artifacts/venvs/dev"
uv sync --locked --extra dev --python 3.12
uv run --locked --no-sync pytest -q
corepack pnpm test
```

开发运行采用 `.env + config.toml`：从 `.env.example` 创建本机 `.env`，从 `config.example.toml` 创建 `.artifacts/workspaces/dev/config.toml`。`.env` 由 uv 显式加载；工作区端口、数据目录和素材根目录统一写入 TOML。启动命令及首次准备步骤见[开发流程](docs/development/README.md)。

所有实现位于 `src/astrophotoflow`，测试在 `tests`，维护脚本在 `scripts`。前端输出 `build/frontend`，发行包输出 `dist`，新测试报告、临时 workspace 和缓存放入忽略的 `.artifacts`。详细规则见[开发流程](docs/development/README.md)。

## 安装与使用

发行维护者运行：

```powershell
uv run --locked --no-sync python scripts/build_release.py
uv run --locked --no-sync python scripts/verify_distribution.py
```

wheel 和 sdist 携带已构建前端资源，最终用户安装不需要 Node.js 或 Git。CPU 工作台面向 Windows x64/Python 3.12，固定 ComfyUI 0.42.0 和其前端 1.57.1；首次初始化准备 CPU 运行环境，需要下载依赖。安装、启动、workspace 搬迁及 MCP 配置见[工作台使用](docs/development/workbench.md)。

ComfyUI checkout 扩展仍通过根 `__init__.py` 发现；将本仓库链接到自己的 `custom_nodes` 后，先完成前端构建和根 Python 依赖同步。令牌保存在 workspace 数据目录，浏览器通过同源代理调用服务。[接口说明](docs/api/README.md)列出结构化 CLI 和58个 MCP 工具，保留原五工具名称。[项目 Skill](.agents/skills/astrophotoflow-library/SKILL.md)提供素材管理流程。

## 许可与来源

保留上游 Cookiecutter Comfy Extension 的 [LICENSE](LICENSE) 和版权通知；模板生成器已从产品工程移除。内置 ComfyUI 的固定来源、提交和散列见 [vendor 清单](src/astrophotoflow/vendor/comfyui-source.json)。第三方软件与依赖沿用其各自许可，原始开源参考记录保存在[冻结需求](docs/requirements/v1.0/06_开源项目借鉴与许可证.md)及历史验收中。
