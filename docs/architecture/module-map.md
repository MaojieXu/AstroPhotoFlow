# 五模块源码与验证导航

2026-10-29 M3 候选映射：software/public.py 新增程序卸载、真实调用、只读观察、定向取消及当前占用；contracts/software.py 承载实际 DTO，routes.py／client/software.py／固定代理新增待确认卸载。interfaces/siril_node.py 从 JSON 定义生成首个 V3 Siril 节点；workflows/software_calls.py 复用原生执行身份，协调 data.public.resolve_canvas_inputs、科学输出检查及软件调用。UI SoftwarePanel 精简为状态与安装／卸载，宿主注入原生控件。测试新增 software/test_invocation.py、workflows/test_software_calls.py、interfaces/comfyui/test_software_page.py、integration/test_siril_native.py；全部未运行。


统一媒体查看候选：contracts/media.py维护MediaSelection／MediaState；data/media_view.py负责准备、状态、瓦片与媒体HTTP及Preview所有权；media_sources.py提供格式解码和图像平面／区域；media_cache.py提供有限内存／磁盘缓存和清理位置；media_video.py使用既有FFmpeg生成播放代理及实际PTS映射。原生桥接MediaViewer.vue／mediaViewport.ts消费UI包api/media.ts公开类型，Workspace及FixedDatasetMembers通过LibraryControls注入，不反向导入原生源码。回归文件为test_media_sources／cache／view／video、test_media_stream、MediaViewer.test、mediaViewport.test及CanvasDataWidget.test；仅编写，未运行。

Object／分类预览候选：data/preview_recipes.py集中preview_context、backfill_context、describe_recipe及save_group_recipe，同批同来源目录的兼容subframe按Object复用首张有效帧MTF，masterframe独立；ingestion.py负责首帧选择、逐张渲染和重试。auto_stretch.py的statistics_indices／sample_statistics从原图分层随机取样，fits_preview.py的read_stretch_pixels按行读取并保留RGB／Bayer色彩单元；previews.py复用保存的MTF并只在缺少配方时测量。测试归test_import_pipeline、test_fits_preview、test_auto_stretch及test_display_previews，全部仅编写／修改，未运行。

本机直接来源候选：data/local_selection.py复用Windows系统文件／文件夹选择；data/files.py的enumerate_local枚举当前层支持文件并固定来源观察；contracts/imports.py扩展可省略root_id的绝对路径与选择响应。data/imports.py的select_local_import只返回选择，create_import受理托管；ingestion空root_id分支使用保存的绝对路径。原UI LocalImportPicker及ImportDialog消费新入口；旧根目录API与CLI／MCP路径保持，测试未执行。

Nodes 2.0展示映射：contracts/inputs.py的CanvasInspectRequest／Out与data/canvas.py的inspect_canvas_data／HTTP入口提供只读固定成员资料；UI包api/canvas.ts公开消费模型／客户端。原生dataReferenceDisplay.ts负责扩展注册及非序列化展示控件，CanvasDataWidget.vue负责当前成员加载、预览及参数详情；原生WidgetDOM.vue挂载ComponentWidget，ImagePreview.vue提供可选displayOnly。测试归已有test_canvas_data.py及对应原生Widget／组件测试；全部未执行。

2026-10-28 素材入画布候选映射：②modules/data/canvas.py公开prepare_canvas_data及HTTP准备入口；⑤modules/workflows/canvas.py公开list_canvas_pages／add_canvas_data／get_canvas_request路由，应用装配经data.public准备；interfaces/canvas_native.py维护原生连接中的页面观察及会话回执，interfaces/data_reference_node.py提供固定APF_DATA_REFERENCE；client/canvas.py、CLI canvas分组及MCP tools/canvas.py均经HTTP。前端data/api/canvas.ts公开DTO／客户端，Workspace发事件及注入拖放组件，原生canvasDataBridge／useCanvasDataSession负责实际图操作。新增测试归data、workflows、interfaces/comfyui及相应宿主／UI组件；未执行行为验收。此条覆盖表内“节点交接未实现／⑤仅文档”的对应窄范围，其他能力不变。

本页负责定位源码、公开入口、消费契约和验证位置。职责、权威归属与调用方向以[总架构](overview.md)为准；开发依赖以[路线](../development/platform-roadmap.md)为准；目录及产物规则见[文件架构](repository-layout.md)。接任务时先确定模块，再读局部 README／AGENTS 和实际契约。

状态核对日期：2026-10-28，工作台入口已按demo候选迁入原生设置（用户验收待完成），基线为 `demo`／`741f6f1d` 加当前未提交文件。下列“已有”依据源码检查，历史通过范围见[验证矩阵](../development/test-matrix.md)，不代表本轮重跑。文件存在、公开操作存在与真实链路验收分别表达；文件／公开函数映射见第3节。

[数据结构初稿总入口](data-models/README.md)集中提供①至⑤对象、关键字段、关系和待确认事项；它是设计导航，不是新增源码、ORM或测试入口，各模块概要开头均有对应链接。

## 1. 源码归属

Python 根为 `src/astrophotoflow`，自研 UI 根为 `frontend/packages/astrophotoflow-ui/src`；表内链接指向完整位置。模块不是独立进程或页面。

| 模块 | Python | 自研 UI | 原生／引擎接入与当前状态 |
|---|---|---|---|
| ① 公共基础设施 | [core](../../src/astrophotoflow/core) | [core](../../frontend/packages/astrophotoflow-ui/src/core) | M1配置／启停／维护及网页表单已集成dev并获用户批准，共用原生Vue；证据见矩阵 |
| ② 数据与资产管理 | [modules/data](../../src/astrophotoflow/modules/data) | [modules/data](../../frontend/packages/astrophotoflow-ui/src/modules/data) | 数据与界面已有，原生素材侧栏挂载 Workspace；节点交接和记忆未实现 |
| ③ 外部软件接入与环境 | [modules/software](../../src/astrophotoflow/modules/software) | [modules/software](../../frontend/packages/astrophotoflow-ui/src/modules/software) | B31已实现Siril 1.4.4包查询与命令资料；B32已实现安装计划／准备接口及SoftwarePanel候选；真实确认、下载安装和MCP仍待验证 |
| ④ 节点构建与发布 | [modules/nodes](../../src/astrophotoflow/modules/nodes) | [modules/nodes](../../frontend/packages/astrophotoflow-ui/src/modules/nodes) | B41已实现workspace JSON定义及六个public操作；原生注册、HTTP、确认更新、编辑器及连线应用仍待实现／验证 |
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
- **入口与调用**：data/routes.py 装配已有 HTTP 路由；public.py 导出导入／预览、繁忙状态、项目读取、科学输入、内容观察／接纳、输出检查／预览／登记／查询及移除范围。实现文件和公开函数见第3节；其他模块不能直接访问 models.py 或 SQLite。
- **前端与桥接**：UI 的 modules/data/index.ts 导出 Workspace，经包 src/index.ts 被原生 LibrarySidebarTab.vue 消费；既有表单、素材、设备与预览行为保留。M2已提供科学输入解析和所选完整结果登记的Python能力；画布选材、运行来源及网页结果选择等待⑤消费，比较和本地记忆仍未实现。
- **消费契约**：contracts 中 assets、imports、datasets、projects、equipment、setups、calibration、trash、previews 及 common；UI 消费模型在 modules/data/api/contracts.ts。新增部分遵守[数据引用边界](overview.md#boundary-data)。
- **验证位置**：[tests/modules/data](../../tests/modules/data)、[导入配置集成](../../tests/integration/test_import_presets.py)、[UI 数据测试](../../frontend/packages/astrophotoflow-ui/tests/modules/data)和 tests/fixtures；原件、固定版本、快照、revision、null／0、校准及清理保护分别验收。
- **命令**：`uv run --locked --no-sync pytest tests/modules/data tests/integration/test_import_presets.py -q`、根 `pnpm test`。未来工作流及运行引用保护需另补联调，不能由现有数据回收站测试宣称已覆盖。

<a id="module-3"></a>

### ③ 外部软件接入与环境

- **概要设计**：[唯一软件概要](../../src/astrophotoflow/modules/software/README.md)维护软件包、配套节点、状态及交接验收；[前端分工](../../frontend/packages/astrophotoflow-ui/src/modules/software/README.md)只补充界面及宿主责任。B31已建立Siril 1.4.4只读包查询和版本命令资料；安装、节点加载、确认更新和真实工作流调用仍待补。
- **入口与调用**：`contracts/software.py`、`modules/software/public.py`、`routes.py`及AssetClient提供固定包查询、完整命令资料读取、Auto Stretch操作及配套JSON读取。HTTP公开包列表、详情、安装计划和准备；SoftwarePanel候选通过宿主同WS提交真实按钮事件。浏览器／ComfyUI真实确认和MCP未验证；消费core／contracts，不接管资产登记、节点发布、统一排名或运行权威。
- **消费契约**：[数据引用](overview.md#boundary-data)、[节点绑定](overview.md#boundary-nodes)、[运行回执](overview.md#boundary-runs)及[统一检索目标](../requirements/README.md#tool-discovery)。首软件固定为Siril 1.4.4 CLI；package list区分平台未安装与用户手动下载，命令Scriptable标记不代表定义生成／加载／真实运行。
- **首次验收**：S2真实平台安装、许可准备和节点发现及网页／Agent同目录；⑤同步最多10候选和模型失败显式关键词降级；与④验证绑定／使用，与⑤按实际适配验证软件调用、取消及结果。ASTAP、PixInsight等仍是后续候选，PixInsight桥接仍需原型，AT-33／AT-34无完成证据。
- **验证位置与命令**：[B31测试](../../tests/modules/software/test_service.py)验证固定命令目录、只读状态、版本绑定操作／定义、路由依赖和代理白名单；真实安装、节点加载、网页及MCP链路仍需实测。

<a id="module-4"></a>

### ④ 节点构建与发布

- **概要设计**：[唯一节点概要](../../src/astrophotoflow/modules/nodes/README.md)和[数据设计](data-models/04-nodes.md)维护workspace统一节点库、可选测试和确认更新；[前端分工](../../frontend/packages/astrophotoflow-ui/src/modules/nodes/README.md)补界面及宿主责任。B41定义文件操作已有，B42／B43原生加载及编辑器仍待实现。
- **入口与调用**：Python已实现④JSON定义契约及`public.py`六项文件操作；UI、路由和节点客户端仍未实现。调用③公开操作，供⑤消费定义；试运行由应用装配与⑤协调，不让④反向导入⑤，用户选择的完整结果由②检查保存，当前控制和实际画布应用核对归⑤。
- **原生接入**：[nodes.py](../../engine/ComfyUI/nodes.py)、[server.py](../../engine/ComfyUI/server.py)、[app.ts](../../frontend/src/scripts/app.ts)和[litegraphService.ts](../../frontend/src/services/litegraphService.ts)可复用注册。实际加载和保存分别核对；原生输出按位置保存，自定义同方向唯一命名及重排连线保持仍需桥接。
- **子图及转换**：[subgraphStore.ts](../../frontend/src/stores/subgraphStore.ts)、[subgraphService.ts](../../frontend/src/services/subgraphService.ts)、[executionUtil.ts](../../frontend/src/utils/executionUtil.ts)可复用。S6复合内部图及外露映射，工作流局部修改不回写节点库或其他图；导出安装另行规划。
- **消费契约及首次验收**：[节点边界](overview.md#boundary-nodes)、[原型门槛](overview.md#prototype-gates)及[NODE-F01～F08](../../src/astrophotoflow/modules/nodes/README.md#phases)；跨项目使用、可选测试、最近结果及旧内容提示、更新确认、参数重置、端口增删改及重排、实际加载与执行中保护。
- **验证位置与命令**：[平台定义测试](../../tests/modules/nodes/test_service.py)，命令 `uv run --locked --no-sync pytest tests/modules/nodes -q`；覆盖B41文件操作、绑定及端口差异。[迟到注册](../../frontend/src/services/litegraphService.lateRegistration.test.ts)、[蓝图](../../frontend/src/stores/subgraphStore.test.ts)、[子图序列化](../../frontend/src/lib/litegraph/src/subgraph/SubgraphSerialization.test.ts)、[转换](../../frontend/src/utils/executionUtil.test.ts)仅为原生基础，不代替平台节点加载及真实执行验收。

<a id="module-5"></a>

### ⑤ 工作流、执行与Agent交互

- **唯一设计及归属**：[统一概要](../../src/astrophotoflow/modules/workflows/README.md)、[必要数据](data-models/05-workflows.md)及[前端分工](../../frontend/packages/astrophotoflow-ui/src/modules/workflows/README.md)。工作流、运行与Agent交互业务统一进入workflows，不预建内部层级。
- **保存和编排复用**：[comfyWorkflow](../../frontend/src/platform/workflow/management/stores/comfyWorkflow.ts)、[workflowService](../../frontend/src/platform/workflow/core/services/workflowService.ts)、[自动保存](../../frontend/src/platform/workflow/persistence/composables/useWorkflowAutoSave.ts)、[本地草稿](../../frontend/src/platform/workflow/persistence/composables/useWorkflowPersistenceV2.ts)、[ChangeTracker](../../frontend/src/scripts/changeTracker.ts)及[userdata](../../engine/ComfyUI/app/user_manager.py)。原生JSON是唯一当前图，项目关联联动和控制核对待补；重要方案另存，不建永久修订或服务端草稿。
- **执行复用**：[graphToPrompt](../../frontend/src/utils/executionUtil.ts)、[server](../../engine/ComfyUI/server.py)、[main](../../engine/ComfyUI/main.py)、[execution](../../engine/ComfyUI/execution.py)及[定向取消](../../engine/ComfyUI/comfy_execution/jobs.py)。⑤保存实际运行图／参数及任务关联，不建第二队列；原生history是内存，取消受理不代表外部软件停止。
- **自动预览与桥接**：[app事件](../../frontend/src/scripts/app.ts)、[节点输出Store](../../frontend/src/stores/nodeOutputStore.ts)及[原生产品桥接](../../frontend/src/platform/astrophotoflow)。实际执行图像节点生成独立轻量UI输出，多次保存和按任务归图待实现，不能将全部节点设终点、自动登记素材或让A结果写B。
- **MCP和检索**：[MCP装配](../../src/astrophotoflow/interfaces/mcp/server.py)经[HTTP客户端](../../src/astrophotoflow/client.py)调用数据能力，现有[library Skill](../../.agents/skills/astrophotoflow-library/SKILL.md)仍只描述可用功能。精简迁移、Skill直达／按需Top10及在线画布控制未实现；协议仍归interfaces。
- **首次验收**：保存重开／另存、多次自动预览、切图暂停与后台结果归属、手改接管／明确交回、运行实际参数及取消、节点更新、所选完整结果登记和真实客户端。原生[撤销](../../frontend/src/scripts/changeTracker.test.ts)、[自动保存](../../frontend/src/platform/workflow/persistence/composables/useWorkflowAutoSave.test.ts)、[转换](../../frontend/src/utils/executionUtil.test.ts)、[取消](../../engine/ComfyUI/tests-unit/jobs_cancel_test/jobs_cancel_test.py)、[stdio](../../tests/integration/test_cli_mcp_protocol.py)仅作基础；[详细设计](../api/platform-contracts.md#verification-design)逐项区分已有测试和拟新增文件／断言，不能将规划路径作为可运行命令。

场景以[现行需求](../requirements/README.md#scenario-import)为准：②负责导入与固定范围，③真实软件，④定义，⑤连接可见编排、处理及Agent交互；新增能力仍待实现。

## 3. 共享入口与验证命令

| 位置 | 职责与消费规则 |
|---|---|
| [contracts](../../src/astrophotoflow/contracts) | 已有 Pydantic 模型与纯校验，只依赖标准库／Pydantic；未来协议随实现补齐，不创建空模型 |
| [interfaces/http](../../src/astrophotoflow/interfaces/http) | app.py 装配模块路由与生命周期，system.py 提供健康及真实能力，cli.py 提供 apf-service |
| [interfaces/client](../../src/astrophotoflow/interfaces/client)、[interfaces/cli](../../src/astrophotoflow/interfaces/cli) | 具名 HTTP 操作与 apf 命令处理，根 client.py／cli.py 保留公开入口 |
| [comfyui/proxy.py](../../src/astrophotoflow/comfyui/proxy.py) | 固定引擎同源网关、来源／路径校验、服务端令牌、流式请求和 request ID |
| [UI 包入口](../../frontend/packages/astrophotoflow-ui/src/index.ts) | 导出 Workspace、WorkbenchSettings／createWorkbenchClient、SoftwarePanel／createSoftwareClient／pendingSoftwareActionSchema及相关类型；内部模块通过自己的公开入口消费 |
| [Python 边界测试](../../tests/architecture/test_import_boundaries.py)、[前端依赖规则](../../frontend/.dependency-cruiser.json) | 当前检查 contracts／core、数据模块公开入口、客户端不得访问 ORM、nodes不依赖workflows或接入层、UI不反向依赖原生应用；尚不代表未来全部模块调用规则已自动覆盖 |

### 3.1 当前文件与公开函数映射

下表按实际文件定位公开入口，不复制DTO字段或完整签名；已有类型以源码和[现有接口](../api/README.md)为准，后续增量继续见[详细设计](../api/platform-contracts.md#file-design)。②既有业务路由按模块目录导航，本表补齐近期跨模块交接及①③④的具名入口。`create_app`内的组合函数是应用装配接缝，不是模块公开API。

| 归属／实际文件 | 公开函数或导出 | 当前消费者与限制 |
|---|---|---|
| ① [core/config.py](../../src/astrophotoflow/core/config.py) | `resolve_config_path`、`load_settings`、`load_running_settings`、`get_configuration`、`save_configuration` | CLI、HTTP配置与原生薄适配读取配置／采用值；不是配置历史 |
| ① [core/workbench.py](../../src/astrophotoflow/core/workbench.py) | `initialize`、`install_frontend`、`start`、`status`、`stop`、`restart`、`request_restart`、`restart_result` | 本机CLI和网页重启；MCP生命周期入口尚未注册 |
| ① [core/client.ts](../../frontend/packages/astrophotoflow-ui/src/core/client.ts)、[contracts.ts](../../frontend/packages/astrophotoflow-ui/src/core/contracts.ts) | `createApiClient`、`ApiClientError`、`FetchApi`、`createWorkbenchClient`；客户端 `getConfiguration/saveConfiguration/restart/restartResult` | data／software复用HTTP代码；配置表单消费①DTO |
| ① [WorkbenchSettings.vue](../../frontend/packages/astrophotoflow-ui/src/core/WorkbenchSettings.vue)、[WorkbenchSettingsPanel.vue](../../frontend/src/platform/astrophotoflow/WorkbenchSettingsPanel.vue) | UI包导出 `WorkbenchSettings`，宿主传入原生表单组件，挂载到设置窗口的“工作台”页面 | M1已集成dev并获用户批准，历史证据见矩阵 |
| ② [import_progress.py](../../src/astrophotoflow/modules/data/import_progress.py)、[preview_executor.py](../../src/astrophotoflow/modules/data/preview_executor.py) | `ImportProgress.copied/update/flush`、`PreviewExecutor.submit/submit_background/prioritize/shutdown`，均为②私有实现 | ingestion维护原件／预览进度与有界复制调度，common／previews提升主动查看优先级；不新增跨模块公开协议，测试只编写未运行 |
| ② [data/public.py](../../src/astrophotoflow/modules/data/public.py) | `data_busy`、`get_project`、`import_workers`、`mark_interrupted_tasks`、`backfill_missing_previews`、`DisplayPreviews`及下列科学交接重导出 | HTTP生命周期／维护消费；跨模块从public导入 |
| ② [science_inputs.py](../../src/astrophotoflow/modules/data/science_inputs.py) → public | `validate_input_references`、`resolve_inputs`、`observe_reference_inputs` | M2固定引用检查、科学文件准备及引用结束观察；⑤运行尚未接入 |
| ② 同文件 → public；[content.py](../../src/astrophotoflow/modules/data/content.py) | `observe_asset_content`、`accept_asset_content`；HTTP处理 `observe_content/accept_content` | 已有内容观察／接纳HTTP；旧固定引用不自动更新 |
| ② 同文件 → public | `check_output`、`render_output_preview`、`register_output`、`get_output_registration` | 所选输出检查／预览／登记／续查已有；网页选择和⑤运行来源待联调 |
| ② [trash.py](../../src/astrophotoflow/modules/data/trash.py) → public | `preview_library_removal` | 内部只读移除范围；工作流影响及公开移除协议仍待后续 |
| ② [contracts/inputs.py](../../src/astrophotoflow/contracts/inputs.py)、[assets.py](../../src/astrophotoflow/contracts/assets.py) | `ResolveInputsRequest/ResolvedInputs`、`InputReference`、`CheckedOutput`；`AssetContentObservation/AssetContentAccept/OutputRegistration` | Python科学交接及内容HTTP模型；类型存在不表示运行链已接通 |
| ③ [software/public.py](../../src/astrophotoflow/modules/software/public.py) | `list_packages/get_package`、`list_siril_commands/get_command_catalog`、`get_operation/get_bundled_definitions`、`get_package_source` | 路由及应用装配读取Siril固定包、命令、操作和定义；非任意命令执行器 |
| ③ 同文件 | `maintain_package`、`install_package`、`prepare_package`、`set_package_node_definition_ids` | 应用确认流程消费；真实页面确认及下载安装仍未验收，B33执行适配尚未实现 |
| ③ [software/routes.py](../../src/astrophotoflow/modules/software/routes.py) | `get_software_packages/get_software_commands/get_software_package`、`request_software_install/prepare_software_package` | 五个公开HTTP操作；安装POST返回202待确认计划 |
| 接入 [interfaces/client/software.py](../../src/astrophotoflow/interfaces/client/software.py) → [AssetClient](../../src/astrophotoflow/client.py) | `SoftwareOperations.list_software_packages/list_software_commands/get_software_package/install_software/prepare_software` | 具名HTTP客户端已有；软件MCP入口仍待B57 |
| ③ [SoftwarePanel.vue](../../frontend/packages/astrophotoflow-ui/src/modules/software/SoftwarePanel.vue)、[api/client.ts](../../frontend/packages/astrophotoflow-ui/src/modules/software/api/client.ts)、[api/contracts.ts](../../frontend/packages/astrophotoflow-ui/src/modules/software/api/contracts.ts) | `SoftwarePanel`、`createSoftwareClient`；客户端 `listPackages/listCommands/getPackage/requestInstall/prepare` | 命令目录、计划／状态及确认回调候选；UI不反向调用原生单例 |
| ④ [contracts/nodes.py](../../src/astrophotoflow/contracts/nodes.py)、[nodes/public.py](../../src/astrophotoflow/modules/nodes/public.py) | `NodeDefinition/SavedDefinition/DefinitionChange`；`list_definitions/get_definition/create_definition/preview_definition_update/update_definition/replace_package_definitions` | B41定义JSON、绑定检查、更新差异及包定义替换已有；HTTP、registry加载、画布更新和编辑器未实现 |
| 组合DTO [contracts/software.py](../../src/astrophotoflow/contracts/software.py)、[workflows.py](../../src/astrophotoflow/contracts/workflows.py) | `SoftwareInstallRequest/ConfirmSoftwareEvent`；`PendingSoftwareAction/SoftwarePackageDetails/NativePageEvent/NativePageReply`等 | B32计划、结果及页面消息类型已有；不代表⑤业务模型／运行服务已有 |
| 装配 [interfaces/http/app.py](../../src/astrophotoflow/interfaces/http/app.py) | `create_app`；内含 `request_software_action/get_software_package_details/confirm_software_action/execute_software_action/receive_native_page` | 组合③安装、④定义和当前页面确认；内部事件不进入公共OpenAPI；无⑤运行持久记录 |
| 原生适配 [interfaces/comfyui.py](../../src/astrophotoflow/interfaces/comfyui.py)、[server.py](../../engine/ComfyUI/server.py) | `register_native/handle_socket/forward_page_event/socket_closed` | B32同socket页面身份及 `apf.page` 中继已有候选；图写入／入队guard和节点注册未实现 |
| 宿主 [workflowBridge.ts](../../frontend/src/platform/astrophotoflow/workflowBridge.ts)、[SoftwareSidebarTab.vue](../../frontend/src/platform/astrophotoflow/SoftwareSidebarTab.vue)、[useSoftwareSidebarTab.ts](../../frontend/src/platform/astrophotoflow/useSoftwareSidebarTab.ts) | `confirmSoftware`、`useSoftwareSidebarTab`；[api.ts](../../frontend/src/scripts/api.ts) 的 `sendNativePage` | 仅B32软件计划确认回调和侧栏；文件名不表示⑤局部改图、画布控制或运行能力已实现 |
| ⑤ [modules/workflows](../../src/astrophotoflow/modules/workflows)、[UI workflows](../../frontend/packages/astrophotoflow-ui/src/modules/workflows) | 当前仅README／AGENTS，无模块业务函数导出 | 项目图、运行／预览记录、控制、检索及精简MCP仍待B51～B57 |

定向验证位置：② [test_science_inputs.py](../../tests/modules/data/test_science_inputs.py)，③ [test_service.py](../../tests/modules/software/test_service.py)及[软件UI测试](../../frontend/packages/astrophotoflow-ui/tests/modules/software)，④ [test_service.py](../../tests/modules/nodes/test_service.py)，页面传输 [api.nativePage.test.ts](../../frontend/src/scripts/api.nativePage.test.ts)。这些文件已存在；真实安装、加载、运行与用户验收仍以[矩阵](../development/test-matrix.md)分别记录。

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
