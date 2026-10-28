# 五模块源码与验证导航

本页负责定位源码、公开入口、消费契约和验证位置。职责、权威归属与调用方向以[总架构](overview.md)为准；开发依赖以[路线](../development/platform-roadmap.md)为准；目录及产物规则见[文件架构](repository-layout.md)。接任务时先确定模块，再读局部 README／AGENTS 和实际契约。

状态核对日期：2026-10-27。下列“已有”依据源码检查，历史通过范围见[验证矩阵](../development/test-matrix.md)，不代表本轮重跑。占位目录没有公开业务实现，也没有对应测试命令。

[数据结构初稿总入口](data-models/README.md)集中提供①至⑤对象、关键字段、关系和待确认事项；它是设计导航，不是新增源码、ORM或测试入口，各模块概要开头均有对应链接。

## 1. 源码归属

Python 根为 `src/astrophotoflow`，自研 UI 根为 `frontend/packages/astrophotoflow-ui/src`；表内链接指向完整位置。模块不是独立进程或页面。

| 模块 | Python | 自研 UI | 原生／引擎接入与当前状态 |
|---|---|---|---|
| ① 公共基础设施 | [core](../../src/astrophotoflow/core) | [core](../../frontend/packages/astrophotoflow-ui/src/core) | M1候选含配置／启停／维护及网页表单，共用原生Vue；用户验收与集成另记 |
| ② 数据与资产管理 | [modules/data](../../src/astrophotoflow/modules/data) | [modules/data](../../frontend/packages/astrophotoflow-ui/src/modules/data) | 数据与界面已有，原生素材侧栏挂载 Workspace；节点交接和记忆未实现 |
| ③ 外部软件接入与环境 | [modules/software](../../src/astrophotoflow/modules/software) | [modules/software](../../frontend/packages/astrophotoflow-ui/src/modules/software) | 概要及前端分工已成文，两侧仍仅文档，无软件MCP／适配器实现 |
| ④ 节点构建与发布 | [modules/nodes](../../src/astrophotoflow/modules/nodes) | [modules/nodes](../../frontend/packages/astrophotoflow-ui/src/modules/nodes) | 两侧仍仅文档；原生注册／子图可复用，workspace节点、确认更新和连线重映射待实现／验证 |
| ⑤ 工作流、执行与Agent交互 | [modules/workflows](../../src/astrophotoflow/modules/workflows) | [modules/workflows](../../frontend/packages/astrophotoflow-ui/src/modules/workflows) | 统一概要已成文，两侧仅文档；原生机制可复用，项目关联、运行／预览持久保存、在线MCP和当前控制待实现 |

原生产品桥接统一位于 [frontend/src/platform/astrophotoflow](../../frontend/src/platform/astrophotoflow)，可调用原生 Store 和画布；业务 UI 只通过包导出接入，不能反向导入原生应用。引擎保留在 [engine/ComfyUI](../../engine/ComfyUI)，产品的注册及执行桥接沿该固定源码和 Python comfyui 集成边界验证，不另建引擎树。

## 2. 按模块读取与验收

<a id="module-1"></a>

### ① 公共基础设施

- **概要设计**：[唯一公共模块概要](../../src/astrophotoflow/core/README.md)维护十二类能力、七条交接链路、需求覆盖及阶段缺口；[前端归属](../../frontend/packages/astrophotoflow-ui/src/core/README.md)只补充界面和原生桥接分工。
- **入口与调用**：core/config.py 解析配置；core/workbench.py 管理安装、启动停止；core/http.py、errors.py 和 database 提供认证、错误、连接与迁移。HTTP 应用装配在 interfaces/http/app.py，不能让 core 反向导入业务；Alembic 元数据装配例外见文件架构。
- **消费契约**：contracts/common.py和已有HTTP错误、认证、request ID规则；request ID不保证防重，数据revision不代表工作流版本。M1配置／采用值、CLI重启、维护互斥及网页表单已实现；MCP控制、网页诊断、日志轮转／清理和检索资源管理仍待后续；原生进度可复用，领域状态桥接待验证，检索用途及索引归⑤。
- **验证位置**：[tests/core](../../tests/core)、[tests/packaging](../../tests/packaging)、[代理回归](../../tests/interfaces/comfyui/test_proxy.py)、[数据服务中的认证／锁／备份测试](../../tests/modules/data/test_service.py)及架构导入检查。M1重启／采用值／公共界面测试见tests/core、私有UI tests/core/workbench.test.ts及tests/browser/platform-workflows.mjs，真实证据见[矩阵](../development/test-matrix.md#m1-foundation)；原生进度测试不代替跨进程桥接。
- **命令**：`uv run --locked --no-sync pytest tests/core tests/packaging tests/interfaces/comfyui -q`。发行和生命周期集成另按开发流程执行，不由单元检查代替。

<a id="module-2"></a>

### ② 数据与资产管理

- **概要设计**：[唯一数据模块概要](../../src/astrophotoflow/modules/data/README.md)覆盖十二类能力、核心对象、概念交接及八条验收链路；[前端分工](../../frontend/packages/astrophotoflow-ui/src/modules/data/README.md)维护界面与宿主边界。现有机制与待补项目结果／共享、来源、比较、治理及记忆分别标明。
- **入口与调用**：data/routes.py 装配已有 HTTP 路由；public.py 当前仅导出导入线程池、中断任务状态标记、预览补齐和 DisplayPreviews。资产、集合、项目、设备、校准等实现保持在模块内部，其他模块不能直接访问 models.py 或 SQLite。
- **前端与桥接**：UI 的 modules/data/index.ts 导出 Workspace，经包 src/index.ts 被原生 LibrarySidebarTab.vue 消费；既有表单、素材、设备与预览行为保留。节点输入解析、用户选择的完整结果保存、必要来源、比较和本地记忆的公开操作尚需实现；项目作用域模型不代表已有结果登记流程。
- **消费契约**：contracts 中 assets、imports、datasets、projects、equipment、setups、calibration、trash、previews 及 common；UI 消费模型在 modules/data/api/contracts.ts。新增部分遵守[数据引用边界](overview.md#boundary-data)。
- **验证位置**：[tests/modules/data](../../tests/modules/data)、[导入配置集成](../../tests/integration/test_import_presets.py)、[UI 数据测试](../../frontend/packages/astrophotoflow-ui/tests/modules/data)和 tests/fixtures；原件、固定版本、快照、revision、null／0、校准及清理保护分别验收。
- **命令**：`uv run --locked --no-sync pytest tests/modules/data tests/integration/test_import_presets.py -q`、根 `pnpm test`。未来工作流及运行引用保护需另补联调，不能由现有数据回收站测试宣称已覆盖。

<a id="module-3"></a>

### ③ 外部软件接入与环境

- **概要设计**：[唯一软件概要](../../src/astrophotoflow/modules/software/README.md)维护软件包、配套节点、状态及交接验收；[前端分工](../../frontend/packages/astrophotoflow-ui/src/modules/software/README.md)只补充界面及宿主责任。软件包安装、节点发现、确认更新和真实调用均为待补目标。
- **入口与调用**：Python和UI目前仍仅README／AGENTS，没有可调用适配器或路由；消费core／contracts，接收⑤明确的文件交接，向④提供操作和固定实现、向⑤提供外部目录，不接管资产登记、节点发布、统一排名或运行权威。
- **消费契约**：[数据引用](overview.md#boundary-data)、[节点绑定](overview.md#boundary-nodes)、[运行回执](overview.md#boundary-runs)及[统一检索目标](../requirements/README.md#tool-discovery)。软件包、配套节点、实际操作、准确版本、依赖、许可和素材在首次任务锁定，当前没有软件或检索Pydantic契约，不编造命令。
- **首次验收**：S2真实软件包安装、许可准备、节点发现及网页／Agent同目录，⑤同步最多10候选和模型失败显式关键词降级；与④验证绑定／使用，与⑤按实际适配验证软件调用、取消及结果。Siril、ASTAP、PixInsight是候选，PixInsight桥接仍需原型，AT-33／AT-34无完成证据。
- **验证位置与命令**：尚无独立测试；首次实现时在所属模块测试和真实工具集成中新增，记录实际命令与环境，不使用占位命令。

<a id="module-4"></a>

### ④ 节点构建与发布

- **概要设计**：[唯一节点概要](../../src/astrophotoflow/modules/nodes/README.md)和[数据设计](data-models/04-nodes.md)维护workspace统一节点库、可选测试和确认更新；[前端分工](../../frontend/packages/astrophotoflow-ui/src/modules/nodes/README.md)补界面及宿主责任，新增能力均未实现。
- **入口与调用**：Python／UI仍仅README和AGENTS，无public.py、路由或节点契约。调用③公开操作，供⑤消费定义；试运行由应用装配与⑤协调，不让④反向导入⑤，用户选择的完整结果由②检查保存，当前控制和实际画布应用核对归⑤。
- **原生接入**：[nodes.py](../../engine/ComfyUI/nodes.py)、[server.py](../../engine/ComfyUI/server.py)、[app.ts](../../frontend/src/scripts/app.ts)和[litegraphService.ts](../../frontend/src/services/litegraphService.ts)可复用注册。实际加载和保存分别核对；原生输出按位置保存，自定义同方向唯一命名及重排连线保持仍需桥接。
- **子图及转换**：[subgraphStore.ts](../../frontend/src/stores/subgraphStore.ts)、[subgraphService.ts](../../frontend/src/services/subgraphService.ts)、[executionUtil.ts](../../frontend/src/utils/executionUtil.ts)可复用。S6复合内部图及外露映射，工作流局部修改不回写节点库或其他图；导出安装另行规划。
- **消费契约及首次验收**：[节点边界](overview.md#boundary-nodes)、[原型门槛](overview.md#prototype-gates)及[NODE-F01～F08](../../src/astrophotoflow/modules/nodes/README.md#phases)；跨项目使用、可选测试、最近结果及旧内容提示、更新确认、参数重置、端口增删改及重排、实际加载与执行中保护。
- **验证位置与命令**：[迟到注册](../../frontend/src/services/litegraphService.lateRegistration.test.ts)、[蓝图](../../frontend/src/stores/subgraphStore.test.ts)、[子图序列化](../../frontend/src/lib/litegraph/src/subgraph/SubgraphSerialization.test.ts)、[转换](../../frontend/src/utils/executionUtil.test.ts)仅为原生基础。尚无平台节点测试或命令，首次实现补所属模块及②③⑤真实联调，不用上游测试替代。

<a id="module-5"></a>

### ⑤ 工作流、执行与Agent交互

- **唯一设计及归属**：[统一概要](../../src/astrophotoflow/modules/workflows/README.md)、[必要数据](data-models/05-workflows.md)及[前端分工](../../frontend/packages/astrophotoflow-ui/src/modules/workflows/README.md)。工作流、运行与Agent交互业务统一进入workflows，不预建内部层级。
- **保存和编排复用**：[comfyWorkflow](../../frontend/src/platform/workflow/management/stores/comfyWorkflow.ts)、[workflowService](../../frontend/src/platform/workflow/core/services/workflowService.ts)、[自动保存](../../frontend/src/platform/workflow/persistence/composables/useWorkflowAutoSave.ts)、[本地草稿](../../frontend/src/platform/workflow/persistence/composables/useWorkflowPersistenceV2.ts)、[ChangeTracker](../../frontend/src/scripts/changeTracker.ts)及[userdata](../../engine/ComfyUI/app/user_manager.py)。原生JSON是唯一当前图，项目关联联动和控制核对待补；重要方案另存，不建永久修订或服务端草稿。
- **执行复用**：[graphToPrompt](../../frontend/src/utils/executionUtil.ts)、[server](../../engine/ComfyUI/server.py)、[main](../../engine/ComfyUI/main.py)、[execution](../../engine/ComfyUI/execution.py)及[定向取消](../../engine/ComfyUI/comfy_execution/jobs.py)。⑤保存实际运行图／参数及任务关联，不建第二队列；原生history是内存，取消受理不代表外部软件停止。
- **自动预览与桥接**：[app事件](../../frontend/src/scripts/app.ts)、[节点输出Store](../../frontend/src/stores/nodeOutputStore.ts)及[原生产品桥接](../../frontend/src/platform/astrophotoflow)。实际执行图像节点生成独立轻量UI输出，多次保存和按任务归图待实现，不能将全部节点设终点、自动登记素材或让A结果写B。
- **MCP和检索**：[MCP装配](../../src/astrophotoflow/interfaces/mcp/server.py)经[HTTP客户端](../../src/astrophotoflow/client.py)调用数据能力，现有[library Skill](../../.agents/skills/astrophotoflow-library/SKILL.md)仍只描述可用功能。精简迁移、Skill直达／按需Top10及在线画布控制未实现；协议仍归interfaces。
- **首次验收**：保存重开／另存、多次自动预览、切图暂停与后台结果归属、手改接管／明确交回、运行实际参数及取消、节点更新、所选完整结果登记和真实客户端。原生[撤销](../../frontend/src/scripts/changeTracker.test.ts)、[自动保存](../../frontend/src/platform/workflow/persistence/composables/useWorkflowAutoSave.test.ts)、[转换](../../frontend/src/utils/executionUtil.test.ts)、[取消](../../engine/ComfyUI/tests-unit/jobs_cancel_test/jobs_cancel_test.py)、[stdio](../../tests/integration/test_cli_mcp_protocol.py)仅作基础；拟新增测试文件及断言已列入[详细设计](../api/platform-contracts.md#verification-design)，当前不存在，不作为可运行命令。

场景以[现行需求](../requirements/README.md#scenario-import)为准：②负责导入与固定范围，③真实软件，④定义，⑤连接可见编排、处理及Agent交互；新增能力仍待实现。

## 3. 共享入口与验证命令

| 位置 | 职责与消费规则 |
|---|---|
| [contracts](../../src/astrophotoflow/contracts) | 已有 Pydantic 模型与纯校验，只依赖标准库／Pydantic；未来协议随实现补齐，不创建空模型 |
| [interfaces/http](../../src/astrophotoflow/interfaces/http) | app.py 装配模块路由与生命周期，system.py 提供健康及真实能力，cli.py 提供 apf-service |
| [interfaces/client](../../src/astrophotoflow/interfaces/client)、[interfaces/cli](../../src/astrophotoflow/interfaces/cli) | 具名 HTTP 操作与 apf 命令处理，根 client.py／cli.py 保留公开入口 |
| [comfyui/proxy.py](../../src/astrophotoflow/comfyui/proxy.py) | 固定引擎同源网关、来源／路径校验、服务端令牌、流式请求和 request ID |
| [UI 包入口](../../frontend/packages/astrophotoflow-ui/src/index.ts) | 当前只导出 Workspace，内部模块通过自己的公开入口消费 |
| [Python 边界测试](../../tests/architecture/test_import_boundaries.py)、[前端依赖规则](../../frontend/.dependency-cruiser.json) | 当前检查 contracts／core、数据模块公开入口、客户端不得访问 ORM、UI 不反向依赖原生应用；尚不代表未来全部模块调用规则已自动覆盖 |

仓库根命令：

```powershell
uv run --locked --no-sync pytest tests/architecture -q
pnpm check:boundaries
pnpm test
pnpm typecheck
pnpm --dir frontend exec vitest run src/views/GraphView.test.ts src/stores/workspace/sidebarTabStore.test.ts src/utils/executionUtil.test.ts src/utils/executionUtil.stability.test.ts
```

前端命令使用锁定 Node／pnpm 与 frontend workspace 依赖；根 pnpm test／typecheck 只针对私有 UI 包，原生应用类型检查随生产构建执行。完整构建、发行和隔离浏览器入口见[开发流程](../development/README.md)，这些命令不是本轮文档任务的已执行记录。

## 4. 任务说明最小内容

每项任务写清 FR／AT、阶段、所属模块、需读取的实际契约、生产者与消费者、允许修改路径、依赖公开操作、交付物、正常与必要异常验收及证据位置。跨模块任务分别说明双方责任，不复制 ORM 事实或绕过权威版本。

未实现模块先确定真实接口与验收，再创建代码和测试；不因为目录存在而添加空类、假路由、假数据或不存在的命令。后续具体设计从[总架构场景责任](overview.md#8-场景责任与后续设计)继续，不独立重写模块边界。
