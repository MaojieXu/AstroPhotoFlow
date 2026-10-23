# AstroPhotoFlow

AstroPhotoFlow 是运行在 ComfyUI 中的本地天文资产工作台。资产管理服务独立运行，ComfyUI 扩展通过同源代理访问服务。

## 当前状态

资产管理第一阶段在 Git 分支 `feature/database` 上实现：工作区提供项目、设备和拍摄配置管理，并只读查询共享资产及项目固定版本引用。产品资产库保持空库；本阶段没有文件导入、解析、预览、任务队列或资产写入功能。

三个资产管理阶段都在 `feature/database` 开发。第一、第二阶段完成后停止并保留成果；只有三阶段完成、各阶段验收及必要的集成回归通过且无阻断问题，才具备合并到 `dev` 的条件。阶段范围见[资产管理三阶段计划](docs/资产管理三阶段实施计划.md)，第一阶段技术契约见[技术与接口设计](docs/第一阶段技术与接口设计.md)。

## ComfyUI 扩展

在当前 checkout 构建并链接扩展：

```bash
export PATH="/home/maojiexu/.nvm/versions/node/v22.22.2/bin:$PATH"
npm exec --yes --package=pnpm@11.13.1 -- pnpm --dir frontend install --frozen-lockfile
npm exec --yes --package=pnpm@11.13.1 -- pnpm --dir frontend typecheck
npm exec --yes --package=pnpm@11.13.1 -- pnpm --dir frontend test
npm exec --yes --package=pnpm@11.13.1 -- pnpm --dir frontend build
bash scripts/link-comfyui.sh
```

构建会生成 `web/astrophotoflow.js` 与 CSS，由根目录 `__init__.py` 加载。链接脚本根据当前 checkout 计算扩展路径；ComfyUI 的集成宿主为 `/home/maojiexu/Workshop/ComfyUI`，已存在的目标链接不会被覆盖。前端沿用 Vue 3、TypeScript、Vite、Tailwind 4、Pinia 和 Zod，主题与字体继承宿主。

## 独立资产服务

需要 Python 3.11+ 和 uv。首次设置时，将 [服务配置示例](service/config.example.toml) 复制到 `~/.config/astrophotoflow/config.toml`，再按需调整数据目录和 ComfyUI 来源。不要覆盖已有配置。默认服务绑定 `127.0.0.1:8190`，数据目录是 `~/.local/share/astrophotoflow`。

```bash
uv sync --project service
uv run --project service apf-service db status
uv run --project service apf-service serve
```

新数据库在首次服务启动时由 Alembic 初始化。已有数据库需检查 revision 后显式运行 `uv run --project service apf-service db upgrade`；升级前会使用 SQLite backup API 保存一致备份。服务令牌由首次启动生成，保存在数据目录中，仅当前用户可读；浏览器不接收令牌。

更完整的启动、升级和恢复步骤见[服务 README](service/README.md)。实际应用导出的接口定义见 [OpenAPI 快照](service/openapi.json)。

## 仓库模板

本仓库同时保留 ComfyUI 官方 Cookiecutter Extension 模板，供后续生成其他扩展项目：

```bash
python -m pip install cookiecutter
cookiecutter .
```

默认项目名为 `ComfyUI-AstroPhotoFlow`，Python 模块名为 `astrophotoflow`。

## 参考项目与许可

可借鉴的上游仓库及许可证边界见需求文档的[开源项目借鉴与许可证](docs/AstroPhotoFlow_Requirements_v1.0/06_开源项目借鉴与许可证.md)和[调研来源与核验记录](docs/AstroPhotoFlow_Requirements_v1.0/08_调研来源与核验记录.md)。参考源码应单独克隆和审阅，不要放入本仓库提交。

本仓库保留上游模板的 GPL-3.0 许可与版权声明。复用或分发第三方代码时，请遵守其原始许可证。原侧栏截图和验收记录是历史入口测试证据；本阶段只重验了新增或修改的行为。
