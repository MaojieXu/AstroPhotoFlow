# AstroPhotoFlow

基于 ComfyUI 源码定制的本地天文网页工作台。原生工作台始终保留节点画布，素材库和工作流按顺序放在节点库下方，共用原生可调整宽度的侧栏。设备管理位于素材库“导入”旁；切换或收起侧栏不替换画布。

已有素材、数据集、项目、设备、使用组合、拍摄预设、固定版本校准关联、预览和回收站功能保留。CLI 与 58 个 MCP 工具通过同一领域服务访问数据。软件适配、节点制作、项目工作流及运行记录、结果比较及本地上下文记忆仍待实施。

完整目标与阶段边界见[现行产品需求与范围](docs/requirements/README.md)。平台通过 MCP 接入外部通用 Agent；不内置 Agent 或保存完整聊天。本地记忆目标为用户偏好、项目背景、工作流经验与主动提交的交接摘要。Windows 优先，Linux／WSL 后续，支持范围以实际验收为准。

[③概要设计](src/astrophotoflow/modules/software/README.md)已明确固定软件包与配套节点的按需安装、确认更新及统一MCP发现。目标中的全部业务工具由⑤统一做本地embedding＋关键词检索，每次最多10个候选、完整定义按需读取；模型不可用明确关键词降级。这些功能尚未实现，本地检索模型不承担Agent推理，也不改变现有58个数据工具。

[④概要设计](src/astrophotoflow/modules/nodes/README.md)已收敛为workspace统一可编辑节点库、可选测试与确认更新；参数采用新版默认值，只断变化端口，最近测试从⑤读取。Python及复合仍S6，复合内部局部修改不影响其他工作流，导出安装保留后续目标；新增能力尚未实现。

[⑤概要](src/astrophotoflow/modules/workflows/README.md)及[数据设计](docs/architecture/data-models/05-workflows.md)统一工作流、执行和Agent交互：复用原生JSON保存／另存、会话撤销、图转换与队列，补项目关联、必要运行记录、多次自动图像预览和当前控制。首版Agent依托打开的活动画布，切走暂停后续编辑／提交，已有运行继续；手改接管、明确交回和安静接续保持。不保存永久逐编辑历史或服务端草稿，重要方案另存；新增功能仍待实现，现行体系为五模块。

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

模块职责、权威状态及跨模块边界统一见[总架构](docs/architecture/overview.md)，阶段依赖见[开发路线](docs/development/platform-roadmap.md)。源码与验证入口见[模块导航](docs/architecture/module-map.md)，目录和导入规则见[文件架构](docs/architecture/repository-layout.md)。

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

保留上游 LICENSE 与版权通知。ComfyUI 0.42.0 和前端 1.57.1 的来源、提交及归档散列记录在 [vendor 清单](src/astrophotoflow/vendor/comfyui-source.json)。前端上游许可证随发行包保存。现行需求与历史附件见 [docs/requirements](docs/requirements/README.md) 和 [docs/archive](docs/archive/README.md)。
