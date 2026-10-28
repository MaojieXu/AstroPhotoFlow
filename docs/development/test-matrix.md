# 需求、实现与验证矩阵

## 2026-10-27 第⑤阶段计划联合审查与任务卡

候选为dev `75aab88714095d77f2d576c14712a31c2b987bf6`上的本轮文档增量，非业务实现。[总计划](implementation-plan.md)保留M1～M6、22 Batch／建议分支、79项验收、G01～G10及V01～V18；六份任务卡把需求／数据／接口映射到准确文件、关键函数、实施顺序、测试输入／命令／预期及人工操作。

- 使用Context Researcher、Software Architect、Senior Developer、QA Engineer、Git／DevOps Reviewer并行审查，由Document Editor装配，Independent Verifier另行逐卡复验。审查报告、基线、静态检查和独立结论进入`.artifacts/implementation-plan-review`，最终状态以该候选报告为准。
- 用户确认五项取舍，见[ADR-0061](../../frontend/docs/adr/WORKBENCH-PLAN-0061-executable-batches-and-shared-client.md)。原④契约只补真实调用缺口及冲突，未另建协议体系；计划区分Batch技术集成与用户Milestone批准，不把尚未锁定的首包／模型或未过原型写成Ready。
- 本轮仅执行文档及静态源码检查，没有创建业务源文件／测试实现／实际分支、执行迁移或修改schema0009；未运行构建、原型、业务回归、软件／MCP客户端操作、工作台启停或环境维护，未提交推送。当前OpenAPI、锁文件、MCP／Skill及原有脏改动保持。
- 第④阶段下列散列与结论对应其当时历史候选；本轮补文后的新契约与任务卡由本轮报告独立记录，不能把旧散列冒充当前文档。所有业务验收及M1～M6用户批准仍待实际实施。
- 全仓前端ADR脚本实际返回1：历史ADR两处、既有工作流前端README两处短号引用不合现行命名规则，均与本轮开始时内容／散列相同，按范围保留；未当作检查通过。ADR目录命名与元数据单独执行通过；具体失败和范围证据见`.artifacts/implementation-plan-review/adr-check.json`，不以此扩改历史文档。

## 2026-10-27 第⑤阶段近期实施计划编制

候选为dev当前文档工作区。[近期计划](implementation-plan.md)对接现行接口与文件级详细设计，按M1～M6列出22个建议分支、分项验收及V01～V18责任；M2完成②自身近期范围，跨模块项分别由B53／B54／B55／B57联调，最终在M6验收。

- 本轮只检查计划结构、分支依赖、验收编号、接口断言覆盖、本地链接／锚点和Git增量；报告进入`.artifacts/implementation-plan`。检查结果以报告为准，不把计划中的测试名称视为已经执行。
- 所有建议分支、新增原型和功能验收均未实施；首软件准确版本／操作、实际素材和本地检索模型仍按计划门槛确认。保留第④阶段独立证据及下列历史状态，不将当时“近期计划尚未开展”解释为当前状态。
- 未创建实际分支，未修改代码、OpenAPI、依赖、环境、MCP／Skill或业务数据，未运行构建／业务回归、启停工作台、提交或推送。完整产品S6范围继续保留。

## 2026-10-27 第④阶段接口与文件级详细设计

候选为dev当前文档工作区，非新增功能实现。主文[接口与文件级详细设计](../api/platform-contracts.md)通过Context Researcher、Software Architect、Senior Developer、QA Engineer、Document Editor及Independent Verifier复核；报告与本轮增量在`.artifacts/fourth-stage-design`。独立候选主文SHA-256为`1c59ace39a76603e91e261f655444e2dc6b6a3f474c7f4dc7082354c29815738`，R1–R8/I1–I7已逐项关闭。

- 验证范围：五模块文件职责、公开签名及类型、调用/异常/副作用、数据一致性、原生复用、具体测试文件和FR/NFR/AT追踪；已有/拟新增/待原型/后续目标分开。
- 文档静态检查：Python签名块可解析、类型引用闭合、表格/JSON/本地链接锚点、当前78个HTTP/代理/OpenAPI集合及58数据工具迁移映射、既存ADR和本轮Git范围。具体数量与最终文件散列以报告checks.json为准。
- 本轮没有创建ORM/DDL/迁移/接口/类型/组件/测试实现，没有运行构建或业务回归，未操作正常工作台、软件安装、MCP/Skill/环境/业务数据，未提交或推送。原有未提交内容与历史证据保留，不校验不存在的旧需求冻结清单。
- 通过仅指第④阶段文档设计；首软件准确版本/操作、可靠UI来源、真实装载/目标转换/科学缓存/停止/预览及客户端行为仍需原型。第⑤阶段近期实施计划尚未开展。

自动化回归、真实运行和完整产品验收分别记录。子功能通过不表示对应 FR 或全部 AT 已完成；历史结果不替代当前候选验证。需求及验收条件以[现行产品基线](../requirements/README.md#9-验收场景)为准。

2026-10-27 的五模块概要和数据设计属于文档与静态源码检查；新增软件安装、画布桥接、运行和预览能力尚未因此实现或验收。个人偏好历史的恢复和删除仍需后续验证。

## 2026-10-27 现行文档清理检查

按用户要求删除过时需求包和旧设计正文，保留当前产品规则、验收场景及历史业务测试证据。过时的模块文档目录和决策记录已删除，业务规则统一维护在现行方案中。

检查范围包括相关文档的本地链接与锚点、FR／AT编号、过时模块和需求包引用、ADR格式及Git差异；结果记录在 `.artifacts/document-cleanup/report.json`。本轮没有运行构建、业务回归或服务操作，新增能力仍待实现和验收。

## 2026-10-27 接口契约静态检查

[五模块接口契约](../api/platform-contracts.md)覆盖①本机控制、②科学数据／所选结果、③软件包、④可编辑节点及⑤原生画布／运行／MCP交接；局部改图、保存成功后运行、网页按钮绑定目标已按用户选择同步需求。新增路径和工具名均为未来设计，尚未实现或运行验收。

本轮逐项核对领域路由、OpenAPI和同源代理的78个操作，以及58个MCP工具的迁移覆盖；检查任务增量链接、锚点、ADR格式、Git范围及保留文件散列。报告见[接口设计检查](../../.artifacts/interface-design/report.md)，详细清单见 `.artifacts/interface-design/checks.json` 和 `inventory.json`。未运行构建、业务回归、原型或服务，未修改OpenAPI、当前MCP或Skill。历史需求包在任务开始前已删除，本轮不恢复，也不声称通过不存在的冻结清单校验。

## 当前行为与验证入口

| 需求范围 | 已有行为及边界 | 验证入口 |
|---|---|---|
| FR-01 项目 | 资料、回收站、资产与集合固定引用；项目托管工作流未实现 | `tests/modules/data/test_service.py`；UI Workspace／Settings |
| FR-02 工作流目标 | ⑤复用唯一原生当前图、自动保存、本地草稿和会话撤销，项目关联／另存和在线桥接待实现；无永久逐编辑历史 | 按[⑤概要](../../src/astrophotoflow/modules/workflows/README.md#verification)、AT-06～11验证保存重开、另存、活动目标及断连，不以原生测试代替新增业务 |
| FR-09 运行目标 | ⑤记录当次图／输入／参数及原生任务关联，两类输入保证、真实调用／停止核对和所选结果保存待实现；复用ComfyUI队列 | 按[⑤阶段](../../src/astrophotoflow/modules/workflows/README.md#phases)、AT-14～18／28／29补真实软件及运行证据 |
| FR-03/13 软件包 | ③软件专用副本及配套节点、安装版本位置和可用状态仍待实现；Agent只连接平台MCP | 按[③概要](../../src/astrophotoflow/modules/software/README.md#phases)、AT-02／03／25／33验证安装、许可引导、节点发现及确认更新 |
| FR-04 导入 | 登记与托管分离、并发、Header 分类、预设快照、编辑与排序 | `tests/modules/data/test_import_pipeline.py`、`test_ingestion.py`、`test_library_sort.py`、`tests/integration/test_import_presets.py`；UI 导入／任务测试 |
| FR-04/11 删除 | 确认范围、部分清理、固定身份、共享路径与外部原件保护 | `tests/modules/data/test_service.py`、`test_calibration.py`；UI LibraryTrashDialog |
| FR-05 预览 | 100 px 缩略图、1080 px 大图、单图自动拉伸与 RGB 白平衡；完整比较未实现 | `tests/modules/data/test_auto_stretch.py`、`test_fits_preview.py`、`test_display_previews.py`、`test_video_preview.py`；UI PhotoPreviewDialog |
| 设备与预设 | 接受时冻结快照、删除后恢复／重试、历史名称和草稿保护 | `tests/modules/data/test_equipment_snapshots.py`、`test_setups.py`；UI SettingsOrganization／Workspace |
| 校准引用 | 默认、继承／null／覆盖、跨组隔离、历史清理保护；不执行校准 | `tests/modules/data/test_calibration.py`、`test_domain_foundation.py`；UI CalibrationLibrary |
| FR-07 数据 MCP | 58 工具与 CLI 共用服务；图编辑和软件运行工具未实现 | `tests/integration/test_client_operations.py`、`test_cli_mcp_protocol.py` |
| FR-07 统一检索目标 | ⑤派生目录、Skill直达、按需混合Top10及明确关键词降级待实现，当前58数据工具保持 | 按[⑤阶段](../../src/astrophotoflow/modules/workflows/README.md#phases)、AT-33／34验证精简MCP整体迁移、Skill及真实客户端，不遗漏已有数据业务 |
| FR-08 并发 | 数据revision已有；⑤活动目标核对、简单当前控制、手改接管／明确交回及在线结果返回尚未实现 | 按AT-07～10／24验证旧写拒绝、切图暂停、不抢视图、已有运行继续；A后台完成预览归A，不串B |
| FR-10/11 来源与恢复 | 数据固定版本及既有保护保留；⑤当次运行内容、多次自动图像预览、另存方案、所选完整结果和S6显式固定结果续跑待实现 | 按[⑤概要](../../src/astrophotoflow/modules/workflows/README.md#phases)、AT-06／09／18／20／21补证据；预览不代表完整文件仍在，核对／补登记不重跑 |
| FR-12 本地上下文 | 偏好、项目背景、工作流经验与交接摘要均待实施；个人偏好历史可查看／恢复为当前，删除包括历史正文；不包含完整聊天或模型会话 | 后续按 AT-22、AT-30、AT-31 验证，暂无完成证据 |
| FR-16 节点制作 | ④设计已收敛为workspace可编辑节点库、可选测试、最近测试查询及确认更新，均待实现；Python／复合S6，导出另行规划 | 按[④概要](../../src/astrophotoflow/modules/nodes/README.md#phases)、AT-03／29验证参数重置、变化端口、加载及执行中保护，暂无产品节点测试命令 |
| FR-13/15 交付 | 固定引擎、现有init/start/status/stop、完整网页、源码外安装和无Node重建；MCP启动、端口冲突自动选择及实际地址交接、网页公共配置、CLI／MCP重启、日志轮转与确认清理待补 | `tests/core`、`tests/packaging`、`scripts/verify_distribution.py`；新增验收见[公共概要](../../src/astrophotoflow/core/README.md#verification) |
| FR-14 服务边界 | 认证、代理来源／路径、原件和共享文件保护 | `tests/interfaces/comfyui/test_proxy.py`；数据服务／导入回归 |
| FR-15 契约 | OpenAPI、Pydantic、前端 Zod 与 MCP 结构 | OpenAPI 快照、UI 契约和真实 stdio 测试 |

前端 API JSON fixture 是模拟数据，不是整批真实照片的端到端验收。浏览器写入验收使用隔离服务和合成 PNG，覆盖原生侧栏、未保存保护、画布／视口、保存加载、真实 CPU 执行、上传、自动预览、回收站恢复及刷新。

## 保留的历史证据

| 日期与候选 | 当时验证结果 | 本机证据与范围 |
|---|---|---|
| 2026-10-25，原生侧栏 `c11745a` | UI 144、原生侧栏／画布 21、浏览器 5 组；类型及构建通过 | `.artifacts/redesign/sidebar-frontend.xml`、`sidebar-native-tests.log`、`sidebar-browser.log`；Windows／CPU、合成素材 |
| 2026-10-25，源码迁移阶段 `c11745a` 至 `16025dd` | Python 286 passed／1 skipped，另 1 项引擎构建回归通过；UI 144、原生 21、浏览器 5 组；OpenAPI 与 58 工具结构一致，发行验证通过 | `.artifacts/restructure/python-isolated.xml`、`engine-build-test.log`、`boundaries.log`、`browser-final.log`；218 个数据实现行为 AST 核对保持 |
| 2026-10-26，切换前 `16025dd` 加 URL 调整 | Python 287 passed／1 skipped，UI 144、侧栏 8；构建及发行通过 | `.artifacts/rename/*-before-move.log`、`python-before-move.xml`；仅证明切换前候选 |

旧阶段过程可从 Git 历史查询；本机日志与环境不随源码分发。历史独立复查和运行验收不表述为本轮新做的代码审查。

## 2026-10-26 改名收尾验收

日期：2026-10-26。基线 `16025dd`，候选包含文档清理和仓库 URL 调整。Windows／Python 3.12／CPU、Node 26.8.2、pnpm 11.13.1，依赖锁文件保持。

| 检查 | 本轮结果 | 证据 |
|---|---|---|
| dev 环境与路径 | 锁定重装、包定位、apf／apf-service 和固定工具版本通过；只更新 AstroPhotoFlow 的 MCP 注册内容，其他配置保持 | `.artifacts/docs-update/uv-sync.log`、`path-repair.json` |
| Python 全量 | 288 passed，无 skipped；FFmpeg 首帧用例实际执行通过。保留 1 条 SQLAlchemy 外键环警告 | `.artifacts/docs-update/python.xml` |
| 启动回执修复 | 实际启动仍打印旧 `#/library`；新增回归断言先复现，再将回执修正为 `#/workflows`。修复后工作台 5 项通过 | `start-url-before-fix.log`、`workbench.xml`，均位于 `.artifacts/docs-update` |
| 自研 UI | 19 个文件、144 passed | `.artifacts/docs-update/ui.log` |
| 原生侧栏与画布 | 5 个文件、25 passed；旧上游侧栏预期对齐已确认的节点库／素材库／工作流顺序，保留任务历史开关与菜单断言；定向格式和 ESLint 通过 | `.artifacts/docs-update/native.log`、`test-format.log`、`test-eslint.log` |
| 依赖边界 | Python 5 项通过；前端 0 errors、保留 9 条组件循环依赖警告 | `.artifacts/docs-update/boundaries.log` |
| 类型与生产构建 | 私有 UI 和原生应用类型检查、完整网页构建通过 | `.artifacts/docs-update/build.log` |
| 隔离浏览器 | 32588／32590、合成 PNG、5 组通过，含真实 CPU 执行、保存加载、上传与自动预览、回收站恢复 | `.artifacts/docs-update/browser.log`、`.artifacts/reports/native-web/results.json` |
| 网页／CLI／HTTP／MCP | 同库查询一致，真实注册命令启动 stdio 后发现 58 工具；1149 个网页文件与构建一致且不含领域令牌 | `.artifacts/docs-update/dev-before-restart.json`、`dev-after-restart.json` |
| 停止与重启 | 两套实例端口释放、重启后身份保持；dev 最终 running、隔离实例 stopped，默认 workspace 不变 | `.artifacts/docs-update/lifecycle.json` |
| 数据保持 | 118 个非数据库文件的大小／mtime／SHA-256 保持；SQLite 主文件字节变化，但 17 张表的行级摘要与改名前一致，外键有效；无新增数据库备份 | `.artifacts/docs-update/data-preservation.json` |
| 文档与链接 | 当时的文档整理、本地链接、锚点与删除引用检查通过 | `.artifacts/docs-update/docs-check.json` |
| 发行与安装 | wheel 源码目录外安装、无 Node 的 sdist 重建及再安装通过；完整网页、迁移、入口和源码包范围检查通过 | `.artifacts/docs-update/distribution.log`、`.artifacts/reports/packaging.json` |

上述全量 Python 在启动回执修复前运行；该修复之后运行了对应工作台回归与真实启动／重启。

受限进程首次运行 UI 时出现跨进程临时目录 ENOENT；正常用户环境重跑后全部通过，未为该环境故障修改产品逻辑。早期失败和最终日志均保留在本轮目录。

浏览器脚本在隔离用户配置中显式设置 `Comfy.TutorialCompleted`，沿用上游首次引导；这 5 组检查不代表首次引导已重新设计或单独验收。运行核对使用 HTTP／CLI／MCP；数据库容器变化的诊断沿用维护脚本的只读 SQLite 快照比对，不构成新的业务访问路径。

## 仍需后续验收

- FR-02、FR-03、FR-07～FR-12、FR-16及其他有效FR的未完成部分，按[现行需求](../requirements/README.md)与[当前路线](platform-roadmap.md)推进；使用现行AT及覆盖解释，旧需求包已删除，不对不存在的冻结清单宣称散列校验通过。
- S0 固定性能基准机器、数据规模与测量指标，相关功能可测后补齐数值门槛。标准节点热发布须有单独原型证据，不由现有定义刷新入口推定支持。
- ①的默认／自选目录、待应用配置及旧连接保持、并发控制／繁忙拒绝／重启核对、原生领域状态桥接、日志轮转／确认清理和完整升级恢复，按公共概要及其阶段表补实际证据；不能以本次文档覆盖代替功能通过。
- ②的固定科学输入、用户选择结果保存、比较、标签／文件治理及本地记忆，按数据概要DATA-F01～F08和阶段出口补实际证据；完整中间文件不作为长期保存内容，现有58个数据工具和数据回收站测试不代替新增闭环验收。
- ③软件包安装、配套节点发现、未就绪提示、确认更新、科学交接及卸载按现行③概要验收；⑤联合全部业务工具的混合检索、最多10候选、定义按需读和模型故障显式降级须有AT-34及真实MCP证据。具体模型与桥接均待原型，不把外部项目源码当作本平台支持。
- ④按NODE-F01～F08补workspace节点保存及跨项目使用、可选真实测试及最近结果、修改后旧测试提示、影响确认、参数默认值、端口增删改及重排、加载失败和执行中保护的证据。S6 Python及复合局部副本分别验证；不恢复项目草稿、测试门禁或旧版并存要求，导出安装仍后续规划。
- ⑤编排与在线交互按⑤概要验收：项目关联及唯一原生当前图、自动保存／另存／重开、本地草稿和会话撤销、缺依赖JSON、目标与控制检查；手动接管／明确交回、切图暂停、断连核对和真实MCP。取消永久逐编辑修订、服务端草稿、独立转换及永久画布回执要求，原生基础不代替新增桥接证据。
- ⑤执行与结果按⑤概要验收：可选真实测试及整图／受支持目标、两类输入保证、实际提交核对、运行内容／缓存、取消与实际停止、完整重跑及S6已保存固定结果续跑。各实际执行图像节点自动预览，保留多次并按任务归原图；只有用户选择完整结果才交②保存，未请求保存不构成登记失败。
- ⑤业务场景继续覆盖整夜／叠加起点、Skill直达／按需分型检索、精简MCP整体迁移、外部Agent调参及更换客户端接续；原生按钮、快捷键、自动队列和MCP托管运行统一提交且保留实际事实。未来Judge仅概念边界，数据工具、元数据字段和Skill不作完整场景通过证据。
- Linux 尚无本轮运行证据。视频用例在 FFmpeg 不可用的平台仍需单列为 skipped，不能计作通过。
- 用户最终业务体验验收与自动化回归分开。设置、设备快照和校准引用等有效场景见功能文档；旧页面、旧照片数量和退役入口不再作为条件。
