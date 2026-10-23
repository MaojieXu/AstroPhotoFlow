# AstroPhotoFlow

AstroPhotoFlow 是运行在 ComfyUI 中的本地天文资产工作台。资产服务以独立进程运行；ComfyUI 加载 Extension 时会复用或自动启动服务，浏览器通过同源代理访问。

## 当前状态

资产管理第一阶段已在 Git 分支 `feature/database` 上验收；第二阶段已在该分支完成素材导入、资料编辑、数据集、项目选用和 FITS 元数据／预览闭环及 S2-AT-01 至 S2-AT-11 验收。产品库不预置演示资产。格式支持范围及验证证据见[验收记录](docs/第二阶段验收记录.md)和[资产格式支持矩阵](docs/资产格式支持矩阵.md)。

当前数据库闭环按两个阶段在 `feature/database` 开发。第一、第二阶段及必要集成回归验收通过且无阻断问题后，报告合并就绪；第三阶段暂缓，不作为当前数据库闭环的合并门槛。实际合并等待用户指令。阶段范围见[资产管理实施计划](docs/资产管理三阶段实施计划.md)，接口契约见[第一阶段设计](docs/第一阶段技术与接口设计.md)和[第二阶段设计](docs/第二阶段技术与接口设计.md)。

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
uv sync --project service --locked
uv run --project service apf-service db status
```

ComfyUI 扩展启动时会复用已认证且健康的资产服务，或通过 PATH、`~/.local/bin/uv` 自动启动服务并等待就绪。ComfyUI 启动不会安装依赖或迁移已有数据库。若 `db status` 显示 revision 不是当前版本，先审阅并显式运行 `uv run --project service --locked --no-sync apf-service db upgrade`；升级前会用 SQLite Backup API 保存一致备份。新数据库在首次服务启动时初始化。服务令牌由首次启动生成，保存在数据目录中，仅当前用户可读；浏览器不接收令牌。

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
