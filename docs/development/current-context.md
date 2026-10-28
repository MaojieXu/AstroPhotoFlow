# 当前开发上下文

更新时间：2026-10-28。集成分支为 **dev**，当前M1候选分支为 **codex/workbench-settings-ui**，继承B11 `6b10657`和B12中间提交`c23e10d`；M1已获用户人工验收通过及合入dev、删除当前功能分支授权。设计基线`9d4c729`已同步远端。原生网页及平台源码基线为 `16025dd89f2c3c2b25bae58bcc241e5202863c87`，已从原 dev `b6759ab` 快进合入；main 不属于本轮交付范围。

仓库为 [MaojieXu/AstroPhotoFlow](https://github.com/MaojieXu/AstroPhotoFlow)，本地目录为 `C:/Users/Administrator/Desktop/WorkSpace/AstroPhotoFlow`。本文维护当前实现、运行基线和有效待办；产品范围见[现行需求](../requirements/README.md)，历史测试证据见[验证矩阵](test-matrix.md)。

## 当前设计状态

验收反馈已修复UUID字符串请求、重启受理回执及未保存配置误用；实际网页已验证导入3／预览6保存并重启生效，地址可点击，原生风格输入及移除按钮对齐。证据为`.artifacts/implementation/M1/restart-browser.json`、`restart-python-final.xml`（115通过）、`restart-build-final2.log`和`restart-build-final3.log`。用户要求修复后停止追加测试，已遵从；网页重启第三轮独立审查因此中止，不宣称该轮完成。跨端口自动重连仍按界面提示及CLI核对。

M1界面按用户验收反馈调整为左侧“工作台配置”，位于工作流之后；复用原生侧栏和主题，取消顶部按钮及弹窗。侧栏注册5项、配置表单4项测试、类型检查和生产构建通过，真实浏览器5类检查通过；本次界面调整已由用户验证通过，随M1整体集成。证据见`.artifacts/implementation/M1/sidebar-update.md`。

**M1用户验收通过，交付合入dev**：用户确认修订后，启动失败已统一复用stop排空；待登记进程提前留痕，身份暂不可读时保留核对依据，控制结果写入失败不遮盖启动及清理错误。新迭代第三轮独立审查无剩余阻断。全量Python为336 passed、2项显式真实测试另行通过；浏览器五类检查通过。真实在途导入在模拟引擎启动失败后完整完成并正常退出。最新报告为`.artifacts/implementation/M1/delivery-report.md`及`iteration2-round3-review.md`；旧轮次失败证据保留。原dev已恢复31388／31390，隔离候选实际网页为32592；用户已于2026-10-28在当前聊天确认“通过测试，可以将结果merge到dev，并删除目前这个branch”；B11～B13及本轮修复整体交付dev。

五模块概要、数据设计及[接口契约与文件级详细设计](../api/platform-contracts.md)已成文，第④阶段已通过多Agent独立复核。[第⑤阶段近期实施计划](implementation-plan.md)按六个里程碑细化22个Batch：M1三卡已集成dev并获用户批准；M2的B21～B24在`feature/database_management`形成实现候选，尚未集成或批准；其余15卡尚未开工。五模块分别由①公共基础、②素材和项目资料、③外部软件、④节点定义、⑤工作流／运行／Agent交互负责。原78个HTTP操作加M1八项后为82项，M2再增加内容观察／确认两项，当前OpenAPI和同源代理共84项；58个数据MCP工具及注册保持。第④阶段独立证据保留于`.artifacts/fourth-stage-design`，计划检查进入`.artifacts/implementation-plan`。

第⑤阶段计划联合审查补充六份按M分组的22张任务卡，细化文件N／M／R、关键签名、调用顺序、测试和人工验收；原契约补齐必要的编辑期只读数据校验、Python具名客户端和固定业务ID。用户确认22 Batch内部小步、M3／M4交叉同轮分别批准、共用HTTP归core、维护窗口恢复原dev、普通移除与MCP在B57一次切换；历史证据进入`.artifacts/implementation-plan-review`。后续卡Ready仍须实际前置，首包和模型继续在各自任务前选择。

B11实现：新增ConfigValues／ConfigSave／ConfigState及get_configuration／save_configuration／load_running_settings；用户TOML的workspace.default取代旧active-workspace读取，Settings.workspace显式且必填。保存采用文件锁、配置token与完整文件替换，只保存最新值；运行采用值独立读取，无默认时清楚失败。初始化激活写默认TOML。B12已实现结构化启停／重启、自动端口及安全回写、实际采用值和导入／预览／原生准入屏障，B13已提供原生页面配置表单。全部实现与真实验证见[矩阵](test-matrix.md#m1-foundation)及`.artifacts/implementation/M1`，最终独立复核结果在同一证据目录登记，用户已批准A(M1)，B11～B13随本次Git集成记I(B11)／I(B12)／I(B13)。正常dev用保留的原版本恢复31388／31390，补齐实际恢复启动的运行元数据以保持当前数据客户端可读；配置、默认指针、令牌、业务表行数与引擎散列不变。M1页面使用隔离工作区，实际地址见候选回执；不要把旧dev页面当作M1页面。

⑤复用原生当前图、会话撤销、转换和队列；重要方案另存，每次运行保存实际图与参数。首版Agent针对明确活动画布操作，手动改图即接管，用户明确交回后继续；切图暂停后续编辑或新提交，已受理运行继续。实际执行的图像节点产生多次轻量预览，用户选择完整结果后才交②保存。相关桥接、运行记录及预览仍待实现或验证。

2026-10-27确认：Agent日常局部改图，整图JSON用于导入或明确替换；运行先保存当前画布，失败不提交；用户在目标网页点击“交给Agent”绑定页面。未来精简MCP的三个入口设计及58业务迁移清单见契约文档，均尚未实施。原生连接命令／响应、可靠UI确认、软件装配及科学执行须原型，当前没有画布MCP能力。

默认运行保证为可复现，可明确选择仅引用；固定素材组范围、新运行使用纠正资料、节点更新规则及原件保护保持。个人偏好可查看和恢复历史，删除包括历史正文；该能力仍待实现。

第④阶段确认：④定义JSON、⑤记录SQLite，原生连接的有限中继及一个白名单平台节点包；外部变化确认后同Asset新增内容记录，仅显式引用更新，旧组／旧运行不改；软件安装／更新由网页确认准确计划后执行。文件落位、公开签名、原生最终写与入队检查、实际取消／停止、无网页事件及具体测试归属均进入详设。软件首包／操作、可靠页面交回、装载、目标转换、科学缓存与实际缩图仍需原型；详设不是这些能力已通过的证据。

## 当前实现

- 固定 ComfyUI 0.42.0 和前端 1.57.1 的原生网页平台。画布始终挂载，节点库下依次为素材库、工作流；启动打开素材库，设备管理位于导入旁。
- Python 已按 core、contracts、modules/data、interfaces 归位；自研 UI 与原生桥接分开。③软件、④节点及⑤工作流业务目前只有文档，不表示已实现。
- 已有资产与集合版本、项目固定引用、导入、设备快照、校准关联、预览和回收站。schema 为 `0009_remove_legacy_capture_profiles`，数据 MCP 为 58 个工具。
- 单图自动拉伸从原件计算 RGB 背景白平衡和 MTF 配方，同步大图与缩略图；不修改原件、科学参数、版本身份和其他成员。

当前边界见[架构概览](../architecture/overview.md)、[模块导航](../architecture/module-map.md)和[素材行为](../architecture/assets.md)。

## 当前运行基线

- 开发 Python：`.artifacts/venvs/dev`，使用根 `uv.lock`；Node 26.8.2、pnpm 11.13.1，前端锁文件为 `frontend/pnpm-lock.yaml`。
- 正常 dev workspace：`.artifacts/workspaces/dev`，网页 31388、领域服务 31390；根 `.env` 与默认指针仍选择同一 workspace。
- 固定 CPU runtime：真实用户 LocalAppData 下的 `AstroPhotoFlow/runtime/native-web-0.1.0`，与旧 0.1.0 runtime 分离。
- 产品输出：`.artifacts/build/frontend`、`.artifacts/build/python`、`.artifacts/dist`。完整网页由 workspace/web 提供，不依赖 custom node 或扩展加载业务界面。
- 改名收尾隔离验收：`.artifacts/workspaces/docs-update`，网页 32588、领域服务 32590，不激活为默认 workspace。

目录改名后已按锁文件重新安装 dev，修复 editable 安装和命令入口；AstroPhotoFlow MCP、默认指针、编辑器和项目工具脚本中的有效旧路径已修正，其他 MCP 配置保持。本机固定工具入口为 `.artifacts/redesign/bin` 与其 Node 26 目录，不使用系统中版本不同的 Node/pnpm。

受限执行环境会将 LOCALAPPDATA 重定向到沙箱目录；本机维护使用正常用户环境访问已有 runtime，不修改产品路径解析，不新建另一套 CPU runtime。

2026-10-26 改名收尾已验证 dev 网页、HTTP、CLI 和真实 MCP 访问同一库，112 条存量资产在重启前后保持；这里的数量是当时观察值，不是后续固定验收条件。当时正常 dev 保持运行，隔离实例已停止，32588／32590 已释放。启动回执已修正为 `#/workflows`；需求归并未重新启停或核对实时服务状态。

原件、令牌、配置与锁文件保持；SQLite 主文件字节在启停后变化，但 17 张逻辑表与改名前快照的行级摘要一致，外键检查通过。运行与发行证据统一记录于[验证矩阵](test-matrix.md)。

wheel 源码目录外安装、无 Node 的 sdist 重建与重装已在改名收尾通过；需求归并未重新构建发行物。运行证据仍只覆盖 Windows／CPU，首次引导体验与 Linux 验收没有因此标为完成。

## 已取消的旧任务

不重建历史 restructure 验收环境，不恢复 redesign 实例或 `branch/redesign`，也不重新执行目录切换任务。

## 后续有效待办

- M1已由用户确认通过并集成dev。M2的B21～B24在当前`feature/database_management`形成实现候选；需完成独立功能验收、用户审阅和Git集成后，才记录为已完成Milestone。B31前锁定软件包／操作，B56前比较固定模型候选；其余15个Batch尚未开工，不创建空适配或空路由，S0仍未整体验收。
- ①M1已补齐默认workspace、保存／采用值、自动端口／实际地址、真实启停／重启、最近控制结果及网页配置；M2候选已提供固定输入解析、文件变化确认、内部输出登记及只读移除范围。⑤活动运行输入保护、工作流影响提示、运行界面结果选择、记忆与完整比较仍待各自批次；原件／校准保护继续保留。
- ③锁定首个软件包、来源、准确版本和操作并真实验证安装／就绪；④推进共享可编辑定义、可选测试、更新影响确认、全参数新默认及变化端口重映射。
- ⑤按[统一阶段](../../src/astrophotoflow/modules/workflows/README.md#phases)形成原生当前图项目关联、自动保存／另存、活动网页MCP、当前控制、真实运行记录和逐图像节点自动预览任务；切图后拒绝迟到写，后台结果归原图，无网页只查询。
- 验证两类输入保证、实际目标范围、原生缓存机制、③调用及实际停止、运行持久保存和所选完整结果交②登记；未知先查询不重跑，不建额外图调度／转换／恢复框架。
- 精简MCP整体迁移58工具及Skill／参考／配置／真实客户端测试，Skill已知能力直达、需要时分型混合Top10和显式关键词降级；现有业务不遗漏，不留旧入口。
- S6保留跨软件、完整查看比较、固定结果显式续跑、本地偏好及Python／复合节点；节点导出安装和Judge实际接入另行规划，不前移首个闭环，不预建空接口。
- 后续实现须真实业务与客户端验收，历史FFmpeg跳过、Linux未验证和未完成业务项继续保留，不能把本轮文档检查或现有58工具当成产品闭环已交付。

第④阶段补充确认：新画布先选项目并原生保存，再交给Agent；同图控制按当前允许/撤销状态跨客户端共享，不区分客户端身份。由用户主动指定页面，已接管仍要明确交回，不新增临时图控制或客户端会话体系。
