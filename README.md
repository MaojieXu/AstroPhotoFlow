# AstroPhotoFlow

基于 ComfyUI 源码定制的本地天文网页工作台。原生工作台始终保留节点画布，素材库和工作流按顺序放在节点库下方，共用原生可调整宽度的侧栏。设备管理位于素材库“导入”旁；切换或收起侧栏不替换画布。

已有素材、数据集、项目、设备、使用组合、拍摄预设、固定版本校准关联、预览和回收站功能保留。CLI 与 58 个 MCP 工具通过同一领域服务访问数据。完整 Agent、天文处理适配、结果比较和项目记忆仍属后续范围。

## 源码开发

需要 Python 3.12、uv、Node.js 26.8.2–26.x 和 pnpm 11.13.1。

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$PWD/.artifacts/venvs/dev"
pnpm --dir frontend install --frozen-lockfile --ignore-scripts
pnpm build
uv sync --locked --extra dev --python 3.12
uv run --locked --no-sync pytest -q
pnpm test
```

`engine/ComfyUI` 为固定版本引擎源码，`frontend` 为原生前端完整 workspace，`src/astrophotoflow` 保存按模块组织的平台 Python 源码、客户端与启动器。业务界面与组件测试位于 frontend/packages/astrophotoflow-ui，产品构建共用原生 Vue/Pinia；模块位置见 docs/architecture/module-map.md。

七模块源码落点见[模块导航](docs/architecture/module-map.md)，文件迁移与边界见[文件架构](docs/architecture/repository-layout.md)。

详细入口见[文档索引](docs/README.md)、[开发流程](docs/development/README.md)及[实现与验证矩阵](docs/development/test-matrix.md)。

## 运行与发行

```powershell
uv run --locked --no-sync apf init --workspace .artifacts/workspaces/dev --service-port 31390 --comfyui-port 31388 --frontend-assets .artifacts/build/frontend --no-activate
uv run --locked --no-sync apf start --workspace .artifacts/workspaces/dev --no-activate
uv run --locked --no-sync apf status --workspace .artifacts/workspaces/dev
uv run --locked --no-sync apf stop --workspace .artifacts/workspaces/dev
```

打开 `http://127.0.0.1:31388/#/workflows`。首次初始化准备固定 CPU 依赖；无需下载生成式图像模型。安装发行 wheel 后无需 Node.js、Git 或另行安装 ComfyUI。原生运行环境与旧版 CPU runtime 分开，业务数据保存在指定 workspace。

```powershell
uv run --locked --no-sync python scripts/build_release.py
uv run --locked --no-sync python scripts/verify_distribution.py
```

wheel 与 sdist 携带完整已构建网页资源及定制引擎归档；从 sdist 重建 wheel 无需 Node.js。工作台统一启动网页引擎和内部 FastAPI 服务，服务令牌保留在 workspace，浏览器使用同源业务网关。

## 来源与许可

保留上游 LICENSE 与版权通知。ComfyUI 0.42.0 和前端 1.57.1 的来源、提交及归档散列记录在 [vendor 清单](src/astrophotoflow/vendor/comfyui-source.json)。前端上游许可证随发行包保存。冻结需求与历史附件见 [docs/requirements](docs/requirements/README.md) 和 [docs/archive](docs/archive/README.md)。
