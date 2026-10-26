# 七模块源码导航

本表对应[开发路线](../development/platform-roadmap.md)和[文件架构](repository-layout.md)。目录位置已经确定，功能状态以实际实现及验收证据为准。接任务时先确定所属模块，再读取局部 README／AGENTS、相关 contracts 和测试。

| 模块 | Python 落点 | 前端落点 | 当前公开入口与状态 | 验证入口 |
|---|---|---|---|---|
| ① 公共基础 | `src/astrophotoflow/core` | UI 包 `src/core`；原生框架提供 Vue／Pinia 与主题 | 已有配置、数据库、认证、进程基础；前端 core 仅文档占位 | `pytest tests/core tests/packaging -q` |
| ② 数据与资产 | `src/astrophotoflow/modules/data` | UI 包 `src/modules/data` | 已有数据功能；Python public.py／routes.py，UI 包导出 Workspace；新节点交接协议仍待实现 | `pytest tests/modules/data -q`、根 `pnpm test` |
| ③ 软件接入 | `src/astrophotoflow/modules/software` | UI 包 `src/modules/software` | 文档占位，无 AstroPhotoFlow 外部软件适配器实现 | 首次实现时补充真实工具与验证 |
| ④ 节点构建 | `src/astrophotoflow/modules/nodes` | UI 包 `src/modules/nodes` | 文档占位；可复用原生节点机制，制作与热发布待实现 | 首次实现时补充节点契约与测试 |
| ⑤ 工作流 | `src/astrophotoflow/modules/workflows` | UI 包 `src/modules/workflows`；原生桥接和画布 | 项目工作流权威仅文档占位，已有原生编辑与保存加载继续使用 | 原生 GraphView／侧栏测试、浏览器保存加载 |
| ⑥ 运行 | `src/astrophotoflow/modules/runs` | UI 包 `src/modules/runs` | 托管运行仅文档占位；ComfyUI 队列和导入任务不是完整外部运行闭环 | 首次实现时验证真实执行与产物 |
| ⑦ 人与 Agent | `src/astrophotoflow/modules/collaboration` | UI 包 `src/modules/collaboration`；原生桥接 | 协作仅文档占位；已有数据 MCP 在 interfaces/mcp | `pytest tests/integration -q`；图写入和接管待实现 |

表内 pytest 命令使用 `uv run --locked --no-sync` 前缀，前端使用锁定的 Node／pnpm。

## 跨模块设施

| 位置 | 职责与读取方式 |
|---|---|
| `src/astrophotoflow/contracts` | 公共模型与纯校验；API 事实结合实际 HTTP 路由，OpenAPI 是生成快照 |
| `src/astrophotoflow/interfaces/http` | 应用与模块路由装配、系统健康、apf-service |
| `src/astrophotoflow/interfaces/cli`、`interfaces/client` | apf 命令处理与具名 HTTP 操作；根 client.py／cli.py 保留公开入口 |
| `src/astrophotoflow/interfaces/mcp` | 现有 58 个数据工具及协议适配，调用同一 HTTP 服务 |
| `src/astrophotoflow/comfyui/proxy.py` | 固定引擎同源网关，来源校验、服务端令牌、流式请求及请求 ID |
| `frontend/src/platform/astrophotoflow` | NativeShell、原生素材侧栏及注册；通过 UI 包公开入口挂载 |
| `frontend/packages/astrophotoflow-ui` | 一个私有源码组件包；公开入口 src/index.ts，内部模块有自己的入口 |
| `tests/architecture` 与前端 `.dependency-cruiser.json` | 导入和消费边界；根 `pnpm check:boundaries` |

## 任务说明最小内容

每项任务写清：所属模块、实际入口、需读取的契约、允许修改的路径、依赖的公开操作、验收命令和结果证据。跨模块变更分别说明两侧责任，不复制数据库事实或另建状态权威。

大模型可以设计或解释接口，最终字段与行为仍需核对实现。小模型按局部任务和测试入口实现；不要求读取整个上游 workspace。未实现模块先明确真实接口与验收，再创建代码，不因目录已经存在而填充空类或假数据。
