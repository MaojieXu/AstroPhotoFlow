> 历史设计参考（2026-10-29退出现行计划）。签名、状态和任务顺序可能过时；不能直接据此实施。当前任务见 [当前计划](../../../development/implementation-plan.md)。

# 五模块接口契约与文件级详细设计

## 2026-10-29 Bundle 增量契约（实现候选）

- `BundleManifest` 固定 schema_version/host_api=1，标识 package、bundle/software version、Windows 平台、程序/适配器相对路径、操作与节点文件。`ProcessPlan` 返回 arguments、outputs、output_format、可选 linear_sample；不接收任意用户脚本。
- `GET /api/v1/nodes` 与 `GET /api/v1/nodes/{definition_id}` 返回 `NodeCapability`，包含有效定义、content_token/native_type、操作、可用原因、preview/help/examples。
- `POST /api/v1/canvas/graph` 消费 `CanvasGraphRequest`：精确 operation/page/workflow/graph ID、content/control token 和一个 edit（inspect/add_node/set_parameter/connect）。沿原生连接返回实际 graph/node/link ID、新内容 token；未知结果不自动重放。
- `POST /api/v1/software/preview` 消费 `BundlePreviewRequest`，固定引用、成员索引、消费者/generation、package/operation ID 和参数；返回 PNG。DELETE 同路径/consumer_id 取消。旧 Siril 预览入口保留协议适配，正式调用使用内部 `/internal/native/bundles/calls`。
- 本轮增加 list_nodes/get_node/get_canvas/edit_canvas 四个 MCP 工具和对应 CLI；不实施整套精简 MCP 迁移。当前完整字段以契约类和 OpenAPI 为准。

2026-10-29 已实现候选覆盖：③补齐 SoftwareInvocation／Observation／Result／CancelResult／Use 及 invoke／inspect／cancel／usage；首操作为固定 Siril 1.4.4 Auto Stretch，完整 FITS 的 one-or-many 有序输入／输出使用 APF_SCIENCE，指定 HDU／切片未支持。新增 SoftwareUninstallRequest(package_token)，卸载提前交付为保留图及定义的程序移除，不改写图，不代替 B55 更新影响。NativeSirilCall 仅传固定科学引用（或同 prompt 已检查的 OutputLocator）及三个真实参数，内部按原生 prompt_id 固定工作目录；不接受路径、shell、URL 或脚本正文。窄原生适配与调用 JSON 是本轮首节点的真实消费者，不代表下文 M5 完整 NativeNodeCall／SQLite 运行契约已实现。详见[本轮任务](../development/batches/03-software.md)，测试尚未执行。


2026-10-28 素材入画布窄候选补充：②prepare_canvas_data提供固定InputReference，⑤canvas.py与宿主canvasDataBridge／useCanvasDataSession实现按钮、拖放及已授权活动画布的MCP／CLI加数据。实际HTTP及字段见[现有接口](../../../api/README.md)；此增量不等于下文B51／B52完整项目关联、通用改图或运行协议已完成，测试未执行。

**状态：未来接口设计与当前实现分开记录；M1／M2已有实现，B31／B32／B41已有本地候选。** 当前文件／公开函数／消费者见[源码映射](../../../architecture/module-map.md)。 本文仍是五模块契约和文件级详细设计的统一入口；[接口说明](../../../api/README.md)、[OpenAPI](../../../api/openapi.json)及源码描述当前实现，不用本页替代已实现请求模型。B32安装／准备及同socket页面确认已有代码，真实确认与下载安装仍待验收；动态节点加载、受控运行、MCP迁移及其余原生桥接仍待对应Batch。

依据[现行需求](../../../requirements/README.md)、[总架构](../../../architecture/overview.md)、[五模块数据设计](../architecture/data-models/README.md)和模块概要。2026-10-27 用户确认：**日常局部改图；整图 JSON 用于导入或明确替换；保存当前画布成功后运行；在目标网页点击“交给 Agent”绑定该页面。** 取舍见[ADR-0059](../../../../frontend/docs/adr/WORKBENCH-WORKFLOWS-0059-native-editing-save-and-agent-target.md)。

## 1. 已有接口与必要增量

| 事实来源 | 已有能力 | 本轮设计的增量及限制 |
|---|---|---|
| [领域 HTTP](../../../../src/astrophotoflow/modules/data/routes.py)、[软件路由](../../../../src/astrophotoflow/modules/software/routes.py)、[系统接口](../../../../src/astrophotoflow/interfaces/http/system.py)、[同源代理](../../../../src/astrophotoflow/comfyui/proxy.py) | 当前 89 个公共HTTP操作，与OpenAPI／固定代理路由对应；M2新增素材内容观察／确认，B31只读包列表／版本命令目录，B32详情／安装计划／准备查询 | 软件安装计划需同原生页面WS确认；真实安装、节点加载、软件执行和能力检索仍待后续Batch；工作流移除影响由B54／B57接入，M2科学输入与所选输出登记已有Python交接，⑤消费及偏好仍待实现 |
| [客户端](../../../../src/astrophotoflow/client.py)、[MCP](../../../../src/astrophotoflow/interfaces/mcp/server.py)、[工具参考](../../../development/library-agent-tools.md) | HTTP 客户端、CLI、58 个数据工具；图片工具返回真实图像内容；AssetClient已有软件包列表／命令目录／详情／安装计划／准备五项调用 | 软件、节点、画布与运行 MCP 未实现；精简 MCP 是后续整体迁移 |
| [工作台控制](../../../../src/astrophotoflow/core/workbench.py) | init/start/status/stop/restart、自动端口及实际地址、结构化就绪、配置／采用值、固定runtime、两个服务、进程文件 | M1已集成dev并获用户批准；MCP本机启停及后续业务占用待补，start/stop/restart已不改变默认workspace |
| [原生文件](../../../../engine/ComfyUI/app/user_manager.py)、[工作流 Store](../../../../frontend/src/platform/workflow/management/stores/comfyWorkflow.ts) | userdata 保存／读取／改名／删除，临时文件后替换；自动保存、本地草稿、另存与会话撤销 | 项目关联与当前控制没有接入；原生文件写入不是已有 Agent 改图接口 |
| [原生转换](../../../../frontend/src/utils/executionUtil.ts)、[引擎接口](../../../../engine/ComfyUI/server.py) | graphToPrompt、object_info、POST /prompt、/queue、/history、/api/jobs、定向取消及 /ws 事件 | 复用转换与调度，补受控提交、实际运行保存和软件调用；/api/jobs 同样来自内存队列／history，不是持久运行库 |
| [原生事件消费](../../../../frontend/src/scripts/app.ts) | UI 输出、执行事件、当前画布显示 | 多次完成预览按任务归原图；当前 rootGraph 路由不能证明切页签后归属正确 |

原生 `/ws` 已有feature_flags等原生消息及B32的 `apf.page` 软件页面事件候选，仍没有本文的改图协议；`client_id`／socket 标识只负责路由，不证明授权。`/view` 和 `/upload/image` 也不代替科学文件交接。上述结论来自静态源码核对，不是本轮运行验收。

<a id="common"></a>

## 2. 共同约定与入口选择

- **同一业务能力**：网页经 `/astrophotoflow/api/v1` 同源代理，CLI／MCP 经 `/api/v1` 调用领域服务；同进程模块调用公开入口，不读其他模块的 ORM。①启停是例外：由目标服务外的本机控制入口执行，才能启动尚未在线的服务；不增加第三个常驻服务。
- **名称与实现**：下表操作名和新增路径均为设计名，不是已注册工具或现有路由；内部交接不各自生成 HTTP API。已有字段、分页、认证及错误以 OpenAPI／当前模型为准，不复制 112 份 schema。
- **认证与错误**：沿用 workspace Bearer、同源检查、`X-Request-ID` 和 `{error:{code,message,fields},request_id}`。已有数据 PATCH 保留省略／null／0、`base_revision` 语义。新增目标／内容／控制冲突返回 409 及实际原因；不存在 404，输入不支持或不可执行 422，依赖／桥接暂不可用 503。客户端断连是“结果未知”，不能伪造一个服务已返回的失败。
- **当前内容**：`content_token` 是宿主按原生变更语义维护的当前内容标记，`control_token` 识别过期控制；它们不代表永久图修订、版权身份或身份认证。写入处重新核对，不只在 MCP 入口检查。
- **确认**：安装、更新、永久清理等仍需具体计划确认或明确预授权。业务检查确认覆盖的目标、版本和影响；软件维护和画布交回的网页确认不能由Agent自填 `confirmed:true`、工具文本、Origin或socket编号代替。已有数据／节点动作仍要求调用方明确取得用户授权，服务校验具体范围及影响，不在此新增通用审批系统。原生 UI 手势与受控调用之间的可靠交接须验证，不新增角色／通用审批账本。
- **异步事实**：受理、画布已应用、图已保存、引擎执行、科学产物可用和素材已保存分别表达。只有真实观察才返回成功；未知先查询。长处理不持有数据库事务，request ID 和 prompt_id 本身不保证防重。

表中“输出”均指必要内容；字段只在对应行为适用时出现，不要求每个模块返回统一的大对象。S1～S6 是交付阶段，不是服务数量。

<a id="foundation"></a>

## 3. ① 打开工作台、配置与维护

依据FR-13～15、AT-01／25，S1补最低基础，S6完善维护。M1候选已有本机init/start/status/stop/restart和网页配置；未来MCP控制调用同一入口，真实接入留B57，不据此新增工具注册。用户M1批准与dev集成仍另行记录。

| 逻辑操作、调用方 → 提供方 | 必要输入 | 输出及失败含义 |
|---|---|---|
| `foundation.start`，CLI／MCP → 本机控制 | 明确 config 路径或 workspace；省略按 config.toml 默认解析 | `workspace_path`、`state`、`web_url`、`service_url`、`reused`、最近结果／日志位置。核对同 workspace 双服务身份和健康后复用；他程序占用则选可用端口，就绪后写回实际端口；未就绪不返回可点击成功地址 |
| `foundation.status`，CLI／MCP／网页 → 本机控制／服务状态 | 目标 workspace | 当前进程及实际地址、健康／就绪原因、有效配置、最近操作结果；缺失、部分在线、未知分别说明，不把“发现 PID”当作已就绪 |
| `foundation.config.get/save`，网页／CLI → ① | 读取目标；保存具体可编辑配置及读取时配置校验值 | 返回最新保存配置、当前有效值、`restart_required`；性能项下次重启采用。冲突重新读取，不覆盖新修改；保存不自动重启，不建配置历史 |
| `foundation.stop/restart`，CLI／MCP → 本机控制 | 固定目标 workspace；restart 不顺带改默认指针 | 返回当前／最近控制结果及实际地址。复用 stop 排空；restart 繁忙或无法确认空闲时拒绝并列阻塞原因，不安排自动重启。断连后 status 核对，不重复重启 |

MCP 的 start／status 必须在创建依赖在线 HTTP 的业务客户端之前可用；不能把它们实现为只调用已停止服务的 HTTP 路由。复用进程文件和少量最新状态文件，不建立维护记录库。当前start/stop/restart已不修改默认workspace；初始化是否设为默认由activate参数控制，MCP定向控制仍待B57。

M1网页配置使用 `GET/PATCH /api/v1/settings/workbench` 读取当前workspace保存／有效配置并保存可编辑值；PATCH带读取时校验值，响应字段沿上表。停止后的查询与控制继续走本机入口，不为此新增在线控制服务。

①向②③⑤查询真实繁忙／排空信息：返回 `busy`、阻塞任务说明及 `unknown` 原因；空闲检查到进入维护间不得再接纳冲突操作。③安装更新及⑤运行在所属模块登记占用，不由①扫描私有业务表；机制随实际模块接入，不创建通用资源调度器。

<a id="data"></a>

## 4. ② 导入、选择科学输入与保存所选结果

M2已在dev实现`resolve_inputs`、`observe_reference_inputs`、`check_output`、`render_output_preview`、`register_output`、`get_output_registration`、`preview_library_removal` Python公开能力，以及素材文件变化观察／接纳两个HTTP路由。它们与原有16个业务模型、AssetTask流程配合，不新增迁移。内容接纳路由为`POST /library/assets/{asset_id}/content-observation`和`POST /library/assets/{asset_id}/content-accept`；科学输入及输出登记仍不单独暴露HTTP／MCP，等待⑤实际运行消费者接入。M2用户Milestone批准及跨工作流验收状态以开发矩阵为准。

### 4.1 现有操作继续复用

导入按钮与 Agent 使用相同上传／授权目录导入能力：创建上传批次 → PUT 文件 → start；本机目录只浏览配置允许的 root → import。任务通过现有 task 查询／取消／resume／retry，登记、原件处理和预览分别报告。resume 延续中断任务，retry 按现有分阶段规则处理失败项，不能等同于重新独立导入。同批重复来源跳过，独立导入建立新素材，具体请求见[现有工具参考](../../../development/library-agent-tools.md)。

项目查询和固定引用、资产／集合查询、设备快照和校准仍用现有模型及 `base_revision`。集合增加成员后项目继续引用原 `dataset_version_id`；明确更新才换版本。文件选取范围与科学处理范围不能从聊天、目录名或预览猜测。以下为新增交接，S2～S4；偏好和完整比较在 S6。

### 4.2 新交接

| 操作、调用方 → 提供方 | 输入 | 输出、失败与用户下一步 |
|---|---|---|
| `resolve_inputs`，⑤ → ②公开入口 | `project_id`；已选资产版本／集合版本引用；必要的 `hdu_index`／受支持切片选择；`input_mode`=`reproducible` 或 `reference` | 有序成员、稳定 ID／版本、可读科学文件交接、当前纠正资料及其 revision、实际采用的选择／校准、内容检查结果和准备成本。⑤保存本次实际值；③只消费明确文件交接。缺失、变更待确认、空间不足、不支持选择明确阻塞，不用预览补位、不降级 |
| `data.removal_preview`，网页／MCP → ②协调⑤ | 已选素材／集合 ID，移除范围 | 沿现有清理预览补充受影响工作流及节点；确认范围变化须重新展示。确认移除后⑤保留节点并提示重新选择；活动任务、校准和原件保护仍按现有规则，不把引用提示改成无条件永久删除 |
| `runs.save_output`，网页／MCP → ⑤协调② | `SaveOutput`，含准确`OutputLocator`及可选`name` | 返回 `save_state`、已有导入任务或 `asset_id/asset_version_id`、来源运行和错误。仅选择的完整科学结果进入托管素材库；未命名用默认名。预览、任意客户端 path、已清理输出不能冒充可保存原件 |
| `runs.get`中的输出保存状态，网页／MCP → ⑤读取②事实 | 已知`run_id`；响应outputs中的原定位及task／asset关联 | 返回未请求／处理中／已保存／失败／未知及真实关联。提交后断连或登记失败先核对；同次保存续查／补登记不得重复创建资产或重跑软件；不再为同一查询另设data.output_save_status别名 |

`resolve_inputs` 是同进程能力，不把内部绝对路径无差别暴露给外部 MCP。托管输入已有固定可读内容时不每次复制；仅引用记录较弱保证和执行前后观察，不能保证外部旧字节始终存在。外部文件变更接纳仍待实现；未确认前不换新文件，确认后沿同一素材新增内容记录，仅显式选择的引用改用新内容，固定组不原地改写，不承诺恢复已丢失旧字节。

内部文件交接的最少字段为：

| 字段 | 语义及消费者 |
|---|---|
| `items[].asset_id/asset_version_id` | ②解析身份与固定内容，⑤记录，③不凭文件名重建身份 |
| `dataset_version_id/member_index`（适用时） | 固定组版本和成员顺序；处理的子集也明确列出，不随库中追加变化 |
| `selection` | 已明确的 HDU／受支持切片或工具支持的完整文件选择；原始视频不默认拆帧，不把首帧预览作为输入 |
| `read_path/content_check` | 仅供受控执行的可读完整科学文件及本次内容检查；保护原件，③只在运行工作目录写输出 |
| `parameters/parameters_revision` | 本次采用的纠正资料及 revision，连同导入接收快照的区别一起保留；执行后修改资料不回写旧记录 |
| `input_mode/preparation` | 实际采用保证、是否准备固定字节及成本／失败；⑤记录采用结果，不只记用户请求模式 |

这些字段随本次运行保存，不新增一个可独立编辑的输入库。③返回的产物至少带节点／输出／成员定位、实际文件及检查所需格式信息；⑤核对预期输出与实际可读性，必要时调用②公共文件检查能力。部分文件不能冒充全部成功，检查不自动登记素材。

结果保存可复用现有托管导入处理及任务查询，不另建“登记回执”对象。⑤在输出处关联保存任务／资产，②保存真实资产权威。选中后若文件已不可用，明确要求重新处理或选其他结果，不自动重算；本页不设中间文件清理期限。

移除影响的未来远程映射为 `POST /api/v1/library/items/removal-preview`，选择格式复用现有移除请求；返回受影响工作流／节点和已确认范围的校验信息。实际移除扩展现有 `DELETE /library/items`，重新核对本次确认的影响，变化则返回冲突并要求重查；这属于后续接口变更，不声称现有 DELETE 已支持工作流检查。结果保存只经⑤的 outputs/save 交接，不在②再建一条等价登记接口。

### 4.3 偏好与后续资料

S6 的必要业务操作为 `list/get/save/update/disable/delete/history/restore`，不是八个固定 MCP 工具。资料至少表达内容、workspace／项目范围、用户表达或 Agent 分析、来源项目／结果、当前有效性。用户满意后 Agent 可自动写分析并跨项目参考，用户可查看修改；恢复指定历史内容成为当前，不改旧运行；删除包括旧正文。只为偏好保留所需历史，不推广成全业务修订框架。完整聊天留在客户端，具体请求和历史存储在 S6 任务细化。

夜间目标汇总、比较指标、ROI 和采用方案先保持②的数据责任及⑤运行／预览关联；不为算法未定内容生成新接口或表。

<a id="software"></a>

## 5. ③ 安装软件包、准备与更新

FR-03／13、AT-02／03／25／33；S2 首包及目录，S3 进入节点，S4 真实调用，S6 完整维护。网页和 MCP 经同一③应用能力；包清单由项目维护，Agent 只能选择清单条目，不提交任意下载 URL 或安装脚本。

| 操作 | 输入 | 输出与边界 |
|---|---|---|
| `software.list/get` | 可选 `package_id` | 名称、清单可选版本、已安装版本、安装位置、可用状态及原因、配套节点；下载地址来自维护清单，不让客户端改写来源 |
| `software.install` | `package_id`、清单准确版本、读取时package_token | 202当前待确认动作和网页地址；网页确认具体计划后才安装，GET查询实际阶段；Agent不分别连接软件MCP |
| `software.prepare` | 已安装包 ID | 返回软件或平台内需要用户操作的界面／步骤及未就绪原因；密码、验证码、许可证由用户直接输入，Agent 不读取、转发或保存具体内容；完成后重新检查实际可用性 |
| `software.update_preview` | 包 ID、目标版本 | 当前版本、受影响工作流／节点、变化参数及新默认值、删除节点、运行阻塞。返回当前包／定义及各图的内容校验，供确认对应影响，不建持久安装计划对象 |
| `software.update` | 同一目标及影响校验 | 202当前网页待确认动作；用户确认后重新核对繁忙及影响再替换。变化参数新默认，缺节点保留；逐图报告，不后台排程或承诺原子回滚 |
| `software.uninstall` | 包ID、读取时package_token | 202网页待确认动作，确认后才移除；使用中阻塞。保留图节点、原件、自制定义和历史运行 |

未来 HTTP 映射：`GET /api/v1/software/packages`、`GET /api/v1/software/packages/{package_id}`；上述动作分别为该包路径下的 `POST /install`、`/prepare`、`/update-preview`、`/update`、`/uninstall`。包 ID 由路径提供，其他输入放 JSON 正文，返回沿表中同一业务结果；只接受维护清单的准确版本。查询同时返回正在进行的准备状态，不另建安装任务资源体系。

③向④提供配套定义与操作描述，向⑤提供当前可用性与实际调用观察。更新影响由⑤读取图并执行原生更新，④维护定义；这不是绕过活动画布规则的普通 Agent 改图。经用户明确批准的软件维护仅修改已确认图，碰到未同步草稿或新变化先报告冲突，不自动覆盖。重新安装后以实际加载和就绪为准，不承诺旧版长期并存或历史可复现。

### ③ → ⑤ 的执行交接（内部）

⑤传入本次运行及节点关联、准确软件／操作、明确科学输入、有效参数、受控工作目录和预期输出；③核对安装／许可后实际调用，报告调用标识、进度依据、日志位置、退出／错误、实际输出及取消能力。超时、传输断连、工具取消、桥接停止和应用退出分别表达；③不自行登记素材，不判整图成功。会话及内部通信按首软件原型确定，不预建独立会话／占用历史模型。

<a id="nodes"></a>

## 6. ④ 制作、保存与更新自定义节点

FR-16、AT-03／29；S3 首种操作封装，Python／复合 S6，导出安装另行规划。软件包配套节点遵守③政策，以下全参数重置规则仅针对自定义节点。

| 操作 | 必要输入 | 输出及失败含义 |
|---|---|---|
| `nodes.list/get` | 可选 `node_id` | ID、名称说明、输入／输出、参数默认值、执行内容及当前内容校验、实际加载／就绪原因、最近测试运行链接及是否仍对应当前内容 |
| `nodes.save` | 名称说明、端口、参数、执行绑定；更新时另走确认流程 | 保存节点 ID／定义及实际加载结果。保存可直接使用，测试不是门槛；保存成功但加载失败分别报告，不假报可执行 |
| `nodes.test` | 节点当前内容、明确测试输入和参数、目标页面上下文 | 应用装配交⑤同一运行入口，返回 `run_id`；不增加执行器或证据库。首版测试用明确在线测试画布并先保存，不隐含覆盖用户正在编辑的图；⑤查询最近测试 |
| `nodes.update_preview` | 节点 ID、拟保存内容 | 受影响图／实例、全部参数的新默认值、保留／断开的端口连接、内容校验。说明旧测试针对旧内容 |
| `nodes.update` | 拟保存内容、已确认影响及对应校验 | 替换定义并由⑤更新确认范围，返回保存／加载和各图更新情况；新冲突先报告，不声称跨文件原子完成。执行中及历史内容不改，不要求旧实现长期并存 |

未来 HTTP 映射：`GET/POST /api/v1/nodes` 列表／首次保存，`GET /api/v1/nodes/{node_id}` 读取，节点路径下 `POST /test`、`/update-preview`、`/update` 对应上表；JSON 正文使用表中字段。网页、客户端和精简 MCP 共用这些应用能力，不直接改定义文件或图文件。

输入名称各自唯一，输出名称各自唯一；同方向、名称和类型均不变时保留连线，包括只重排端口；改名、改类型、删除则断开对应线，增加端口不自动连接。⑤按原生端口／参数机制更新（含已转换为输入的参数控件，名称/类型未变保线，默认值仍重置），**所有实例参数采用新默认值**，不另建参数兼容迁移框架。

执行绑定指向受支持的③操作；端口／参数的映射是节点内容，不是独立管理对象。固定值、连线供值和实际输入采用值在运行中记录。S6 用户 Python、复合内图及导出格式本轮不定义执行环境或包协议；修改复合内部仅作用当前工作流，不回写节点库。

<a id="workflows"></a>

## 7. ⑤ 读取、改图、控制与运行

FR-01／02／07～11、AT-06～11／14～18／24；S3 最小项目编排与测试，S4 运行，S5 完整在线交互。`workflow_id` 使用原生持久图身份，节点 ID／子图定位使用原生格式；不拿页签会话编号当持久图编号。

### 7.1 对外形态与必要字段

下表为**未来 HTTP 设计路径**，均在 `/api/v1` 下；同源代理、客户端和精简 MCP 调用同一处理能力。只把真实远程需求设为接口；保存桥接委托原生 Store，另存／改名／删除复用原生文件操作，由⑤挂接项目关系及预览清理，不再平行做一套文件存储。

| 路径／操作 | 输入 | 结果 |
|---|---|---|
| `GET /projects/{project_id}/workflows` | 项目 | 原生图身份、名称／位置及必要关联，不复制整图权威 |
| `GET /workflows/{workflow_id}` | 图身份 | 已保存原生 JSON、项目和位置；在线目标另返回实际画布内容及是否未保存，不混称保存图 |
| `GET /workflows/agent-context` | 当前明确绑定的页面；不可自动选择另一页面 | `target`、当前 `content_token/control_token`、Agent 是否允许、活动／在线／同步及保存状态、受支持操作。未绑定返回需要用户在目标网页点击交给 Agent；不列出后自行猜选 |
| `POST /workflows/{workflow_id}/edits` | `target`、预期两类 token、`operations` | 各操作实际结果／新原生 ID、最新 token、`applied` 和 `saved` 分别返回；失败或部分应用说明实际情况，不伪装整批事务回滚 |
| `POST /workflows/{workflow_id}/save` | 同样目标及两类 token | 委托活动页面原生保存，返回实际 `saved`、位置和内容校验；新图先落实保存位置，失败保留当前草稿。运行内部也使用这一个保存能力 |
| `POST /workflows/{workflow_id}/replace` | 同样上下文、完整原生编辑 JSON、用户明确替换意图 | 原生加载实际结果、缺失节点和保存状态；导入需明确项目关联，覆盖已有内容须明确，不在普通调参时整图替换 |
| `POST /workflows/{workflow_id}/runs` | 客户端本次生成的 `run_id`、上下文、范围、输入保证 | 本次 `run_id`、提交状态、原生 `prompt_id`（已有时）、阻塞原因；受理不是完成，详见下文 |
| `GET /runs/{run_id}`、`GET /workflows/{workflow_id}/runs` | 已知运行／图；列表沿现有分页规则 | 本次实际图／输入／参数、范围和软件节点信息、引擎关联、进度／日志及结果、取消／实际停止、输出保存状态；内存 history 缺失不删平台事实 |
| `POST /runs/{run_id}/cancel` | 明确运行 | 分别返回请求是否送达、排队移除／停止观察及未知原因，不等同成功停止 |
| `GET /runs/{run_id}/previews`、`GET /runs/{run_id}/previews/{preview_id}` | 运行及已关联预览 | 按节点／输出／成员定位多次完成缩图及可读图像；MCP 返回图像内容，不能只返回客户端不可达的本机 URL |
| `POST /runs/{run_id}/outputs/save` | 节点／输出／成员和可选名称 | 调用第4节同一所选结果保存能力；不是登记所有产物；查询运行中的保存关联后再补登记 |

示例仅表达设计字段，`target` 包含 `project_id/workflow_id/page_id`，进入子图时附原生子图路径；不默认当前鼠标选中对象。`run_id` 是一次明确运行意图在运行记录内的关联，不增加提交意图表；由网页／客户端生成 UUID 并在网络不确定后用它查询，查询本身不再执行。

```json
{
  "guard": {
    "target": {"project_id": "11111111-1111-4111-8111-111111111111", "workflow_id": "22222222-2222-4222-8222-222222222222", "page_id": "33333333-3333-4333-8333-333333333333"},
    "content_token": "opaque-current-content",
    "control_token": "44444444-4444-4444-8444-444444444444"
  },
  "operations": [{"op": "set_parameter", "node_id": "12", "parameter": "stack_count", "value": 60}]
}
```

示例参数是占位说明，不声称某个软件已有该名称。实际类型、范围和默认值读④／原生定义；特殊控件未支持则明确拒绝，不猜索引或强制转换。

项目关联由⑤内部保存钩子消费 `project_id`、原生图 ID 和实际文件位置：首次保存／导入建立关联，改名更新位置，另存取得原生新图 ID，删除清理关联及专属预览。原生 Store 已有另存生成 UUID 的机制，不能改用会话 `instanceId`；同名外来 JSON 与已有图冲突时要求明确另存或替换，不自行推断为同一项目。关联元数据不包含第二份可编辑 JSON。

### 7.2 局部编辑和页面交接

- 最小局部操作为读取目标、添加／更换素材引用、添加库节点、改参数、连线／断线、移除节点、移动／分组及原生撤销／重做。每项带实际原生节点／端口标识；添加先返回原生 ID，再用于后续连接，不建立新图语言。素材引用含②的固定版本和范围，库节点使用④实际定义。
- 用户在目标网页点击“交给 Agent”时绑定该页面当前图并允许继续；按钮也承担手动接管后的明确交回。MCP 不提供自行赋予控制的操作；读取、重连或客户端新会话不能调用某个“恢复写入”旁路。浏览器的确认入口不纳入精简 MCP 的可调用能力目录。
- 只在绑定页面仍在线且活动图一致时应用；切图暂停，不自动跟随。手动改图／布局／撤销先更新当前控制标记，旧 Agent 写和新运行在实际受理处拒绝；查看、缩放、切页签不交出控制，已有运行继续。
- 干净画布应用变更并加入原生撤销；当前内容不一致、未确认接管或同步冲突时保留草稿，返回实际目标／控制及冲突原因。应用后仍须单独报告保存情况，不把通知送达当作已应用。丢失回执先读取当前图核对，不重放 edits。

桥接已选复用原生连接：领域服务经受控引擎HTTP下发，原生WS定向送达页面，同WS返回实际结果；业务入口仍是上述共享HTTP，不增加连接服务。**传输选择的原型必须验证页面身份、确认来源、定向返回和断连；当前 `/ws` 并未支持本协议。** 待处理响应只保留当前连接所需状态，不建立永久命令／画布回执账本。UI 包仅通过公开导出接入，原生单例只在宿主桥接使用。

首批 `operations` 的参数约定如下；原生布局／分组操作沿用已有操作模型，不重新发明通用图 DSL。

| op | 必要字段 | 实际结果 |
|---|---|---|
| `add_node` | `definition_id`，可选原生 `position` | 新原生 `node_id`；定义缺失或加载失败明确返回，不触发处理 |
| `add_data/set_data` | 新增或指定 `node_id`、已选固定版本及科学选择 | 固定范围的数据引用节点 ID；先经②核对项目可用范围，不直接存任意 path |
| `set_parameter` | `node_id/parameter/value` | 实际控件采用值；省略操作不会清空参数，null／0按该参数定义处理 |
| `connect/disconnect` | 源节点输出及目标节点输入的原生标识；断线可用实际 link ID | 真实连接／断开结果，不通过显示名称猜重名端口 |
| `remove_node` | `node_id` | 原生移除及关联线变化，不删除②素材或④定义 |
| `move_node`、`undo/redo` | 移动用 `node_id/position`；撤销／重做使用当前会话 | 原生布局或撤销实际结果；不在无会话时编造跨重启撤销 |

读取上下文附支持的操作列表；尚未桥接的分组／特殊控件不能被目录标为可用。批量中第几项已应用须返回，剩余项不自动重试；下一次先读当前图再决定继续。

### 7.3 先保存再运行

1. 人工按钮、快捷键、自动队列和 MCP 托管提交都进入⑤同一受理边界；Agent 请求先核对绑定目标与控制。受理后先在同次 `run_id` 记录准备状态，查询可区分尚未投队列；未保存新图先建立原生保存位置及项目关联。
2. 原生运行前控件准备和 `graphToPrompt` 各执行一次；核对转换期间没有人工改动且实际参数／拓扑一致，然后立即保存当前画布一次。保存失败阻止提交，不能只等待防抖自动保存。准备后内容变化明确阻塞，不自动重转或保存另一份图；完整顺序见[运行详细设计](#workflows-design)。
3. ②解析用户已选固定范围及当前纠正资料，默认可复现准备；显式 `reference` 才采用较弱保证。预检返回本次实际目标、依赖和未执行部分、输入成本、缺失软件／节点及转换错误；不自动降低保证、安装或缩小执行范围。预检信息并入本次运行，不建立独立计划资源。
4. 固定当次图、输入、有效参数／连线、节点执行内容和软件信息，提交前确定原生允许调用方提供的 UUID `prompt_id` 并写入同次运行，再交原生 `POST /prompt`。用它关联队列／事件／软件调用。相同 `run_id` 的重复请求只查询既有准备／提交情况，不能再投队列；内容不一致则冲突。中断位置不能证明是否提交时保留未知，先查队列／history／真实调用，不承诺跨进程严格只执行一次。
5. ComfyUI 调度，③实际调用并返回观察；⑤记录实际结果及必要调用，有产物才能报告可用。自动为本次实际完成的图像节点生成缩图，经原生 UI 输出／事件展示并按运行归原工作流。A 后台完成不写入当前 B；不持久化进度每帧，不把所有节点设终点，不重复记录缓存回放为新处理。
6. 取消针对该 prompt／实际调用，优先原生定向任务取消；原生返回无操作、已送中断、软件仍运行分别说明，不使用无目标全局中断误停其他任务。未知任务不提前释放软件占用。用户选完整结果时才按第4节交②保存。

运行查询至少区分准备中、排队、执行、完成、失败、取消和未知；输出检查、取消请求／停止依据、所选素材保存情况分别返回，不扩成一个混合“大成功”状态。可无可靠百分比，此时返回阶段、时长和日志。原生 history 可清除／重启丢失，⑤记录仍在；缺证据不推断失败或成功。预览失败不等于科学文件丢失，须分别显示。

提交的 `scope` 为 `{"mode":"all"}` 或 `{"mode":"targets","node_ids":["12"]}`；后者是目标及必要依赖，不是只运行选中节点。返回本次实际终点、依赖范围及未执行部分；不支持的目标阻塞。`input_mode` 默认 `reproducible`，明确 `reference` 才改变保证。实际调用参数由本次绑定与连线解析产生，不接受 MCP 另传一份与保存图无关的执行参数。

受托管的软件节点在实际调用③前还须核对该运行保存的执行上下文、节点和允许文件范围；不能只在网页或MCP入口检查，也不把裸 `/prompt` 请求的任意 `extra_data` 当作可信运行凭据。原生其他节点的执行事实不自动冒充平台受托管运行；受支持桥接与原生入口的联调必须覆盖这一边界，不另建图调度器。

完整重跑创建关联的新运行，仍须符合当前活动页面、保存及控制要求；不改旧事实。S6 显式续跑只引用已保存、可读的固定科学结果，不从压缩预览或内存缓存恢复。恢复旧运行方案先明确加载当时图，需要保留当前方案则另存，不改历史运行或取消已有任务。

<a id="mcp"></a>

## 8. 精简 MCP：按需发现与调用

以下为**未来设计工具名**，本轮现有58工具及 Skill 不变。S2 实施时整体替换，数据 HTTP／CLI 继续共用原业务能力；不同时保留旧注册工具、兼容别名或双轨模式。

| 未来固定 MCP 入口 | 输入／输出 | 规则 |
|---|---|---|
| `search_capabilities` | `query`、可选类型／来源过滤 → 最多10候选及 `search_mode`、降级原因 | 仅发现未知能力时使用；本地固定 embedding＋关键词，模型不可用明确 `keyword`，不静默换能力 |
| `get_capability` | `kind/id` → 当前完整定义、来源版本、就绪原因；业务工具含参数 Schema、风险及前置条件 | 已知 Skill 可直接读取，无须先检索；节点／软件操作返回各自定义，不伪装为可调用工具 |
| `call_capability` | 业务 `id`、符合定义的 `arguments` → 真实业务结果／结构化错误及必要图像 | 仅调用登记的业务能力；查询／状态也通过所属操作，不另建全局操作账本。禁止客户端指定任意 HTTP URL、method、Python 路径或 shell 命令 |

候选含 `kind`（`tool/node/software_operation`）、`id/name/description/source`、当前版本或内容校验、`ready/reason`；索引可重建，不独立修改定义。节点通过⑤加入图，未封装操作经④制作后使用⑤执行，不由 MCP 直接绕过图调度运行软件。安装及准备工具属于③业务能力。

`call_capability` 的固定映射调用所属应用能力，经同一 HTTP；①本机控制例外已在第3节说明。业务确认、活动目标、内容和控制在所属实际提交处检查；包装器不得只靠工具说明限制。MCP 传输工具执行错误时保留业务 code／request_id／fields，图像保留 ImageContent，不把失败包装成成功文本。

### 58 个现有工具的完整迁移清单

下列名称作为现有业务盘点；拟用 `data.<现有名称>` 作为目录操作 ID，**不是继续注册同名 MCP 工具或兼容别名**。`import_photo/import_photos` 仍由客户端读取文件后走上传流程，不能变成服务任意路径读取。实施时同步 Skill、参考、客户端配置说明、真实 stdio／图像测试，要求客户端刷新工具列表或重连。

| 组 | 现有工具（合计58） | 迁移后的业务去向 |
|---|---|---|
| 导入10 | import_photo、import_photos、list_import_roots、browse_import_root、import_local、list_import_tasks、get_import_task、cancel_import_task、resume_import_task、retry_import_items | 原上传／授权目录／导入任务应用能力 |
| 素材与集合18 | list_assets、list_library_items、get_asset、update_asset、update_asset_parameters、list_asset_versions、get_asset_version、create_dataset、list_datasets、get_dataset、update_dataset、list_dataset_versions、get_dataset_version、publish_dataset_version、update_dataset_members、list_calibration_targets、remove_library_items、list_trash | 原查询、资料／集合版本、校准和移除／回收站 |
| 恢复与预览6 | restore_trash、preview_trash_delete、delete_trash、schedule_display_preview、get_display_preview_status、read_display_preview | 原恢复／确认永久清理和按需预览，保留 fingerprint 与图像行为 |
| 项目12 | list_projects、create_project、get_project、update_project、list_project_assets、get_project_asset、add_project_asset、remove_project_asset、list_project_datasets、get_project_dataset、add_project_dataset、remove_project_dataset | 原项目资料及固定引用 |
| 设备与预设12 | list_equipment、create_equipment、get_equipment、update_equipment、list_equipment_setups、create_equipment_setup、get_equipment_setup、update_equipment_setup、list_capture_presets、create_capture_preset、get_capture_preset、update_capture_preset | 原设备、使用组合及预设，保留接收快照 |

索引与检索不管理个人偏好正文，不保存完整聊天，不执行 Agent 推理。未来 Judge 的候选评价输入及来源仍为 S6 后另行接入边界，本页不生成模型／评分协议。




<a id="coverage"></a>

## 9. 详细设计与验收阅读顺序

第3～8节给行为和远程入口；下面确定关键文件、公开签名、类型、实际调用及测试归属。已有接口仍查OpenAPI，不复制已有112份schema。本页保留设计签名；M1／M2及B31／B32／B41已落位部分文件与测试，下文逐项区分已有与后续增量。不能把设计签名整体视为当前公开面。

- [文件与共同类型](#file-design)、[①](#foundation-design)、[②](#data-design)、[③④](#software-design)、[⑤](#workflows-design)。
- [原生跨进程交接](#native-design)、[精简MCP](#mcp-design)、[具体测试与FR／NFR／AT追踪](#verification-design)。
- 首软件准确发行版／操作／素材、目标转换、缓存、实际停止、桥接和加载须原型；设计明确责任和阻塞出口，不声称原型已经成立。S6细节保持延期。

<a id="file-design"></a>

## 10. 文件规划与共同类型

下列为拟新增／扩展落点；已有事实见第1节。跨模块入口为 `public.py`，路由只适配HTTP，`interfaces/http/app.py`显式装配；不预拆service／repository／manager、Protocol容器、第二图副本或调度器。

纯DTO复用 `contracts/common.py` 的StrictModel／UuidInput／ErrorDetail、Pydantic JsonValue；`JsonObject = dict[str, JsonValue]`在现有contracts/common.py定义一次，其他新契约显式引用。无默认值即必填，可空不等于可省略；JSON输入UUID沿UuidInput，输出沿UUID／UTC序列化。已有AssetParameters／AssetClassification／CalibrationBindings直接引用。内部Path／敏感字段不直接model_dump为MCP结果，长处理不持有数据库写事务。
`Settings.workspace: Path`已是显式配置解析结果，业务调用方不自行猜data_dir父目录。业务不导入接入层；组合根注入有限具体调用函数，迁移装配仍在现有Alembic入口。

| 必要文件 | 状态与责任 |
|---|---|
| `src/astrophotoflow/contracts/{workbench,inputs,software,nodes,workflows}.py` | `software.py`、`nodes.py`已实现B31／B41契约；`workflows.py`已有B32计划／网页事件组合DTO，⑤其余契约仍待实现；调用方向保持③④不反向引用⑤ |
| `src/astrophotoflow/core/config.py`、`core/workbench.py` | 已有，扩展默认workspace、当前采用值、结构化控制及固定薄引导 |
| `src/astrophotoflow/core/database/schema.py`、`core/database/alembic/env.py`、`versions/0010_workflow_records.py` | 已有schema.py同步目标revision，env.py显式装配⑤models／core Base，拟新增0010保存⑤关联／运行／预览；同步既有迁移与发行清单测试，不改0009历史，本轮不执行 |
| `src/astrophotoflow/modules/data/science_inputs.py` | M2已实现科学输入解析／结束观察、输出检查／纯文件预览、外部内容接纳及所选输出登记／查询；⑤真实消费待联调 |
| `src/astrophotoflow/modules/data/{projects,ingestion,trash,imports,public}.py` | 已有，窄提取项目公开读取、输出登记／查询／任务执行及移除范围；public已在既有导入／预览导出上增加繁忙、项目、科学输入／内容／输出及移除范围交接，函数见源码映射。新输出任务序列化不得泄漏内部source_path。既有16模型保持 |
| `src/astrophotoflow/modules/software/{public,routes}.py` | B31实现只读清单／命令／操作／配套定义；B32实现固定包下载、安装计划／准备及软件状态HTTP，实际confirm仍只接受原生网页事件 |
| `src/astrophotoflow/modules/nodes/{public,routes}.py` | B41已实现定义JSON／差异／替换；HTTP、加载和影响由后续Batch装配 |
| `src/astrophotoflow/modules/workflows/{public,routes,models}.py` | 拟新增⑤公开业务、薄HTTP及三个SQLite模型；唯一当前图仍在原生文件 |
| `src/astrophotoflow/interfaces/client/{software,nodes,workflows}.py`、根`client.py` | software.py已有SoftwareOperations五项HTTP操作并由AssetClient消费；nodes.py／workflows.py及NodeOperations／WorkflowOperations仍待真实HTTP消费者出现后添加 |
| `src/astrophotoflow/interfaces/http/{app,system}.py`、`interfaces/cli/main.py`、`interfaces/mcp/server.py`、`comfyui/proxy.py` | B31/B32公开软件HTTP和固定代理白名单已装配；安装Task／页面确认由app组合；MCP三入口仍待B57 |
| `src/astrophotoflow/interfaces/comfyui.py` | B32实现单socket `apf.page` 消息及页面身份回传；托管文件guard、入队范围guard、节点注册／执行等剩余适配待对应Batch |
| `engine/ComfyUI/server.py`、`app/user_manager.py`、`execution.py` | 已有，在原生实际WS／文件／入队／敏感hidden／事件处接薄钩子，详见第15节 |
| `frontend/packages/astrophotoflow-ui/src/core/WorkbenchSettings.vue`、`core/contracts.ts`、`core/client.ts` | M1已实现①配置／当前采用值与网页重启；demo候选已将现有表单迁入原生设置窗口，由宿主传入原生控件，HTTP与保存／重启契约不变；完整诊断仍待后续。B13已把data客户端的实际共用请求／错误代码窄移到这两个文件，不新建transport文件或网络框架 |
| UI包`modules/software/SoftwarePanel.vue`、`modules/nodes/NodeEditor.vue`、`modules/workflows/WorkflowPanel.vue` | B32已有软件计划／状态／确认面板；NodeEditor及项目图／运行／预览／结果保存界面待后续Batch，GraphView继续原生 |
| UI包各模块`api/contracts.ts`、`api/client.ts`、`index.ts`及包根`src/index.ts` | data／software入口及core共用客户端已有，nodes／workflows领域入口仍拟新增；各模块保存自身Zod产品DTO和具名客户端，根只公开实际消费者所需导出。FetchApi声明／共用请求代码归core/client.ts，data原入口直接重导出保留既有消费；原生JSON只校验对象，不复制其schema |
| UI包已有`modules/data/workspace/Workspace.vue`及设备表单 | 选定引用／拖入走公开宿主接缝；单像元输入明确写x/y，未修改则保留；不要求位深／赤道仪／配件，不删既有字段／类型 |
| `frontend/src/platform/astrophotoflow/workflowBridge.ts`、`NativeShell.vue` | 前者已有B32的confirmSoftware软件确认回调，⑤图编辑／控制／运行桥接仍待实现；后者挂载原生GraphView并按路由选择素材／软件侧栏；可用原生Store／画布，业务UI不可反向导入 |
| `frontend/src/scripts/{api,app,changeTracker}.ts`、原生`workflowService.ts/workflowStore.ts` | 已有，实际文件／编辑／提交／事件钩子详见第14、15节 |

B13共用ApiClientError已包含fields／code／requestId；后续客户端直接复用，不复制多套JSON／错误／图像请求处理。部分编辑事实仍由业务DTO保存。UI只显示事实或提交明确操作，不新起应用；双解释器适配的依赖隔离见第15节。

### 前端具名客户端公开面

下列包含已有WorkbenchClient／SoftwareClient与后续规划导出；当前公开面见源码映射，模型字段唯一按本设计对应DTO维护，UUID/Path/日期在前端使用其JSON字符串表示。组件只通过这些客户端消费业务HTTP；原生交回、人工运行和软件确认由宿主回调完成。2026-10-27用户确认：core/client.ts承接现data/api/client.ts的FetchApi、ApiClientError、createApiClient；core/contracts.ts承接现data/api/contracts.ts的errorSchema及①DTO。只窄移这段真实多消费者代码，data原路径直接重导出已有名字，各模块领域DTO不迁入core，core不反向导入业务。既有调用／错误分类／图像Content-Type校验保持，仅补已要求的fields；不新增请求抽象、定位器或客户端基类。

```typescript
export interface WorkbenchClient {
  getConfiguration(): Promise<ConfigState>
  saveConfiguration(body: ConfigSave): Promise<ConfigState>
}
export function createWorkbenchClient(fetchApi: FetchApi): WorkbenchClient

export interface SoftwareClient {
  listPackages(): Promise<SoftwarePackage[]>
  listCommands(packageId: string, version: string): Promise<SirilCommand[]>
  getPackage(packageId: string, operationId?: string): Promise<SoftwarePackageDetails>
  requestInstall(packageId: string, body: SoftwareInstallRequest): Promise<PendingSoftwareAction>
  prepare(packageId: string): Promise<SoftwarePreparation>
  previewUpdate(packageId: string, targetVersion: string): Promise<PackageUpdatePreviewResult>
  requestUpdate(packageId: string, body: SoftwareUpdateRequest): Promise<PendingSoftwareAction>
  requestUninstall(packageId: string, body: SoftwareUninstallRequest): Promise<PendingSoftwareAction>
}
export function createSoftwareClient(fetchApi: FetchApi): SoftwareClient

export interface NodesClient {
  list(): Promise<NodeDetails[]>
  get(definitionId: string): Promise<NodeDetails>
  create(body: { definition: NodeDefinition; operation_version: string }): Promise<NodeDetails>
  previewUpdate(body: { definition: NodeDefinition; operation_version: string; expected_content_token: string }): Promise<NodeUpdatePreviewResult>
  update(body: { definition: NodeDefinition; operation_version: string; expected_content_token: string; impact_token: string }): Promise<NodeUpdateResult>
  test(body: NodeTestCreate): Promise<RunDetail>
}
export function createNodesClient(fetchApi: FetchApi): NodesClient
```

路径、HTTP状态与错误分别按①③④契约映射，节点动作从body.definition.definition_id取路径身份，test从body.definition_id取；不另传可矛盾的ID。软件request*返回202当前待确认动作，不能展示为已安装／已更新。getPackage的operationId只用于核对当前确认链接，过期不静默改成新动作。更新与当前图的复合响应由应用组合产生，不让节点定义文件复制运行或工作流状态。

UI包根和所属模块index.ts公开这些类型／工厂及对应组件；FetchApi保持当前签名`(path: string, init?: RequestInit) => Promise<Response>`，声明权威在core/client.ts，可从原data入口直接重导出。WorkflowsClient沿⑤专节，不重列；其submitRun/edit是具名HTTP能力，实际人工编辑／运行仍通过宿主原生链，不能在UI请求体自填human。

数据UI继续现有具名方法，只为内容变化增加：`observeAssetContent(assetId: string): Promise<AssetContentObservation>`与`acceptAssetContent(assetId: string, body: AssetContentAccept): Promise<AssetOut>`；定义在现有data/api/client.ts并同步该模块api/contracts.ts。内容接纳201后只通过明确set_data更新选中节点；固定素材组显式发布／项目选择沿现有方法，不扩大到其他引用。

<a id="python-clients"></a>

### Python具名客户端的实施补全

以下把前述已确定HTTP操作落到现有AssetClient组合模式，补齐此前只给文件、未给方法签名的缺口；没有新增远程路径或业务能力。`src/astrophotoflow/client.py`保留request／_result／ServiceApiError，新增三个mixin分别放`interfaces/client/software.py`（SoftwareOperations）、`nodes.py`（NodeOperations）、`workflows.py`（WorkflowOperations）。新返回模型用既定DTO校验；原有58项方法除明确的移除协议切换外保持返回行为，不整体改成新客户端体系。

根AssetClient直接增加①网页配置的两个在线方法；离线启停仍调用core，不能先构造AssetClient。数据增量放已有LibraryOperations：

```python
def get_workbench_configuration(self) -> ConfigState: ...
def save_workbench_configuration(self, body: ConfigSave) -> ConfigState: ...

def observe_asset_content(self, asset_id: str) -> AssetContentObservation: ...
def accept_asset_content(self, asset_id: str, body: AssetContentAccept) -> AssetOut: ...
def preview_library_removal(self, body: LibraryEntriesRemove) -> LibraryRemovalPreview: ...
def remove_library_items(self, body: LibraryRemovalApply) -> dict[str, Any]: ...
```

前两项对应GET／PATCH settings/workbench；观察／接纳对应既定content-observation／content-accept；preview对应removal-preview；remove继续唯一DELETE，不自动先查后确认。用户已确认后两项在B57与精简MCP定义一次切换；切换前保留既有移除正文，B54只交内部影响查询／测试，不提前宣称新公共场景可用。Any只沿现有客户端返回注解，不进入新DTO。

```python
class SoftwareOperations:
    def list_software_packages(self) -> list[SoftwarePackage]: ...
    def list_software_commands(self, package_id: str, version: str) -> list[SirilCommand]: ...
    def get_software_package(self, package_id: str, *, operation_id: UUID | None = None) -> SoftwarePackageDetails: ...
    def install_software(self, package_id: str, body: SoftwareInstallRequest) -> PendingSoftwareAction: ...
    def prepare_software(self, package_id: str) -> SoftwarePreparation: ...
    def preview_software_update(self, package_id: str, target_version: str) -> PackageUpdatePreviewResult: ...
    def update_software(self, package_id: str, body: SoftwareUpdateRequest) -> PendingSoftwareAction: ...
    def uninstall_software(self, package_id: str, body: SoftwareUninstallRequest) -> PendingSoftwareAction: ...

class NodeOperations:
    def list_nodes(self) -> list[NodeDetails]: ...
    def get_node(self, definition_id: UUID) -> NodeDetails: ...
    def create_node(self, definition: NodeDefinition, operation_version: str) -> NodeDetails: ...
    def preview_node_update(self, definition: NodeDefinition, operation_version: str, expected_content_token: str) -> NodeUpdatePreviewResult: ...
    def update_node(self, definition: NodeDefinition, operation_version: str, expected_content_token: str, impact_token: str) -> NodeUpdateResult: ...
    def test_node(self, body: NodeTestCreate) -> RunDetail: ...
```

软件方法逐项使用第13节同名动作／请求DTO。节点方法按definition.definition_id构造路径，正文仍为既定definition／operation_version／token字段；test从body.definition_id取路径，不能再接一份可矛盾的ID。SoftwareOperations／NodeOperations不调用彼此或本机软件，只使用self.request后校验响应。WorkflowOperations完整公开面仍见[第16节](#mcp-design)，另含以下已要求的来源回查：

```python
def find_saved_output(self, asset_version_id: UUID) -> OutputLocator | None: ...
```

它对应既定GET /runs/outputs/by-asset-version/{asset_version_id}。所有业务冲突保留ServiceApiError原code／fields／request_id，无自动重试；read_run_preview沿已有read_display_preview的JPEG检查及bytes返回方式，不为新客户端复制错误处理框架。各方法随真实HTTP消费者落位：B13配置，B23内容接纳，B31／B32／B55软件，B42／B53／B55节点，B51～B57工作流，移除按确认后的任务归属；不提前注册空路由。

<a id="foundation-design"></a>

## 11. ①公开配置和本机控制

### 配置与公开接口

配置定位沿现有入口明确为：显式config参数→ASTROPHOTOFLOW_CONFIG→用户CONFIG_PATH中`[workspace] default`所指目录下的config.toml。用户默认TOML只保存这一定位，各workspace原有config.toml继续保存server/storage/comfyui/imports/ingestion；不再读active-workspace或另建登记表。Settings.workspace为所选workspace配置的父目录，不能从data_dir猜测。相对storage.data_dir仍按所属配置目录解析，不搬数据。默认未设且无显式目标时明确要求初始化／选择，不静默创建另一套workspace。

Settings保留现有位置参数次序，新增必填keyword-only的workspace（dataclasses.field(kw_only=True)，无默认／推断）；完整构造形态为`Settings(host: str, port: int, data_dir: Path, allowed_origins: tuple[str, ...], import_roots: tuple[ImportRoot, ...] = (), file_workers: int = 2, preview_workers: int = 1, *, workspace: Path)`。load_settings明确传选定配置父目录；所有显式构造点包括测试、`scripts/export_openapi.py`及`scripts/verify_distribution.py`内嵌验证脚本都传独立测试workspace，不为兼容旧构造器猜data_dir父目录。

M1已实现下列Python配置与本机控制签名；后续业务章节的拟实现能力仍按各自批次推进：

```python
def get_configuration(config_path: Path | None = None) -> ConfigState: ...
def save_configuration(config_path: Path, values: ConfigValues, config_token: str, *, default_workspace: Path | None = None) -> ConfigState: ...
def load_running_settings(workspace: Path) -> Settings: ...

def start(workspace_config: Path | None = None) -> WorkbenchResult: ...
def status(workspace_config: Path | None = None) -> WorkbenchState: ...
def stop(workspace_config: Path | None = None) -> WorkbenchResult: ...
def restart(workspace_config: Path | None = None) -> WorkbenchResult: ...
```

CLI格式化结构化结果，本机MCP定向控制不写默认位置或旧active指针。配置读取无副作用，保存只替换可编辑字段及token、不重启；旧token冲突409，无效字段422，依赖不可用503，本机控制沿WorkbenchError报告，不能伪造HTTP回执。

1. 固定本次config/workspace及采用值，核对进程身份和双服务健康后复用；确需启动时为占用端口选其他可用端口，实际绑定／健康后才报ready。
2. 扩展 `workspace/run/processes.json` 保存config_path/workspace/effective_settings/web_url/service_url/processes；进程身份字段见下表。当前或最近控制结果写 `workspace/run/control.json`，只保留一次。复用完整写入／互斥，不能把数据库锁当启停锁。
3. ASTROPHOTOFLOW_CONFIG标记来源，APF_WORKSPACE固定目标。启动器先写采用值；服务和引擎经load_running_settings读取同份值，HTTP CLI交给create_app，网关／适配及在线AssetClient沿实际运行地址连接，不每请求重读新保存端口。
4. 就绪后仅将实际端口／允许Origin写回源配置，不覆盖并发保存的其他项。回写失败报告已在线及未写回原因，不再启动。性能设置下次成功重启采用；改默认位置不改已有进程归属。
5. 网页GET/PATCH /api/v1/settings/workbench固定当前在线目标，PATCH带config_token；本机start/status/stop/restart不依赖HTTP在线。
6. 本机控制器以Bearer调用 `POST /internal/maintenance`（action=enter/release，operation_id复用本次WorkbenchResult标识，不进MCP目录）。app组合②导入／预览、③安装／使用、⑤准备／运行及原生队列，空闲检查至维护期间拒绝冲突准入；busy或unknown拒绝并释放本次准入，不安排自动重启。enter回执丢失仍按同一operation_id释放，迟到释放不能清除另一操作的维护；释放未确认如实报告。stop沿原排空，包括ComfyUI尚未登记时已经启动的领域服务。领域离线而引擎／进程仍在时不能假定空闲；身份核对均已停止时启动不需调用离线HTTP。

M1实现将当前维护operation_id（可空）合入既有processes.json；进程登记与维护更新共用短文件锁，不另建维护实体。原生桥接为/prompt与/api/prompt受理、/queue与/api/queue观察使用同一短期互斥：先关闭本次准入，再观察已受理的验证／入队，避免空队列检查后又接入新运行。仍调用原生队列，不增加调度器或托管执行上下文；后者归B53。该门禁在既有register_proxy_routes接入，不修改固定引擎归档。

### 配置结果字段

远程路径为str，内部Settings用Path；时间为UTC。配置字段验证复用core/config.py。
| 类型 | 字段与约束 |
|---|---|
| `ImportRootValue` | `id: str`、`path: str`；沿现有授权根目录规则 |
| `ConfigValues` | `host: str`、`service_port: int`、`data_dir: str`、`allowed_origins: list[str]`、`import_roots: list[ImportRootValue]`、`file_workers: int`、`preview_workers: int`；后两项正整数，host本机回环，port及origin沿当前验证。网页端口仍由allowed_origins首项表达，不再加一份可独立矛盾的端口字段 |
| `ConfigSave` | `config_token: str`、`values: ConfigValues`、`default_workspace: str \| None = None`；values是完整可编辑启动配置。默认位置仅显式提供非空路径时修改，省略保持、显式null拒绝；不删除资源或搬运数据 |
| `ConfigState` | `config_path: str`、`default_workspace: str \| None`、`saved: ConfigValues`、`config_token: str`、`effective: ConfigValues \| None`、`restart_required: bool`；token覆盖当前workspace配置及所显示默认定位，restart_required只比较启动参数，改默认不要求重启当前实例 |
| `ProcessInfo` | `role: Literal['asset-service','comfyui']`、`pid: int`、`create_time: float`、`executable: str`、`command: list[str]`、`workspace: str`、`started_at: datetime`；沿现有身份核对，不能只检查PID |
| `BusyState` | `busy: bool`、`unknown: bool`、`blockers: list[str]`；unknown时不能当空闲，不为阻塞项另建资源对象 |
| `WorkbenchResult` | `operation_id: UUID`、`action: Literal['initialize','start','stop','restart']`、`state: Literal['in_progress','completed','rejected','failed','unknown']`、`workspace: str`、`config_path: str`、`reused: bool`、`web_url: str \| None`、`service_url: str \| None`、`detail: str \| None`、`blockers: list[str]`、`log_path: str \| None`；地址存在也要结合state/ready，不伪报成功 |
| `WorkbenchState` | `workspace: str`、`config_path: str`、`state: Literal['stopped','starting','stopping','running','partial','unknown']`、`ready: bool`、`web_url: str \| None`、`service_url: str \| None`、`processes: list[ProcessInfo]`、`effective_settings: ConfigValues \| None`、`versions: dict[str,str]`、`reason: str \| None`、`recent: WorkbenchResult \| None` |

ConfigValues只映射workspace原有TOML启动字段，默认定位单独表达；有效值来自进程采用信息。保存涉及两个配置文件时不承诺跨文件事务，失败说明实际已保存部分并重读，不自动回滚或重启。config_token只服务当前保存，不积累历史。初始化保留原入口：

```python
def initialize(workspace: Path, service_port: int = 8190, comfyui_port: int = 8188, *, frontend_assets: Path | None = None, activate: bool = True, reuse_runtime: bool = False) -> Path: ...
```

initialize返回实际config路径；activate表示本次初始化是否把位置设为config默认，沿既有--no-activate选择，不写旧active指针。M1候选已实现本节配置函数／类型、启动采用、启停互斥及结构化控制；start只控制目标，没有activate或--no-activate。Windows打开的读句柄会阻止原子替换，已针对实测WinError 5进行最多5次、每次50ms的有限等待并记录警告；持续失败保留旧文件且明确报错，不重做业务或启动。用户批准及MCP控制不由这些测试代签。

各模块经公开查询供app组合维护，core不扫描业务表：

```python
def data_busy(database: Database) -> BusyState: ...
def workflows_busy(database: Database) -> BusyState: ...
```

分别由data/public.py和workflows/public.py提供导入／生成与准备／排队／运行／未知事实；app再结合software.get_usage、当前软件动作及原生queue观察。

<a id="data-design"></a>

## 12. ②科学引用、内容接纳与所选结果

### 科学交接类型

实现落点见第10节；所有新增DTO遵循共同类型规则，判别联合沿既有contracts/datasets.py模式。

### 引用与选择：可以持久保存在原生图中，不含实际路径

| 类型 | 精确字段与条件 |
|---|---|
| `InputMode` | `Literal["reproducible", "reference"]`。未提供使用 `reproducible`；准备失败不改模式。 |
| `ScienceSelection` | `kind: Literal["whole_file", "fits_hdu"]`；`hdu_index: int \| None = None`。`fits_hdu` 必须给非负 HDU 索引；`whole_file` 不带 HDU 索引。首批不声明支持任意 cube／slice／视频帧区间；尚未接入的选择返回 `UNSUPPORTED_SELECTION`，原始视频选择完整文件仍须③操作真实支持。以后确有受支持切片时扩展同一选择模型，不先放任意表达式或虚构帧资产。 |
| `AssetInputReference` | `kind: Literal["asset_version"]`；`asset_version_id: UuidInput`；`selection: ScienceSelection`。使用固定版本，不取 `Asset.current_version_id` 代替请求。 |
| `DatasetInputMember` | `member_index: int`（非负，指当前所选 `DatasetVersion` 的原始 `DatasetMember.position`）；`asset_version_id: UuidInput`；`selection: ScienceSelection`。两项身份须与同一个固定成员匹配。 |
| `DatasetInputReference` | `kind: Literal["dataset_version"]`；`dataset_version_id: UuidInput`；`members: list[DatasetInputMember]`（至少一项，同版本内成员不重复）。全组选择传该固定版本的全部成员；子集传明确所选成员。不以当前搜索结果或集合最新版本重建成员。客户端可从现有 `DatasetVersionOut.members` 形成该列表，不增加新选择资源。 |
| `InputReference` | `Annotated[AssetInputReference \| DatasetInputReference, Field(discriminator="kind")]`。 |
| `ResolveInputsRequest` | `project_id: UuidInput`；`references: list[InputReference]`（至少一项）；`input_mode: InputMode = "reproducible"`。本次调用来自⑤已经保存的图／绑定解析，MCP 不另传一份游离输入。 |
| `OutputLocator` | `kind: Literal["run_output"]`；`run_id: UuidInput`；`node_execution_id: str`；`output_index: int`（非负）；`member_index: int \| None = None`。`node_execution_id` 是本次固定执行图内的原生执行节点定位（包括实际子图定位），不能用另一图的显示节点名。`member_index` 仅集合输出存在，指实际输出manifest成员，标量输出必须为null。 |
| `ScientificValue` | `Annotated[AssetInputReference \| DatasetInputReference \| OutputLocator, Field(discriminator="kind")]`。原生科学单文件端口传一个该值；集合端口传 `list[ScientificValue]` 并保序。定义只包含可核对的轻量定位；不传科学数组、预览tensor、任意path或整个文件字节。 |

`references` 的外层顺序即端口绑定顺序；每个组按固定 `DatasetMember.position` 展开，保留原位置，子集不重新编号。不禁止不同端口显式引用同一文件；不通过全局去重改变用户请求。单个资产遵守现有共享／所属项目范围；组及其每个成员也须处于当前项目可用范围。项目关联和数据权限不是因为复制一条图或知道路径就自动获得。

`ScientificValue` 是统一的原生科学端口值约定，不另设 NativeScientificValue 别名。⑤在实际节点调用前解析它：固定资产／组从本次准入时已经固定的RunContext.inputs取ResolvedAssetInput，只复核可读／完整内容，不重读当前资料、不重复物化；只有同run新上游locator须属于当前run，来源节点／输出／成员与该run已保存执行图的实际入边和④执行绑定一致，并可定位到实际完成的科学输出manifest，才转换为内部 `ResolvedOutputInput`。上游轻量值本身不携带授权，不能指向任意节点／文件；S6跨run续跑仍须使用已保存、可读的固定科学素材，而不是任意历史run locator。该校验和manifest解析归⑤，②不读取⑤ORM。普通IMAGE／显示tensor不自动转为科学原件；未桥接类型按支持范围拒绝。scalar端口实际连线采用值由⑤依固定图和绑定解析并记录，再交③的软件参数DTO。

受支持操作若使用序列文件，科学端口的有序值及实际manifest须同时包含该序列所需关联帧；仅可读的索引文件不证明科学输入完整。首个操作的真实文件组合须锁定并验证，缺关联文件明确阻塞，不自行拆帧或建立新帧资产模型。

### 内部解析结果：只在同进程业务和受控引擎交接使用

| 类型 | 精确字段与条件 |
|---|---|
| 两种解析输入的共同文件字段 | `read_path: Path`；`format: ScienceFormat`；`selection: ScienceSelection`；`byte_size: int`（非负）；`content_hash: str`；`mtime_ns: int`；`scientific_metadata: dict[str, JsonValue] \| None`。字节和科学选择均来自实际核对的完整文件。下述两种variant共用这些字段，但不为此增加单独存储实体。 |
| `ResolvedAssetInput` | `kind: Literal["asset_version"]`及上述共同字段；另含 `reference_index: int`、`asset_id: UUID`、`asset_version_id: UUID`、`dataset_version_id: UUID \| None`、`member_index: int \| None`（后二者仅组成员同时有值）；`asset_revision: int`（至少1）；`parameters: AssetParameters`；`classification: AssetClassification \| None`；`value_sources: dict[str, Literal["manual", "file", "preset", "unknown"]]`；`capture_snapshot: dict[str, JsonValue] \| None`；`equipment_snapshot: dict[str, JsonValue]`；`effective_calibration: CalibrationBindings`；`preparation: Literal["existing_managed", "materialized", "reference"]`。②只生成此variant，不制造未知值、资料默认或预览推断。 |
| `ResolvedOutputInput` | `kind: Literal["run_output"]`及上述共同字段；另含 `locator: OutputLocator`。由⑤核对当前run／固定连线／实际科学manifest后生成；完整输出文件的选择为manifest声明的完整文件，不猜默认HDU。没有asset_id、asset_version_id、asset_revision、接收设备快照或当前资产资料；不为尚未入库的上游产物伪造资产身份。 |
| `ResolvedInput` | `Annotated[ResolvedAssetInput \| ResolvedOutputInput, Field(discriminator="kind")]`。③输入唯一使用此联合，不平行定义另一份科学文件Schema。 |
| `ResolvedInputs` | `input_mode: InputMode`；`items: list[ResolvedInput]`（实际完整展开顺序）；`required_copy_bytes: int`；`copied_bytes: int`。② `resolve_inputs` 返回的items只含真实 `ResolvedAssetInput`；⑤可把已核对上游产物解析为 `ResolvedOutputInput` 并按固定端口顺序形成③所需 `dict[str, list[ResolvedInput]]`。成本只计本次确需固定的注册输入，已固定托管原件及同run科学输出不算再次复制。实际采用值写入同次运行，不另建可编辑输入库。 |
| `ReferenceObservation` | `input_index: int`（`ResolvedInputs.items` 中位置）；`observed_at: datetime`（UTC）；`state: Literal["unchanged", "changed", "missing", "unverified"]`；`byte_size: int \| None`；`mtime_ns: int \| None`；`content_hash: str \| None`；`error: ErrorDetail \| None`。`unchanged` 表示结束观察与该次采用的前置观察相符，不声称证明整个运行期间始终不变。缺失／无法完整读取明确给原因，不能填零或替换路径。 |

当前资料来自 `Asset.parameters`／`classification`／`value_sources` 和 `Asset.revision`，不是从设备库重建旧接收信息；`AssetVersion.capture_snapshot` 独立保留（`models.py:107–113, 141`）。内容散列沿现有 `blake3:<hex>` 表达（`ingestion.py:189–212`），不引入第二散列体系。文件布局／dtype／单位／WCS等读取结果保留在实际格式资料中；本次不重新定义通用科学数组或强制转换协议。

`effective_calibration` 使用既有 `CalibrationBindings`：组默认先确定，再按该固定成员覆盖；缺键继承、null不使用、显式目标引用固定 `asset_version`／`dataset_version`，不做自动匹配。某个已选③操作真正采用校准时，⑤把采用的固定目标以同一 `InputReference`／`resolve_inputs` 机制解析成明确文件交③，并记录实际采用关联；关联存在不等于已经执行校准，不递归猜测软件需要哪些处理。

HTTP／MCP 输出只能显式选择身份、科学选择、实际资料、检查／准备摘要，不序列化 `ResolvedInput.read_path`，也不能把内部模型 `model_dump()` 直接作为远程结果。③只接收受控执行所需的完整文件交接。

### 已检查输出与现有导入的连接

| 类型 | 精确字段与条件 |
|---|---|
| `ScienceFormat` | `Literal["fits", "xisf", "image", "raw", "video", "numpy", "other"]`。前六项沿用现有格式分类；`other` 仅用于③受支持操作已产生且可读的完整输出，不能据此宣称具有解析／预览或科学执行支持。 |
| `CheckedOutput` | 内部模型：`run_directory: Path`；`path: Path`；`format: ScienceFormat`；`byte_size: int`；`content_hash: str`；`checked_at: datetime`（UTC）；`scientific_metadata: dict[str, JsonValue] \| None`。路径必须是⑤已记录的该运行科学输出之一，落在该受控运行工作范围，且在检查时完整可读。UI预览、任意客户端path和无法定位到本次实际输出的文件不能产生此交接。类型名／客户端声称“checked”不提供信任；实际服务检查仍执行。 |
| `OutputRegistration` | `task_id: UUID`；`created: bool`；`task_status: Literal["queued", "running", "cancelling", "completed", "completed_with_errors", "failed", "cancelled", "interrupted"]`；`asset_id: UUID \| None`；`asset_version_id: UUID \| None`；`content_status: Literal["pending", "available", "failed"]`；`metadata_status: Literal["pending", "available", "unsupported", "failed"]`；`preview_status: Literal["pending", "available", "unsupported", "failed"]`；`error: ErrorDetail \| None`。asset／version只有已登记时有值，完整内容 `available` 才可报告已保存；预览／解析失败另报，不把可读完整素材冒充未保存。`created` 只说明本次是否新建现有导入任务，供装配决定是否启动它，不作授权／永久回执。 |

运行／节点／输出／成员定位由⑤拥有；外部保存请求只传这些定位和可选 `name`，不接受 `CheckedOutput`／path／任意URL。⑤核对定位并检查后，先在同次运行输出关联中固定一个 `task_id`，再调用②。此关联保存来源事实；不向②新增来源表或让②读取⑤表。

### ②公开函数与副作用

以下均由 `modules/data/public.py` 显式导出；实现分别位于第10节所列文件。Database／Settings沿core，CfaPattern沿contracts/common.py，项目／资料／移除和科学类型引用其唯一契约。
### 项目关联所需的现有公开读取

```python
def get_project(database: Database, project_id: UUID) -> ProjectOut: ...
```

在已有projects.py内窄提取：read_session按UUID读取Project并返回既有ProjectOut；不存在404 RESOURCE_NOT_FOUND，归档按当前行为返回，不新增active限制。无创建、revision或文件副作用，既有GET /projects/{project_id}窄委托，响应不变。⑤首次创建／导入／关联图经此核对真实project_id，不调用data路由、导入ORM或仅查UUID格式；认证仍由实际业务入口承担。
### 科学输入与结束观察

```python
def validate_input_references(database: Database, project_id: UUID, references: Sequence[InputReference]) -> None: ...

def resolve_inputs( database: Database, settings: Settings, request: ResolveInputsRequest, *, run_directory: Path, ) -> ResolvedInputs: ...

def observe_reference_inputs( settings: Settings, inputs: ResolvedInputs, ) -> list[ReferenceObservation]: ...

def check_output( settings: Settings, *, run_directory: Path, path: Path, expected_format: ScienceFormat, ) -> CheckedOutput: ...
```

- validate_input_references是编辑期必要的②公开只读交接，由science_inputs.py实现、public.py导出。⑤add_data/set_data在改图前调用：一个短read_session核对项目、所选固定资产／集合及每个成员的身份、项目可用范围、原成员position和选择结构，复用现data/common.py的范围规则；失败沿404／INVALID_REFERENCE／UNSUPPORTED_SELECTION。它不散列、复制、读预览、创建运行目录、改当前指针或承诺原件可读；实际运行仍由resolve_inputs完整核对。两处真实消费者只提取必要共用范围逻辑，不让⑤导入②私有函数或ORM，不增加HTTP／MCP工具。
- ①／⑤明确传入 `workspace/runs/{run_id}/work`；②不猜路径、不新增远程文件读取API。resolve_inputs短读冻结固定版本、当前资料revision、顺序及校准后关闭会话，再散列／复制；不创建版本或修改项目选择。
- reproducible直接使用已验证托管字节(existing_managed)；reference原件需固定时在run_directory/inputs流式复制(materialized)，按接受hash及读取前后观察核对，临时part完整后归位。准备失败不发布、不降级，只清本次未发布part。
- 显式reference保持所选原件、完整核对并记录前置观察；执行结束由⑤调用observe_reference_inputs，仅观察kind=asset_version且preparation=reference的项。missing／unverified及错误作为后置事实返回，不改AssetVersion、不重跑；执行前已缺失／变化待确认则阻塞。
- 科学选择只验证已支持whole_file／fits_hdu，不用显示默认HDU或视频首帧代替。check_output按⑤已核对的manifest检查运行范围、完整可读性及格式，返回字节／hash／资料，不改文件、不登记或生成预览；path本身不证明运行归属。
- 文件工作沿既有后台执行，HTTP先返同次运行／保存准备状态；不阻塞事件循环。返回实际准备成本和可确定失败字节，不编百分比／ETA。
### 纯文件预览

```python
def render_output_preview(checked: CheckedOutput, destination: Path, *, selection: ScienceSelection | None = None, max_edge: int, cfa_pattern: CfaPattern | None = None) -> None: ...
```

同science_inputs.py实现、data.public导出，只读checked.path并向⑤指定位置写JPEG，无Database／asset身份／Preview行；不调用素材预览HTTP或先登记产物。⑤核对destination归属，第14节规定唯一文件位置；②拒绝与科学源同路径。max_edge为⑤给出的正整数，发布沿既有临时文件完整替换，失败只清本次临时文件。
显示算法复用[现有FITS预览](../../../../src/astrophotoflow/modules/data/fits_preview.py)及[导入预览helper](../../../../src/astrophotoflow/modules/data/ingestion.py)，不复制算法或新增版本：显式fits_hdu采用指定HDU；省略selection／whole_file沿inspect_fits.selected_hdu显示默认。默认不可用或布局未支持返回PREVIEW_UNSUPPORTED，不另猜HDU，且不改run的科学选择。常规图像、XISF、RAW沿既有whole-file支持范围；视频沿[静态首帧](../../../../src/astrophotoflow/modules/data/video_preview.py)，不证明整段可处理；NumPy／other及未接入布局不猜测回退。
支持组合渲染失败为PREVIEW_FAILED，可确定缺RAW／XISF／FFmpeg依赖为PREVIEW_DEPENDENCY_UNAVAILABLE。公开函数固定返回None，PIL／NumPy及私有helper差异留②内部。⑤在文件存在后更新预览索引；显示失败与完整科学结果可用性分开，不重跑／扩分支或自动登记。验收覆盖省略selection、显式HDU、不支持布局及科学字节／run科学选择不变，统一见第17节。
### 确认外部内容变化：同素材新增内部版本

在既有 `contracts/assets.py` 定义两个DTO并复用AssetOut／AssetVersionOut；仍用16个ORM模型，无内容变更任务／审批表。
| 类型 | 最少精确字段及条件 |
|---|---|
| `AssetContentObservation` | `asset_id: UUID`；`base_version_id: UUID`；`base_revision: int`；`storage_mode: Literal["reference", "managed"]`；`stored_hash: str`；`state: Literal["unchanged", "changed", "missing", "unsupported"]`；`observed_hash: str \| None`；`observed_byte_size: int \| None`；`observed_mtime_ns: int \| None`；`error: ErrorDetail \| None`。state为unchanged／changed时已接受的stored_hash和本次观察值均完整，error为null；missing时不伪造hash／大小并给SOURCE_UNAVAILABLE，unsupported给UNSUPPORTED_FORMAT原因。hash沿用 `blake3:<hex>`，不返回内部path。base_version_id／base_revision指观察开始时确定的当前版本和资料revision，不是内容修订历史编号。 |
| `AssetContentAccept` | `base_version_id: UuidInput`；`base_revision: int`（至少1）；`expected_observed_hash: str`（完整 `blake3:<hex>`）。这三个值来自用户实际确认的同一次观察；不接收任意path、storage_mode、覆盖旧版本选项或 `confirmed:true`。 |

```python
def observe_asset_content( database: Database, settings: Settings, asset_id: UUID, ) -> AssetContentObservation: ...

def accept_asset_content( database: Database, settings: Settings, asset_id: UUID, body: AssetContentAccept, ) -> AssetOut: ...
```

两函数由science_inputs.py实现、data.public导出；沿共享素材认证／范围。HTTP为 `POST /api/v1/library/assets/{asset_id}/content-observation`→200观察，`/content-accept`→201 AssetOut(current_version为新版本)；越界／不存在404，不接收path。

1. 观察短读确定当前version／revision、已接受hash和实际storage_location，关闭会话后流式核对字节／hash及读取前后稳定性。managed只查实际副本，不追原导入来源；读取中变化409 SOURCE_CHANGED，不自动再读。可短事务更新该版本availability=available/changed/missing；不改hash／大小／科学资料或Asset当前资料，unsupported不是新availability。
2. 接纳重核base_version_id／base_revision及expected_observed_hash，仅接纳已明确确认的changed内容。原内容未完成／无接受hash／仍在导入发布时SOURCE_UNAVAILABLE／IMPORT_ACTIVE；unchanged接纳422 VALIDATION_ERROR。再变409 SOURCE_CHANGED，丢失422 SOURCE_UNAVAILABLE，不支持422 UNSUPPORTED_FORMAT，均不自动重试；长读／复制在事务外。
3. 保持storage_mode：reference沿原授权位置记录新观察；managed在data/staging准备本次部分副本，核对后归位 `data/objects/{new_asset_version_id}/source<实际后缀>`，解析同一固定副本，不覆盖旧对象。临提交源观察再变则失败，只清本次未发布副本。文件与SQLite不是一个事务；201不锁住reference外部字节。
4. 短write_session再核同Asset revision／current_version_id，不符409 REVISION_CONFLICT；通过后插同asset_id的新UUID／下一version_number，写真实hash／大小／位置／新文件观察，更新current_version_id并revision+1。保留人工parameters／classification及其manual来源、equipment_snapshot、名称备注与原导入capture_snapshot，不从改删后的设备库重建。非人工字段仅按现有ingestion._refresh_fits_metadata的规则采纳实际新文件观察，不猜默认或覆盖manual修正；新Header／HDU不回写旧版本，新运行采用修正后的当前资料并记录。
5. 旧版本hash／大小／接收及科学资料不改，只如实更新availability；旧字节不在不承诺恢复。旧run及任何节点／ProjectAssetReference／DatasetMember／DatasetVersion／ProjectDatasetReference不自动推进。指定节点由set_data显式选新版本；固定组需publish新DatasetVersion后按既有引用操作显式选择。
6. 重复原确认因旧revision／base_version_id返回409 REVISION_CONFLICT，不增第二版本、不伪装幂等200；断连先GET Asset／versions核对，不重POST。冲突只清未发布副本，不删已发布版本／原件或其他任务文件。测试统一见V04及AT-05。

### 所选结果登记、查询及既有任务执行

```python
def register_output( database: Database, settings: Settings, *, task_id: UUID, output: CheckedOutput, name: str | None, ) -> OutputRegistration: ...

def get_output_registration( database: Database, settings: Settings, task_id: UUID, ) -> OutputRegistration: ...

def process_task( database: Database, settings: Settings, task_id: str, workers: tuple[ThreadPoolExecutor, ThreadPoolExecutor] | None = None, ) -> None: ...
```

1. ⑤为明确选中的一个完整输出成员固定task_id。②短写中新建／读取原AssetTask；同task_id、受控源身份、接受byte_size／hash和有效名称返回同任务，checked_at不参与意图比较；不同内容／名称冲突。created=False仅查询，不再调度。
2. 新任务为同workspace共享managed素材，不登记其他节点／成员或复制到其他项目。name=None沿现有stem（无stem用文件名），显式值沿check_name；续查不承担改名，已存素材改名沿现有PATCH。
3. 任务保存受控源、接受hash／大小及资料，公开任务不泄漏完整path。仅created=True由装配用现共享files／previews线程池启动原process_task。重启沿mark_interrupted_tasks及显式resume/retry，保留原资产身份／完成阶段。
4. 内容沿现有data/staging/{task_id}及data/objects/{asset_version_id}/source<后缀>完整归位；提交前中断先核对已分配最终文件，不重复建资产。科学源只读并供本次下游使用，⑤保留它到②内容完成或明确失败，托管副本独立长期可读。
5. ingestion.py按扩展名的普通导入门禁不能用于已核对运行输出；未支持解析／预览分别报unsupported，普通上传／授权目录范围保持。沿既有raw／calibration默认，不凭选择保存推断final，不加中间／最终或扩展名保存门禁；来源只由⑤关联。
6. get_output_registration只读该能力建立的真实task／asset和完整内容事实，不复制／改状态／调用软件。解析／预览失败与文件缺失分开；显式补登记沿原任务阶段，源缺失不删成功托管副本、不新建或重跑。
### 普通移除与实际清理的跨模块闭合



| 类型／位置 | 字段 |
|---|---|
| `LibraryRemovalScope` | 保留 `selection: LibraryEntriesRemove`、`asset_version_ids: list[UUID]`、`dataset_version_ids: list[UUID]`、`data_token: str`；补 `asset_ids: list[UUID]`、`dataset_ids: list[UUID]` 供⑤按稳定身份查影响。集合成员是本次原有移除逻辑采用的固定版本范围，不随追加扩展 |
| `LibraryRemovalPreview`，`contracts/workflows.py` | `scope: LibraryRemovalScope`；`workflows: list[WorkflowImpact]`；`removal_fingerprint: str` |
| `LibraryRemovalApply`，同上 | 继承 `LibraryEntriesRemove` 的原items及唯一性校验；新增必填 `data_token: str`、`removal_fingerprint: str`。不加入confirmed／actor／永久删除标志 |

`data_token`绑定数据侧已核对范围；合成fingerprint为scope（包括data_token及原selection）和按workflow_id排序的完整WorkflowImpact JSON的SHA-256，对象键排序、UUID用JSON字符串。图的内容token、节点位置、未同步页面和影响范围均参与；进度／日志不参与。不保存预览对象或审批记录。

实现仍放既有 `modules/data/trash.py`，只由 `data/public.py` 导出；不是从其他模块调用HTTP handler。必要签名如下（这里修订既定草案的拟签名，不声称已有导出）：

```python
def preview_library_removal(database: Database, body: LibraryEntriesRemove) -> LibraryRemovalScope: ...
def remove_library_items(
    database: Database, body: LibraryEntriesRemove, *, expected_data_token: str,
    verify_impact: Callable[[LibraryRemovalScope], None],
) -> LibraryEntriesRemoveOut: ...
```

`remove_library_items`自己进入现有 `Database.write_session()`（BEGIN IMMEDIATE），在写之前重建scope、核对expected_data_token、调用同步verify_impact，再执行原检查和LibraryEntryRemoval写入。verify_impact只核对⑤公开影响，不执行远程HTTP或写图；异常使本次事务无写入。不可先外部核对后另开事务移除。

应用装配闭包（绑定database/settings及当前已确认pages）只暴露这两条具体处理链：

```python
def preview_library_removal_for_client(body: LibraryEntriesRemove) -> LibraryRemovalPreview: ...
def remove_library_items_for_client(body: LibraryRemovalApply) -> LibraryEntriesRemoveOut: ...
```

前者供 `POST /api/v1/library/items/removal-preview` 返回200：②scope→⑤既定 `find_input_usage(database, settings, pages, scope)`→合成fingerprint。后者供扩展DELETE返回200：拆出原selection，verify_impact在数据实际写事务／既定图写准入内读取最新影响并比较fingerprint。图或数据范围改变返回409 `REMOVAL_PREVIEW_STALE`；原revision冲突／404保持。所有读取不改变项目共有数据权限或资产scope。

`interfaces/http/app.py`把两闭包绑定到app.state；两个路由均留在 `data/trash.py`，新preview handler委托preview闭包，现有 `remove_library_entries(body: LibraryRemovalApply, request: Request)`窄委托remove闭包，去掉其原HTTP WriteSession依赖以免嵌套写事务。只注册这条DELETE，不保留绕过校验的旧处理。代理／client／MCP请求模型同步扩展，缺新字段422，不默认跳过。token只防过期；仍核对原认证、shared范围和用户本次普通移除意图，不授予其他删除权。

确认后只移除既定库入口；⑤保留原节点及固定引用，后续显示缺失供重新选择，不删节点、素材文件或旧运行快照。已经实际采用的运行继续；普通移除不因活动读取而升级成永久删除或强制停止。

#### 活动输入与永久清理

`ActiveRunInputUse(StrictModel)`放 `contracts/inputs.py`，仅为⑤只读投影：`run_id: UUID`、`node_execution_id: str | None`、`asset_version_id: UUID | None`、`read_path: Path | None`、`phase: Literal['preparing','active','unknown']`。路径仅内部使用，不放MCP错误；不建Protection／依赖表。

```python
def find_active_input_usage(
    session: Session, asset_version_ids: Sequence[UUID], read_paths: Sequence[Path]
) -> list[ActiveRunInputUse]: ...
ActiveInputUsage = Callable[[Session, Sequence[UUID], Sequence[Path]], list[ActiveRunInputUse]]
```

⑤只读本模块Run.context_json／calls中的实际输入：保护preparing／submitting／queued／running／unknown以及仍有starting／running／unknown软件call的运行，即使顶层run已报错。已固定输入按**实际read_path**与本次要unlink的托管路径精确匹配；已经复制到独立run目录且不再读源的输入不因旧asset身份被永久阻塞。已结束且全部实际调用停止的历史运行不阻塞清理。

准备中的采用范围若已固定，按其版本范围检查；真实准备／未知运行尚无足够JSON能排除本次托管文件使用时，返回phase=unknown并阻塞该次永久清理，不能把空context当空闲。后续范围可知再查询；不新增输入登记／释放API或让长散列／复制持有写事务。候选没有要删的托管科学路径时，不以此guard扩大成外部reference原件删除或永久历史引用保护。

`app.state.active_input_usage`直接绑定该公开函数；data不导入⑤实现／ORM。复用现有session准入：

1. `library_trash_delete_preview`在 `_trash_scope` 得到真实versions／paths后调用callback；非空返回409 `RUN_INPUT_IN_USE`（fields只含run_id／节点及阶段）。原preview_fingerprint格式、校准／导入／预览／共享路径检查保持。
2. `library_trash_delete`在368行初次写事务重建预览时同样检查；**还必须在406行每资产写事务内、现有475-480行检查之后且486-494行unlink之前，用该write Session和当前version_ids／实际paths再调用callback**。不能只在预览时检查。
3. 同一SQLite的BEGIN IMMEDIATE使新run固定输入／call采用记录的写准入不能穿越“最后guard→unlink”。⑤在读取／复制前已有preparing记录；JSON范围未完成时上项unknown检查生效。若清理先标partial，②新科学输入解析必须在其元数据冻结阶段复用现有 `previews.py:87-93` 对LibraryEntryRemoval清理状态的检查，返回409 SOURCE_CLEANUP_ACTIVE而不读该范围；不能假称此新解析guard已经实现。运行先固定使用时cleanup看到真实占用并阻止。Session回调不开第二个连接／事务，不能在data中查⑤表。
4. 沿现有首次冲突409和部分清理failed列表行为报告；此前文件已清理时不伪造整批回滚。原件一旦被活动输入guard拦住就不unlink／删版本；其他现有回收站语义不重写。

这只补现有 `library_trash_delete` 的实际文件／版本清理边界；不引入通用资源锁、租约、恢复治理、长期版本并存或新清理资源。

#### 必要验收（拟新增，未运行）

| 文件／用例 | 预期 |
|---|---|
| ②既有trash测试＋组合路由测试：预览后数据revision／组成员版本或⑤图token变化 | DELETE409，零LibraryEntryRemoval新增；不能拿任意fingerprint越过shared范围／原认证 |
| 同处：确认普通移除，包含active managed输入 | 仅原removed_count／回收站记录变化；原件、当前运行和节点保存，节点后续可显示缺失；不调用永久清理 |
| ⑤运行＋②真实unlink边界：运行JSON引用managed源，原校准／项目／导入保护均为空 | callback仍识别；永久预览或实际清理409 RUN_INPUT_IN_USE，字节和AssetVersion均保留 |
| 同处：预览无占用，unlink前有新运行固定同路径；反向先cleanup占准入 | 同write Session最后guard捕获并阻止删除；清理先占则新输入不能读取已partial／已删文件；不用另建Protection记录 |
| 同处：run顶层失败但软件仍running／unknown；以及真正结束／已独立复制输入 | 前者继续阻止；后者不被历史身份永久阻塞。外部reference原件、现有校准／预览／共享路径回归保持 |

具体测试仍归 `tests/modules/data`、`tests/modules/workflows`及既定接口联调；本页不添加测试代码、迁移或数据操作。

范围精确按原selection的类型解释：asset_version_ids只列本次直接移除资产入口涉及的版本，dataset_version_ids只列直接移除集合入口涉及的固定版本；移除集合不等于移除其成员资产。find_input_usage按这份scope匹配图内固定引用/所选成员，不仅按稳定dataset_id扩大到所有旧版本。Scope中的asset_ids/dataset_ids用于原数据校验与展示，不替代版本范围。永久文件清理另以其实际_scope的versions/paths调用活动输入guard，不从普通移除推断unlink范围。

### 失败码、实际副作用与后续核对

错误沿ApiError／公共envelope，fields使用path/message；后台错误进入原任务项或同次运行，敏感path不外泄。
| code／HTTP | 发生条件与副作用／下一步 |
|---|---|
| `RESOURCE_NOT_FOUND`／404，复用 | 项目、固定版本、组成员或登记task不存在／不在可访问范围；不回落到当前版本或其他项目。远程不可见对象维持现有不泄漏存在性的处理。 |
| `VALIDATION_ERROR`／422，复用 | 必填字段／类型／选择身份不合约、空白显式name；无文件或资产副作用。 |
| `INVALID_REFERENCE`／422，复用 | 固定组版本与member_index／asset_version_id不对应，或实际校准目标类型不匹配；不猜另一版本。 |
| `SOURCE_UNAVAILABLE`／422，沿用现有内容失败code | 输入原件缺失／不可读／内容阶段尚未就绪；不使用预览。输出结束观察则返回missing／unverified及同code，不抹去真实执行事实。 |
| `SOURCE_CHANGED`／409，沿用现有导入code | 采用前散列／读取前后观察与接受内容不符；准备副本不发布、执行阻止。新内容接纳按C1b再次核对expected_observed_hash，不能暗改原AssetVersion或在变化期间自动accept／retry。 |
| `UNSUPPORTED_SELECTION`／422，新增 | HDU／slice／整段视频选择未获当前实际软件及格式组合支持；不替换默认HDU、首帧或裁剪范围。 |
| `UNSUPPORTED_FORMAT`／422，复用 | 本次科学操作明确不支持输入／要求的产物格式；保留原引用／JSON。它不用于按扩展名拒绝已核对完整结果入库。 |
| `INPUT_PREPARATION_FAILED`／422，新增 | 空间不足、复制／散列失败或无法完成固定内容；附可确定的准备成本，删除本次未发布part，不降级reference，不删除已发布素材或别的run文件。 |
| `FILE_SCOPE_INVALID`／409，复用 | 新结果path不在实际run允许工作范围、托管定位越界或完整输出定位不符；拒绝读／保存／删除，不信客户端path。 |
| `OUTPUT_UNAVAILABLE`／422，新增 | 选中科学输出已缺失／不完整／发生变化，或只有preview；不新建登记任务。已有任务则查询其已发生内容／登记，不能因源文件消失删除成功托管副本。 |
| `OUTPUT_SAVE_CONFLICT`／409，新增 | 相同task_id关联不同checked bytes／输出定位／有效名称；不覆盖原任务。第五模块先核对其run输出关联。 |
| `PREVIEW_UNSUPPORTED`／422，新增 | 当前文件renderer不支持该格式／布局／科学选择；没有JPEG成功结果，⑤标preview=unsupported，科学输出可用性独立。 |
| `PREVIEW_FAILED`／422，沿用已有预览code | 已支持组合的实际解码／显示／JPEG发布失败；不发布部分预览，不自动改HDU／算法／文件或重跑科学节点。 |
| `PREVIEW_DEPENDENCY_UNAVAILABLE`／503，新增 | 可确定缺少当前RAW／XISF／FFmpeg显示依赖；返回具体原因，预览仍不可用，不把科学输出改成失败。 |
| `REVISION_CONFLICT`／409、`TRASH_PREVIEW_STALE`／409，复用 | 数据资料／移除范围或确认影响已变化；不提交旧范围，重新查询。⑤图变化使用同一冲突HTTP但保留自身明确code／原因。 |
| `CALIBRATION_IN_USE`／409、`IMPORT_ACTIVE`／409等，复用 | 现有永久清理／活动任务保护仍阻塞；新确认不绕过。 |
| `INTERNAL_ERROR`／500，复用 | 未预期故障保留request_id和脱敏日志，不造成功或自动换路径／工具。客户端断连没有服务错误回执，⑤显示unknown并查询原run/task。 |

不同task_id不自动防重，⑤须先固定输出→任务关联；②不反向读⑤表补授权或去重。
<a id="software-design"></a>
<a id="nodes-design"></a>

## 13. ③软件与④节点的文件和公开面

### 文件与保存位置

B31已实现Siril固定清单、只读`state.json`与一份配套JSON读取，B41已实现workspace定义JSON读写；文件落点见第10节。③清单由项目维护，不接URL／脚本／shell／Python路径；首软件固定为Siril 1.4.4 CLI。当前状态放 `workspace/software/{package_id}/state.json`，专用软件在同目录app/；只保留当前版本位置与最近结果，无长期多版本目录。④唯一当前定义为 `workspace/nodes/{definition_id}.json`，不建SQLite定义表或历史副本。
白名单引导与实际加载统一见第15节；当前原生注册／白名单能力不证明平台动态定义已实现。

### 身份、校验及错误
- `package_id: str` 是项目清单稳定 ID；`operation_id: str` 在包内唯一；`definition_id: UUID` 是库定义身份，与原生图中节点实例 ID 分开。
- `PendingSoftwareAction.operation_id: UUID` 是本次待确认动作的唯一关联，与上项软件处理操作的 `operation_id: str` 分别属于两个 DTO；不增加 `action_id/plan_token` 别名。这个 UUID 是查询／关联值，不能当确认权限。
- `node_execution_id: str` 是原生执行路径，TS 对应 `frontend/src/types/nodeIdentification.ts` 的 `NodeExecutionId`；不得拿库定义 ID、显示名称或普通子图局部 ID 代替。
- `content_token: str` 是当前定义或操作内容的 SHA-256。定义按完整模型的 JSON 值排序对象键、保持数组次序，以 UTF-8 紧凑序列化计算；不计读取时的加载状态／最近测试。它不形成版本库。
public在副作用前沿ApiError失败；已开始的软件调用失败／失联须保留运行观察。impact_token绑定包／定义及图内容，不授予确认；真实网页确认和运行准入由app核对。

| 情况 | HTTP / code | 副作用约束 |
|---|---|---|
| 包／操作／定义不存在 | 404 `RESOURCE_NOT_FOUND` | 不安装、不写文件、不运行 |
| 读取后包版本或定义内容改变 | 409 `SOFTWARE_CONTENT_CONFLICT` / `NODE_CONTENT_CONFLICT` | 返回当前冲突原因；不猜最新内容继续 |
| 定义／加载替换被已固定内容的准备、排队、执行或未知运行引用 | 409 `NODE_BUSY` | 不替换、不安排自动延迟加载；先查询或等待，用户再发起更新 |
| 包正在维护或仍被真实／未知调用占用 | 409 `SOFTWARE_BUSY` | 不安排延迟更新，不释放未知占用 |
| 更新影响改变 | 409 `UPDATE_IMPACT_CHANGED` | 重新读取预览及确认；不覆盖新草稿 |
| 当前待确认动作已被替换、计划过期或服务重启丢失 | 409 `SOFTWARE_ACTION_EXPIRED` | 不启动任何安装／更新／卸载，重新查询实际状态并请求新计划 |
| 字段、绑定、参数或选择不符合实际定义 | 422 `VALIDATION_ERROR` / `INVALID_NODE_BINDING` / `UNSUPPORTED_SOFTWARE_INPUT` | 不强制转换、不改用预览或另一操作 |
| 未安装、许可未就绪、引擎／桥接不可用 | 503 `SOFTWARE_NOT_READY` / `NATIVE_BRIDGE_UNAVAILABLE` | 保留具体原因；不自动安装、登录或重启 |
| 尚未实现的节点类别／特殊控件 | 422 `UNSUPPORTED_NODE_DEFINITION` | 不把 S6 Python／复合内容当软件操作执行 |
| 未预期的文件或内部错误 | 500，沿现有错误处理 | 不报告保存／安装成功，不静默回滚或换默认值 |

非零退出、加载失败、取消未停等由事实字段表达；断连／504先查package或同次run，不自动重投。

### ③完整定义与调用类型
| 类型 | 精确字段 |
|---|---|
| `SirilCommandAssessment` | `parameter_details: str`；`structured_parameter_defaults_ranges: str`；`single_image_sequence_context: str`；`input_output_semantics: str`；`headless_status: str`；`dependencies: str`；`security_risk: str`；`semantic_review_status: str`；`node_definition_status: str`；`node_definition_reason: str`；`node_generation_status: str`；`node_generation_reason: str`；`registry_load_status: str`；`registry_load_reason: str`；`runtime_test_status: str`；`runtime_test_reason: str`；以逐命令评估备注展示未知或未验证项，不等于完整安全／语义审查通过 |
| `SirilCommand` | `command: str`；`scriptable: bool`；`syntax: str`；`description: str`；`url: str`；`assessment: SirilCommandAssessment`；为固定 Siril 1.4.4 官方目录及本地验证状态，不代表对应操作已有可安全表示的节点定义 |
| `ParameterDefinition` | `name: str`；`kind: Literal['int','float','string','boolean','choice']`；`default: JsonValue`；`minimum: float \| None = None`；`maximum: float \| None = None`；`step: float \| None = None`；`choices: list[JsonValue] \| None = None`；`advanced: bool = False`、`nullable: bool = False` |
| `SoftwareInputDefinition` | `name: str`；`type: str`（引擎真实端口类型）；`formats: list[ScienceFormat]`；`cardinality: Literal['one','many']`；`required: bool`；`supports_hdu: bool \| None`；`supports_slice: bool \| None`；尚未验证的选择能力为null |
| `SoftwareOutputDefinition` | `name: str`；`type: str`；`formats: list[ScienceFormat]`；`cardinality: Literal['one','many']` |
| `SoftwareOperation` | `package_id: str`；`version: str`；`operation_id: str`；`name: str`；`description: str`；`syntax: str`；`scriptable: bool`；`inputs: list[SoftwareInputDefinition]`；`outputs: list[SoftwareOutputDefinition]`；`parameters: list[ParameterDefinition]`；`content_token: str`；`ready: bool`；`reason: str \| None`；`cancel_supported: bool \| None` |
| `SoftwarePackage` | `package_id: str`；`name: str`；`available_versions: list[str]`；`installed_version: str \| None`；`install_path: Path \| None`；`package_token: str`；`availability: Literal['not_installed','ready','not_ready','unknown']`；`reason: str \| None`；`operation: Literal['install','prepare','update','uninstall'] \| None`；`operation_state: Literal['idle','running','completed','failed','unknown']`；`phase: str \| None`；`progress: float \| None`；`last_error: ErrorDetail \| None`；`node_definition_ids: list[UUID]` |
| `SoftwarePackageState` | `installed_version: str \| None`；`install_path: Path \| None`；`availability: Literal['not_installed','ready','not_ready','unknown']`；`reason: str \| None`；`operation: Literal['install','prepare','update','uninstall'] \| None`；`operation_state: Literal['idle','running','completed','failed','unknown']`；`phase: str \| None`；`progress: float \| None`；`last_error: ErrorDetail \| None`；`node_definition_ids: list[UUID]`；为`workspace/software/{package_id}/state.json`当前事实，不包含静态软件清单 |
| `SoftwarePreparation` | `package: SoftwarePackage`；`user_action: str \| None`；`ui_kind: Literal['software','platform'] \| None`；`ui_target: str \| None`；不接收或返回密码、验证码、许可证正文 |
| `SoftwareInvocation` | `run_id: UUID`；`node_execution_id: str`；`call_id: UUID`；`package_id: str`；`version: str`；`operation_id: str`；`operation_content_token: str`；`inputs: dict[str, list[ResolvedInput]]`；`parameters: dict[str, JsonValue]`；`work_directory: Path` |
| `ProducedFile` | `path: Path`；`format: ScienceFormat`；只表示③实际返回的完整文件候选，不表示已经通过②检查或登记 |
| `SoftwareObservation` | `run_id: UUID`；`node_execution_id: str`；`call_id: UUID`；`observed_at: datetime`；`active: bool \| None`；`runtime_ref: JsonObject \| None`；`state: Literal['starting','running','completed','failed','cancelled','unknown']`；`phase: str \| None`；`progress: float \| None`；`log_path: Path \| None`；`exit_code: int \| None`；`error: ErrorDetail \| None` |
| `SoftwareResult` | `call_id: UUID`；`state: Literal['completed','failed','cancelled','unknown']`；`started_at: datetime`；`ended_at: datetime \| None`；`exit_code: int \| None`；`outputs: dict[str, list[ProducedFile]]`；`log_path: Path \| None`；`error: ErrorDetail \| None` |
| `SoftwareCancelResult` | `call_id: UUID`；`request_state: Literal['sent','not_supported','not_running','unknown']`；`stop_state: Literal['stopped','running','unknown']`；`observed_at: datetime`；`reason: str \| None` |
| `SoftwareUse` | `call_id: UUID`；`run_id: UUID`；`node_execution_id: str`；`state: Literal['running','unknown']`；只返回当前占用，不保留③占用历史 |
| `PackageChange` | `package_id: str`；`current_version: str \| None`；`target_version: str`；`before_token: str`；`after_token: str`；`operations_before: list[SoftwareOperation]`；`operations_after: list[SoftwareOperation]` |

参数约束仅在适用kind出现（minimum/maximum/step用于数值，choices用于choice，其余null）；nullable来自真实操作，default须符合类型，0不是缺失。首批只封装表列原生控件。输入／输出／参数在各自范围唯一，参数与数据输入不能占同一原生键。
操作version必须准确；格式／选择／停止能力来自实证，近期supports_slice=False，未支持切片沿UNSUPPORTED_SELECTION。操作token只含包／版本／操作身份、说明、端口、参数及已验证停止能力，不含自身或ready/reason；package_token覆盖当前安装身份／版本／位置及操作内容，不含进度／阶段／就绪。progress有依据为0～1，否则null。
ProducedFile只是候选，⑤经②检查成CheckedOutput才交下游；部分产物不报全成功、不自动登记。SoftwareResult.outputs按操作输出名和真实成员顺序；⑤用本次固定④输出数组及execution.outputs映射取得output_index／member_index，不依文件名、当前新定义或preview推断。

### ③必要 public 函数

③配套定义只返JSON，由app按④NodeDefinition.model_validate核对；software契约不导入nodes／workflows，public不反向调用④。
```python
def list_packages(settings: Settings) -> list[SoftwarePackage]: ...
def list_siril_commands() -> list[SirilCommand]: ...
def get_command_catalog(package_id: str, version: str) -> list[SirilCommand]: ...
def get_package(settings: Settings, package_id: str) -> SoftwarePackage: ...
def get_operation( settings: Settings, package_id: str, version: str, operation_id: str ) -> SoftwareOperation: ...
def get_bundled_definitions( settings: Settings, package_id: str, version: str ) -> list[dict[str, JsonValue]]: ...
def preview_update( settings: Settings, package_id: str, target_version: str ) -> PackageChange: ...
def get_usage(package_id: str) -> list[SoftwareUse]: ...

@asynccontextmanager
async def maintain_package(package_id: str) -> AsyncIterator[None]: ...

async def install_package( settings: Settings, package_id: str, version: str, expected_package_token: str ) -> SoftwarePackage: ...
async def prepare_package( settings: Settings, package_id: str ) -> SoftwarePreparation: ...
async def update_package( settings: Settings, package_id: str, target_version: str, expected_package_token: str ) -> SoftwarePackage: ...
async def uninstall_package( settings: Settings, package_id: str, expected_package_token: str ) -> SoftwarePackage: ...

async def invoke_operation( settings: Settings, invocation: SoftwareInvocation, observe: Callable[[SoftwareObservation], Awaitable[None]], ) -> SoftwareResult: ...
async def cancel_operation(call_id: UUID) -> SoftwareCancelResult: ...
```

| 函数 | 参数／返回及副作用 |
|---|---|
| list/get_package | 只读清单、安装及真实就绪，不安装／运行／触发登录；未知百分比为null |
| list_siril_commands | 只读已版本绑定的官方命令说明；Scriptable标记不代表已生成安全节点或通过真实运行 |
| get_command_catalog | 校验准确包ID与版本后读取固定官方目录；无安装或执行副作用 |
| get_operation | 准确版本完整定义，无条目404；供制作／预检，不是直接执行MCP工具 |
| get_bundled_definitions | 只返目标清单版本JSON；app按④schema核对，不写定义／加载／改图 |
| preview_update | 只读准确版本差异，不下载替换；图影响交⑤ |
| get_usage | 当前真实调用；⑤另供持久未完结／未知使用，③空内存不证明重启后空闲 |
| maintain_package | 单包维护／忙碌409；进入后阻止新固定环境／invoke，覆盖软件、定义和已确认图变更；段内再查⑤已固定准备／排队／执行／未知使用，和①维护gate协调 |
| install/update/uninstall | 仅真实网页确认后的app在维护段await，使用已显示计划准确版本／token；写当前安装事实及最近错误，无跨文件原子性／自动回滚／延迟更新 |
| prepare_package | 引导用户直接操作并重查就绪；敏感正文不进请求／日志／Agent，结束不证明许可完成 |
| invoke_operation | await真实调用结束；核安装版本／操作／许可／参数／科学输入／维护状态，只写受控work目录、原件只读，实际参数来自已准入运行 |
| observe | ③在启动前及真实阶段／终态await⑤回调，保存同次run必要事实与进度／日志；未知进度null，不建调用队列／逐帧账本 |
| cancel_operation | 按call_id真实句柄定向停止；送达与停止分开。不可停给原因，句柄丢失unknown，不全局中断、不提前释放占用 |

⑤先在同次run固定call_id再调用③；③只持当前句柄，最终事实由⑤保存，无独立调用意图表。启动前记录失败阻止软件调用；已开始／返回后的回调或记录失败保留真实调用／日志，不重算。超时／服务退出／丢句柄不推断失败或已停，先查真实事实。
### HTTP 映射、平台网页确认与长操作

| HTTP | 输入 | 成功结果 |
|---|---|---|
| `GET /api/v1/software/packages` | 无 | 200，`list[SoftwarePackage]` |
| `GET /api/v1/software/packages/{package_id}/versions/{version}/commands` | 固定包ID、准确版本 | 200，`list[SirilCommand]`；含官方资料及逐命令参数、上下文、依赖、Headless、风险、定义、registry和CLI验证备注；unknown保持显式，不代表定义、registry加载或运行成功 |
| `GET /api/v1/software/packages/{package_id}` | 路径 ID；可选 `operation_id: UUID`，用于核对确认网页对应的动作 | 200，`SoftwarePackageDetails`，含实际包状态、当前动作、当前计划和可知最终结果；指定动作已失效则409 |
| `POST .../{package_id}/install` | `{version: str, package_token: str}`，请求展示该包／准确版本的计划 | **202，`PendingSoftwareAction(state='awaiting_confirmation')`；此请求不执行安装／写定义／改图** |
| `POST .../{package_id}/prepare` | 无参数正文 | 200，`SoftwarePreparation` |
| `POST .../{package_id}/update-preview` | `{target_version: str}` | 200，`PackageUpdatePreviewResult`，含准确影响的 `impact_token` |
| `POST .../{package_id}/update` | `{target_version: str, impact_token: str}`，请求展示该更新的准确影响 | **202，同一待确认结果；不执行软件／节点／图更新** |
| `POST .../{package_id}/uninstall` | `{package_token: str}`，请求展示当前包／版本移除范围 | **202，同一待确认结果；不执行移除** |

公开提案／查询保持短HTTP，202不执行或挂起到安装完成。确认后app持一个本包coroutine await真实public函数，GET package续查；只有受控引擎实际科学调用显式允许长HTTP读取，不套用普通代理10秒／客户端30秒。package_token与impact_token不互换，均不授予维护权；具体确认如下。

### 当前软件动作、计划展示及专用确认入口

以下是202包装所需的有限 DTO，不是安装计划表或通用审批对象。三个请求模型位于 `contracts/software.py`；含⑤影响的计划和组合结果位于 `contracts/workflows.py`，继续保持单向引用。

| 类型 | 准确字段 |
|---|---|
| `SoftwareActionKind` | `Literal['install','update','uninstall']` |
| `SoftwareInstallRequest` | `version: str`；`package_token: str` |
| `SoftwareUpdateRequest` | `target_version: str`；`impact_token: str` |
| `SoftwareUninstallRequest` | `package_token: str` |
| `ConfirmSoftwareEvent` | `operation_id: UUID`；事件固定为 `apf.page action='confirm_software'`，不接受 confirmed、actor、任意版本／操作／路径或重写计划 |
| `SoftwarePlanNodeChange` | `definition_id: UUID`；`name: str`；`action: Literal['create','update','remove','retain']`；`before_content_token: str \| None`；`after_content_token: str \| None` |
| `SoftwarePlanSummary` | `action: SoftwareActionKind`；`package_id: str`；`current_version: str \| None`；`target_version: str \| None`（仅卸载为 null）；`source: str \| None`（维护清单实际来源，卸载为 null）；`install_path: Path \| None`；`package_token: str`；`impact_token: str \| None`（更新为对应准确影响 token）；`restart_required: bool \| None`；`restart_reason: str \| None`；`node_changes: list[SoftwarePlanNodeChange]`；`workflow_impacts: list[WorkflowImpact]` |
| `PendingSoftwareAction` | `operation_id: UUID`；`state: Literal['awaiting_confirmation','running','completed','failed','expired','unknown']`；`plan: SoftwarePlanSummary`；`confirmation_url: str`；`error: ErrorDetail \| None`。初次202的state固定为awaiting_confirmation；后续作为同一当前动作的事实视图 |
| `SoftwarePackageDetails` | `package: SoftwarePackage`；`current_action: PendingSoftwareAction \| None`；`result: PackageMutationResult \| None`。真实软件阶段／进度来自package；result是当前动作已知最终逐定义／逐图事实 |

operation_id下的plan不可变，包含准确包／路径／来源、节点变化及⑤逐图默认值／保断线／未同步影响；卸载不改图参数／连线，计划无凭据或客户端来源。
confirmation_url由实际ready web_url构成，例如 `/#/workflows?apf_panel=software&package_id=<编码ID>&operation_id=<UUID>`，宿主打开SoftwarePanel；打开／GET及UUID均不授予确认。
以下为create_app内绑定database/settings/workspace/engine及每包当前内存动作的具名闭包：

```python
async def request_software_action( package_id: str, action: SoftwareActionKind, body: SoftwareInstallRequest | SoftwareUpdateRequest | SoftwareUninstallRequest, ) -> PendingSoftwareAction: ...

def get_software_package_details( package_id: str, *, expected_operation_id: UUID | None = None ) -> SoftwarePackageDetails: ...

async def confirm_software_action( body: ConfirmSoftwareEvent, *, page_id: UUID, page_token: str ) -> PendingSoftwareAction: ...

async def execute_software_action( package_id: str, operation_id: UUID ) -> PackageMutationResult: ...
```

| 入口 | 受理和副作用 |
|---|---|
| request_software_action | action由固定路径派生；核对应正文、package／impact token、准确版本、当前繁忙与④⑤影响，生成UUID及不可变计划，202只保存本包pending，无软件／定义／图变更或维护占用。running时409；新明确请求可替换未确认动作，旧UUID失效 |
| get_software_package_details | 只读真实包状态及当前计划／结果；指定operation_id非当前则409 SOFTWARE_ACTION_EXPIRED，普通GET仍可查安装／就绪／进度 |
| confirm_software_action | 只绑定引擎转发的confirm_software网页事件，无公开confirm HTTP／CLI／MCP；page_id/token来自实际连接。SoftwarePanel先显示同UUID计划，真实按钮才发事件，target可空，不依赖画布／Agent权 |
| execute_software_action | 仅确认流程按固定请求／plan启动；app持本包唯一Task await③及④⑤组合直到结束。关页／响应断连不取消；结果更新同一当前动作，不接客户端追加参数 |

确认在单包短准入段核对当前UUID／state，进入maintain_package，重查包／清单／定义／图影响及⑤已固定准备／排队／执行／未知使用；安装／卸载也须与已显示计划相同，更新再核impact_token。全通过才running和实际副作用；变化expired409，繁忙拒绝并使动作失效，无延后自动执行。
以当前调用的内存完成信号保证准入成功才回running，不能先报启动再发现不允许。重复running／completed确认只返回现状，不起第二Task；expired／丢失409。每包仅保留当前动作、Task及最近结果：重启不恢复确认或自动重放，旧pending链接失效；已开始但无结束证据按③安装事实unknown查询，result不可知为null。
202后的安装／定义／图失败由当前state/error/result表达，不改写原202；软件已装而加载失败保留真实安装事实。来源识别仍须UI原型，失败阻塞维护，不降级MCP自填human／confirmed或另设确认API。此专用链不增加普通节点／运行确认。
宿主公开 `confirmSoftware(operationId: string): Promise<PendingSoftwareAction>`，只发已有WS的confirm_software专用事件，SoftwarePanel经公开导出交宿主；page_result回该动作真实结果，不改变画布控制。真实科学调用与动态ScientificValue／scalar核对统一见[原生执行边界](#native-design)，③不另设任意文件执行API。

重启要求由实际包／节点装载原型给出，未知为null并说明原因，不猜成无需重启。安装完成与节点已加载分开；需要重启时先结束当前安装动作并明确显示未加载原因，再由服务外的显式生命周期入口处理，不让安装Task一边保持busy一边等待自身服务重启。未获准重启不自动执行，繁忙仍拒绝、不排稍后自动重启。

### ④定义 JSON、嵌入结构及 public 函数

以下类型位于 `contracts/nodes.py`；端口、参数和绑定内嵌同一 JSON，不拆对象表。

| 类型 | 精确字段 |
|---|---|
| `NodePort` | `name: str`；`type: str`，实际原生类型，数组次序就是原生 slot 次序 |
| `NodeParameterBinding` | `kind: Literal['parameter']`；`name: str`，指本定义的参数名 |
| `FixedParameterBinding` | `kind: Literal['fixed']`；`value: JsonValue` |
| `SoftwareBinding` | `package_id: str`；`operation_id: str`；`inputs: dict[str, str]`（操作输入名→本节点输入名）；`parameters: dict[str, NodeParameterBinding \| FixedParameterBinding]`（操作参数名→来源）；`outputs: dict[str, str]`（本节点输出名→操作输出名） |
| `NodeDefinition` | `definition_id: UUID`；`source: Literal['custom','package']`；`name: str`；`description: str`；`inputs: list[NodePort]`；`outputs: list[NodePort]`；`parameters: list[ParameterDefinition]`；`execution: SoftwareBinding` |
| `SavedDefinition` | `definition: NodeDefinition`；`content_token: str`；`native_type: str`，稳定为 `APF_{definition_id.hex}`，改名和修改内容不换此 ID |
| `PortRemap` | `name: str`；`type: str`；`before_index: int`；`after_index: int` |
| `DefinitionChange` | `before: SavedDefinition`；`after: SavedDefinition`；`input_remap: list[PortRemap]`；`output_remap: list[PortRemap]`；`disconnected_inputs: list[str]`；`disconnected_outputs: list[str]`；`parameter_defaults: dict[str, JsonValue]` |
| `NativeNodeLoad`（组合结果使用） | `definition_id: UUID`；`content_token: str \| None`；`state: Literal['loaded','not_loaded','failed','unknown']`；`reason: str \| None`，来自引擎实际报告，不写入定义 JSON |
| `NativeLoadReport` | `observed_at: datetime`、`definitions: list[NativeNodeLoad]`、`data_reference_loaded: bool`；只有实际registry查询可生产，不从定义文件推断loaded |

| `DefinitionWriteResult` | `definition_id: UUID`；`action: Literal['create','update','remove']`；`applied: bool`；`content: SavedDefinition \| None`；`error: ErrorDetail \| None`；remove 成功时 content 为 null，其他成功项返回实际写入内容 |

source区分custom／package；包归属取execution.package_id。首批仅SoftwareBinding，定义不含项目素材、路径、凭据或会话。
```python
def list_definitions(workspace: Path) -> list[SavedDefinition]: ...
def get_definition(workspace: Path, definition_id: UUID) -> SavedDefinition: ...
def create_definition( workspace: Path, definition: NodeDefinition, operation: SoftwareOperation ) -> SavedDefinition: ...
def preview_definition_update( workspace: Path, definition: NodeDefinition, expected_content_token: str, operation: SoftwareOperation, ) -> DefinitionChange: ...
def update_definition( workspace: Path, change: DefinitionChange ) -> SavedDefinition: ...
def replace_package_definitions( workspace: Path, package_id: str, definitions: list[NodeDefinition], expected_tokens: dict[UUID, str], ) -> list[DefinitionWriteResult]: ...
```

| 函数 | 参数／返回、错误和副作用 |
|---|---|
| list/get_definition | 只读当前JSON；缺失404、损坏明确失败，不跳过或从文件存在推断加载，不读⑤运行库 |
| create_definition | 调用方生成UUID，exclusive首次创建，已有ID409；app从③取operation核对可表示端口／参数及绑定后写单文件，不加载或运行 |
| preview_definition_update | 核旧token及拟内容／operation，返回候选before/after和remap；不写定义／图、不改变测试 |
| update_definition | app核影响、真实确认及在途使用后，写前再核before.content_token，冲突409；临时文件替换唯一JSON，不调用⑤或保留旧版本 |
| replace_package_definitions | 维护段内仅更换该包定义，不覆盖custom；expected_tokens须是完整旧ID→token，新删改集合不符在首写前409。按ID先增改后删；逐项返DefinitionWriteResult，首文件失败即停，未尝试项不执行，不承诺回滚；旧图缺节点仍保留 |

更新不得换definition_id/source/包归属。输入／输出各自唯一，参数与数据输入不得占同一原生键。operation.ready=False不阻止保存；SavedDefinition为内容视图，DefinitionChange.after仅候选，真实写入与加载由组合结果表达。

### 确认更新及在途保护

app从③读取准确operation，④preview_definition_update后将DefinitionChange／PackageChange及前后定义交⑤preview_workflow_change。impact_token绑定包／定义与各图内容，实际应用再核确认、未同步草稿和影响；冲突409或逐图报告。④写定义，⑤apply_workflow_change保存确认范围，返回逐图事实，无跨文件原子性。
custom全部实例参数采用新默认；按方向／名称／类型的PortRemap保线（含纯重排），改名／类型／删除仅断对应线，新增不自动连。package仅按③变化参数规则，不扩大到任意第三方。
定义及引擎装载替换与⑤固定实现共用短准入；get_implementation_usage含已固定的preparing/submitting/queued/running/unknown。仍有引用则NODE_BUSY、零替换，不自动延迟加载或建旧类多版本；结束后用户重新预览／请求。普通编辑和取消不受扩大限制。

### HTTP 映射与组合结果

| HTTP | 输入 | 成功结果 |
|---|---|---|
| `GET /api/v1/nodes` | 无 | 200，当前定义、实际③就绪／原生加载和最近显式测试的组合列表 |
| `GET /api/v1/nodes/{definition_id}` | 定义 UUID | 200，同一组合详情；④原始定义、加载状态与测试结果分开 |
| `POST /api/v1/nodes` | `{definition: NodeDefinition, operation_version: str}`，`source='custom'` | 201，`NodeDetails`；保存成功加载失败仍返回真实保存事实 |
| `POST .../{definition_id}/update-preview` | `{definition: NodeDefinition, operation_version: str, expected_content_token: str}` | 200，`NodeUpdatePreviewResult`；包含change／preview及blocking_run_ids，不另造第二种布局 |
| `POST .../{definition_id}/update` | 同一 definition、`operation_version`、`expected_content_token`、`impact_token` | 200，保存／加载和逐图结果；副作用前冲突409，已部分发生用准确组合结果报告 |
| `POST .../{definition_id}/test` | 下述 `NodeTestCreate` | 202，⑤ `RunDetail`；仅表示同次运行已受理／准备，不表示测试通过 |

组合 HTTP 类型放 `contracts/workflows.py`，由它单向引用④ `SavedDefinition/DefinitionChange/DefinitionWriteResult/NativeNodeLoad`、③ `SoftwarePackage/PackageChange`；④和③契约均不导入⑤。软件／节点路由通过 app.state 的具名已装配函数取得组合结果，不建立动态能力调用框架。

| 组合类型 | 准确字段 |
|---|---|
| `NodeDetails` | `ready: bool`；`reason: str \| None`；`saved_definition: SavedDefinition`；`load: NativeNodeLoad`；`software_ready: bool`；`software_reason: str \| None`；`latest_test: NodeTestResult \| None`；`matches_current_content: bool \| None` |
| `NodeUpdatePreviewResult` | `change: WorkflowChange`（`custom_definition` 分支）；`preview: WorkflowChangePreview`；`blocking_run_ids: list[UUID]` |
| `PackageUpdatePreviewResult` | `change: WorkflowChange`（`software_package` 分支）；`preview: WorkflowChangePreview`；`blocking_run_ids: list[UUID]` |
| `NodeUpdateResult` | `definition_saved: bool`；`saved_definition: SavedDefinition \| None`；`load: NativeNodeLoad \| None`；`workflow_results: list[WorkflowChangeResult]`；`error: ErrorDetail \| None` |
| `PackageMutationResult` | `package: SoftwarePackage`；`definition_results: list[DefinitionWriteResult]`；`loads: list[NativeNodeLoad]`；`workflow_results: list[WorkflowChangeResult]`；`error: ErrorDetail \| None` |

operation_version只供制作／更新准确核③定义，不指定另一运行环境；实际版本来自⑤固定上下文。定义单文件成功后查真实加载，definition_saved=True与load.failed/unknown可并存。副作用前冲突409；第一项真实变更后失败返回已尝试定义／图及错误，不丢失部分事实。软件确认／卸载规则沿本节当前动作。

### 显式节点测试组合

NodeTestCreate／NodeTestAssociation在第14节唯一定义。app绑定nodes.routes，下面submit_node_test是create_app内闭包，捕获当前DB/settings/PageCall/SubmitPrompt/preparations并只委托⑤test_node，不在登记run之前先改图；④不加执行函数：
```python
async def submit_node_test(body: NodeTestCreate) -> RunDetail: ...

```

submit_node_test核④当前token，把明确输入／参数通过⑤局部编辑落实到指定在线测试图，取得真实执行节点定位后形成node_test，再走第14节唯一转换／保存／受理链；新测试图仍是普通原生图，不隐藏覆盖其他图或用正文绕过保存。普通整图运行不自动算显式测试。get_node_details组合latest_node_test与当前token得到matches_current_content；无测试null、旧测试保留、失败不阻止定义保存。
原生类型只引用真实导出：ComfyWorkflowJSON／ComfyApiWorkflow均在 `frontend/src/platform/workflow/validation/schemas/workflowSchema.ts`；`frontend/src/schemas/nodeDefSchema.ts`重导出的ComfyNodeDef可如litegraphService本地alias为ComfyNodeDefV1，并调用useLitegraphService().registerNodeDef。保存、注册、刷新和实际调用分别观察；白名单／热加载及执行适配统一见第15节。

<a id="workflows-design"></a>

## 14. ⑤项目图、运行与预览

### ⑤必要类型

文件和共同DTO规则见第10节；以下在contracts/workflows.py定义。原生编辑／执行图在Python仅作JsonObject，UI不复制原生schema。
| 类型 | 字段及枚举 |
|---|---|
| `WorkflowTarget` | `project_id: UUID`、`workflow_id: UUID`、`page_id: UUID`、`subgraph_path: list[str] = []`；子图路径为原生导航路径，空列表为根图 |
| `WorkflowGuard` | `target: WorkflowTarget`、`content_token: str`、`control_token: UUID`；后台将 token 当不透明校验值，不重新实现原生图比较 |
| `WorkflowSummary` | `project_id: UUID`、`workflow_id: UUID`、`path: str`、`name: str`；path 为原生 userdata 中的工作流相对位置 |
| `WorkflowPage` | `items: list[WorkflowSummary]`、`total: int`、`limit: int`、`offset: int`，分页语义沿现有接口 |
| `WorkflowDetail` | `workflow: WorkflowSummary`、`saved_graph: JsonObject`、`saved_content_token: str`、`online: AgentContext \| None = None`；在线内容和保存内容分开 |
| `AgentContext` | `target: WorkflowTarget \| None`、`content_token: str \| None`、`control_token: UUID \| None`、`agent_allowed: bool`、`online: bool`、`active: bool`、`sync_state: Literal['saved','unsaved','unknown']`、`supported_operations: list[EditOpName]`、`current_graph: JsonObject \| None`、`reason: str \| None`；current_graph为本次向已绑定页面真实读取的最新画布，和保存JSON分开；离线或无法确认时为null并说明原因，未绑定时不猜选其他页面 |
| `PageObservation`（内部） | `page_id: UUID`、`page_token: str`、`native_client_id: str`、`target: WorkflowTarget \| None`、`content_token: str \| None`、`control_token: UUID \| None`、`online: bool`、`active: bool`、`sync_state: Literal['saved','unsaved','unknown']`、`supported_operations: list[EditOpName]`、`workflow_sync: dict[str, Literal['saved','unsaved','unknown']]`、`current_graph: JsonObject \| None`；由实际引擎连接事件建立，只在组合根内存保留，不外发page_token |
| `SaveResult` | `target: WorkflowTarget`、`file_saved: bool \| None`、`association_saved: bool \| None`、`path: str \| None`、`content_token: str`、`error: ErrorDetail \| None = None`；只有文件及项目关联均为True才报告本次保存成功；None是未知，查询核对且阻止运行 |
| `EditRequest` | `guard: WorkflowGuard`、`operations: list[EditOperation]` |
| `EditOperationResult` | `index: int`、`op: EditOpName`、`applied: bool`、`node_id: str \| None = None`、`link_id: int \| None = None`、`value: JsonValue = None`、`error: ErrorDetail \| None = None`；`set_parameter` 依 `applied/op` 解释实际采用的 `value`，合法 null 不被当成缺失 |
| `EditResult` | `guard: WorkflowGuard`、`results: list[EditOperationResult]`、`applied_count: int`、`failed_index: int \| None`、`save: SaveResult`；仅包含已尝试的有序操作，失败后的操作不执行 |
| `ReplaceRequest` | `guard: WorkflowGuard`、`workflow: JsonObject`；只用于已明确的导入／替换，不接收可自行赋权的 `confirmed` |
| `ReplaceResult` | `guard: WorkflowGuard`、`applied: bool`、`missing_node_types: list[str]`、`save: SaveResult`；缺依赖JSON可以保留，加载与保存分别报告 |
| `RunScope` | 判别联合 `AllScope(mode: Literal['all'])` 或 `TargetScope(mode: Literal['targets'], node_ids: list[str])`；ID 是原生 execution ID，包含必要依赖 |
| `NodeTestAssociation` | `definition_id: UUID`、`definition_content_token: str`、`node_execution_id: str`；内容校验及实例必须与本次实际采用的④定义一致 |
| `NodeTestCreate` | `run_id: UuidInput`、`definition_id: UuidInput`、`definition_content_token: str`、`guard: WorkflowGuard`、`inputs: dict[str, InputReference]`、`parameters: JsonObject`；仅显式节点测试组合入口使用，输入参数先落实到指定测试画布，不直接生成游离执行参数 |
| `RunSubmit` | `run_id: UuidInput`、`guard: WorkflowGuard`、`scope: RunScope`、`input_mode: Literal['reproducible','reference'] = 'reproducible'`、`queue_number: float = 0`；queue_number沿原生优先／位置含义，没有可自填的 `origin`、`prompt_id`、执行命令或额外参数副本 |
| `PreparedCanvas`（内部） | `guard: WorkflowGuard`、`path: str`、`workflow: JsonObject`、`prompt: JsonObject`、`saved_content_token: str`、`native_client_id: str`；只由绑定宿主的真实准备结果产生，不接受 MCP 自备执行图 |
| `RunStatus` | `Literal['preparing','submitting','queued','running','completed','failed','cancelled','unknown']`；取消请求另存，只有真实停止才标 cancelled |
| `AssetInputUse`（公开投影） | `kind: Literal['asset_version']`、`asset_id: UUID`、`asset_version_id: UUID`、`dataset_version_id: UUID \| None`、`member_index: int \| None`、`selection: ScienceSelection`、`parameters: AssetParameters`、`asset_revision: int`、`preparation: Literal['existing_managed','materialized','reference']`；来自实际 `ResolvedAssetInput`，不暴露 `read_path` |
| `OutputInputUse`（公开投影） | `kind: Literal['run_output']`、`locator: OutputLocator`、`selection: ScienceSelection`、`format: ScienceFormat`；来自实际 `ResolvedOutputInput`，没有伪造的asset身份或revision |
| `InputUse` | `AssetInputUse \| OutputInputUse` 的kind判别联合 |
| `RunCallUse`（公开投影） | `call_id: UUID`、`node_execution_id: str`、`list_index: int \| None`、`package_id: str`、`version: str`、`operation_id: str`、`operation_content_token: str`、`inputs: dict[str, list[InputUse]]`、`parameters: JsonObject`、`state: Literal['starting','running','completed','failed','cancelled','unknown']`；表达实际调用及动态采用值，不能只保存编排时的静态参数 |
| `RunCallContext`（内部） | `invocation: SoftwareInvocation`、`list_index: int \| None`、`observation: SoftwareObservation \| None`；只保留该真实调用的采用值及最新观察，关联原生list求值位置，不保存进度每帧 |
| `RunContext`（内部） | `canvas: PreparedCanvas`、`inputs: ResolvedInputs`、`node_definitions: list[SavedDefinition]`、`software: list[SoftwareOperation]`、`calls: list[RunCallContext]`；各次真实调用采用的科学来源、解析输入及有效参数随实际入边求值后写入，仍属同一运行，不另建调用队列 |
| `NativeNodeCall`（内部） | `prompt_id: UuidInput`、`node_execution_id: str`、`list_index: int \| None`、`execution_token: str`、`scientific_values: dict[str, ScientificValue \| list[ScientificValue]]`、`parameter_values: JsonObject`；来自原生实际求值，不接收软件操作、命令、workdir或path |
| `NativeNodeResult`（内部） | `outputs: dict[str, list[OutputLocator]]`、`ui: JsonObject`；⑤检查实际完整输出后产生locator，原生适配按已保存端口顺序／单个或集合声明返回，不按数量猜类型；ui沿原生输出协议 |
| `OutputSaveState` | `Literal['not_requested','pending','saved','failed','unknown']` |
| `OutputSaveResult` | `output: OutputLocator`、`state: OutputSaveState`、`task_id: UUID \| None`、`registration: OutputRegistration \| None`、`error: ErrorDetail \| None = None`；只有②报告完整content available才是saved；登记、解析、素材预览继续由registration各字段分别表达 |
| `RunOutput` | `output: OutputLocator`、`format: str`、`availability: Literal['available','missing','unknown']`、`preview_ids: list[UUID]`、`save: OutputSaveResult`；内部对应 `CheckedOutput` 另存于同一运行结果，不外发绝对路径 |
| `CancelResult` | `run_id: UUID`、`requested: bool`、`queue_removed: bool \| None`、`interrupt_sent: bool \| None`、`native: NativeCancelResult \| None`、`software: list[SoftwareCancelResult]`、`stop_state: Literal['stopped','running','unknown']`、`reason: str \| None`；动作与实际停止映射见原生取消专节 |
| `RunDetail` | `run_id: UUID`、`workflow_id: UUID`、`project_id: UUID`、`prompt_id: UUID \| None`、`origin: Literal['human','agent']`、`status: RunStatus`、`active: bool \| None`、`reference_observations: list[ReferenceObservation]`、`requested_scope: RunScope`、`actual_node_ids: list[str]`、`terminal_node_ids: list[str]`、`not_executed: list[str]`、`input_mode: Literal['reproducible','reference']`、`inputs: list[InputUse]`、`workflow: JsonObject \| None`、`prompt: JsonObject \| None`、`validation: NativeValidation \| None`、`node_definitions: list[SavedDefinition]`、`software: list[SoftwareOperation]`、`calls: list[RunCallUse]`、`node_test: NodeTestAssociation \| None`、`outputs: list[RunOutput]`、`cancel: CancelResult \| None`、`created_at: datetime`、`started_at: datetime \| None`、`finished_at: datetime \| None`、`log_path: str \| None`、`error: ErrorDetail \| None`；准备未完成的字段为null／空列表，原生详细错误随validation保留，不塞入仅字符串的ErrorDetail.fields |
| `RunPage` | `items: list[RunDetail]`、`total: int`、`limit: int`、`offset: int` |
| `PreviewSummary` | `preview_id: UUID`、`workflow_id: UUID`、`output: OutputLocator`、`created_at: datetime`、`state: Literal['generating','available','unsupported','failed']`、`mime_type: Literal['image/jpeg']`、`error: ErrorDetail \| None`；可读内容由具名读取接口提供 |
| `SaveOutput` | `output: OutputLocator`、`name: str \| None = None`；body中的run_id必须等于路径run_id |
| `NodeTestResult` | `run_id: UUID`、`definition_id: UUID`、`tested_content_token: str`、`status: RunStatus`、`created_at: datetime`、`finished_at: datetime \| None`；④详情用当前定义校验比较，得出旧测试提示 |
| `WorkflowImpact` | `project_id: UUID`、`workflow_id: UUID`、`path: str`、`content_token: str`、`node_execution_ids: list[str]`、`parameter_defaults: dict[str, JsonObject]`（实例→新默认）、`retained_link_ids: list[int]`、`disconnected_link_ids: list[int]`、`missing_definition_ids: list[UUID]`、`unsaved_pages: list[UUID]`；定义／包diff由应用组合，⑤给出准确图影响，不让③④契约反向引用⑤ |
| `WorkflowChange` | `CustomWorkflowChange(kind: Literal['custom_definition'], change: DefinitionChange)` 或 `PackageWorkflowChange(kind: Literal['software_package'], package: PackageChange, before_definitions: list[SavedDefinition], after_definitions: list[SavedDefinition])` 的kind判别联合 |
| `WorkflowChangePreview` | `impact_token: str`、`impacts: list[WorkflowImpact]`；token绑定上述change及各图当前内容，不表示已确认 |
| `WorkflowChangeResult` | `workflow_id: UUID`、`applied: bool \| None`、`save: NativeWorkflowChangeResult \| None`、`error: ErrorDetail \| None`；逐图返回实际结果，不冒充跨文件原子成功 |
| `RunImplementationUse` | `run_id: UUID`、`status: RunStatus`、`binding_unknown: bool`、`package_ids: list[str]`、`definition_ids: list[UUID]`；只列已有固定实现的preparing/submitting/queued/running/unknown运行，包含尚未调用③的排队工作 |
| `PageCommand`（内部） | 公共字段 `command_id: UUID`、`page_token: str`；`read`携带`target: WorkflowTarget`，其余动作携带`guard: WorkflowGuard`。`action`为`read/edits/save/replace/prepare_run/check`判别联合；edits另带`operations: list[EditOperation]`，replace另带`workflow: JsonObject`，prepare_run另带`run_id: UUID/scope: RunScope/input_mode/queue_number: float`，其余无动作载荷 |
| `PageResult`（内部） | `command_id: UUID`、`page_id: UUID`、`page_token: str`、`action`同上、`context: AgentContext`、`error: ErrorDetail \| None`；按action判别联合，各变体的`result`类型严格为`read/check→AgentContext \| None`、`edits→EditResult \| None`、`save→SaveResult \| None`、`replace→ReplaceResult \| None`、`prepare_run→PreparedCanvas \| None`，失败无载荷为null，不建可永久修改的命令对象 |

科学类型唯一引用contracts/inputs.py；AssetParameters沿assets，SavedDefinition／DefinitionChange及SoftwareOperation／Invocation／Observation／PackageChange沿③④契约。公开InputUse为去path投影；内部完整文件只交受控执行。
`EditOperation` 用 `op` 判别的 Pydantic 联合，首批仅以下原生操作；`EditOpName` 即这些名称的 Literal 联合。

| op／模型 | 除固定 `op` 外的字段 |
|---|---|
| `add_node`／`AddNode` | `definition_id: UUID`、`position: tuple[float,float] \| None = None` |
| `add_data`／`AddData` | `reference: InputReference`、`position: tuple[float,float] \| None = None`；科学选择已经在固定reference内，不重复一份selection |
| `set_data`／`SetData` | `node_id: str`、`reference: InputReference`；只替换指定数据节点的固定引用，科学选择沿reference；不全局更换其他节点／项目引用 |
| `set_parameter`／`SetParameter` | `node_id: str`、`parameter: str`、`value: JsonValue` |
| `connect`／`Connect` | `source_node_id: str`、`source_output: int`、`target_node_id: str`、`target_input: int`；使用实际原生端口序号，不按显示名称猜测 |
| `disconnect`／`Disconnect` | `link_id: int`；客户端先读取实际 link ID |
| `remove_node`／`RemoveNode` | `node_id: str` |
| `move_node`／`MoveNode` | `node_id: str`、`position: tuple[float,float]` |
| `undo/redo`／`Undo/Redo` | 无额外字段，作用于该页面当前会话 |

添加先取得真实原生ID，再提交后续连接，无跨操作临时ID；未桥接分组／控件不列支持。局部操作进入原生撤销，部分失败返实际EditResult，不重放。新版本接纳及set_data固定引用规则见第12节。
### `models.py` 与保存的事实

| 拟新增模型 | 关键列、约束及用途 |
|---|---|
| `Workflow`／表 `workflow` | `workflow_id` PK（原生图 UUID）、`project_id`、`path` UNIQUE、`saved_content_token`、`agent_allowed`、`control_token`、`bound_page_id` nullable；同一行保存项目关联及当前控制，name 从实际 path 展示，不另存编辑 JSON |
| `WorkflowRun`／表 `workflow_run` | `run_id` PK、`prompt_id` UNIQUE nullable、`workflow_id/project_id` 的当次身份、`origin/status`、`request_json/context_json/result_json`、`execution_token`（私有）、必要开始结束时间和日志位置；`context_json` 保存实际图、定义、软件与 `ResolvedInputs`，`result_json` 保存实际输出、取消观察和所选结果的固定 task／asset 关联 |
| `WorkflowPreview`／表 `workflow_preview` | `preview_id` PK、`workflow_id`、`run_id` FK、`node_execution_id/output_index/member_index`、`path`、`created_at/state/error`；每个实际完成图像输出生成轻量 JPEG，多次预览分行保存 |

`WorkflowRun.workflow_id/project_id` 是当次身份事实，不以当前 `Workflow` 行存活为前提；删除当前图不级联删除历史运行。图文件仍在 `workspace/comfyui-user/default/workflows/` 的原生位置；运行科学工作目录仍为 `workspace/runs/{run_id}/work`，预览唯一文件为 `workspace/output/apf-previews/{run_id}/{preview_id}.jpg`，⑤SQLite记录此路径。原生UI输出descriptor使用`type='output'`、`subfolder='apf-previews/{run_id}'`、`filename='{preview_id}.jpg'`，直接沿既有`/view`读取同一JPEG；不另复制预览、不新增view根或挂载API。删图清理其专属预览与当前关联，运行如实显示预览缺失，已交②保存的完整素材保持。输出保存关联留在本次 `result_json`，不新增 `SaveReceipt` 表。

连接／活动图／等待响应仅在内存，当前控制仅存表列字段；重连／读取不授予权限，详见第15节。下列调用别名只是app绑定的具体函数，原生观察沿已有JSON，无Gateway／Protocol；等待页面／软件不持事务。

### public.py完整签名
```python
PageCall = Callable[[PageCommand], Awaitable[PageResult]]
SubmitPrompt = Callable[[NativePromptRequest], Awaitable[NativePromptReply]]
ObservePrompt = Callable[[UUID], Awaitable[JsonObject]]
ApplyFileChange = Callable[[NativeWorkflowChange], Awaitable[NativeWorkflowChangeResult]]

def list_workflows(database: Database, project_id: UUID, *, limit: int = 50, offset: int = 0) -> WorkflowPage: ...
async def get_workflow(database: Database, settings: Settings, workflow_id: UUID, *, page: PageObservation | None = None, page_command: PageCall | None = None) -> WorkflowDetail: ...
async def get_agent_context(database: Database, page: PageObservation | None, page_command: PageCall) -> AgentContext: ...
def apply_page_event(database: Database, page: PageObservation, action: Literal['open', 'state', 'changed', 'handoff']) -> AgentContext: ...
async def edit_workflow(database: Database, settings: Settings, body: EditRequest, page_command: PageCall) -> EditResult: ...
async def save_workflow(database: Database, settings: Settings, guard: WorkflowGuard, page_command: PageCall) -> SaveResult: ...
async def replace_workflow(database: Database, settings: Settings, body: ReplaceRequest, page_command: PageCall) -> ReplaceResult: ...
async def submit_run(database: Database, settings: Settings, body: RunSubmit, page_command: PageCall, post_prompt: SubmitPrompt, *, origin: Literal['human', 'agent'], preparations: dict[UUID, Task[None]]) -> RunDetail: ...
async def execute_node(database: Database, settings: Settings, body: NativeNodeCall) -> NativeNodeResult: ...
async def get_run(database: Database, settings: Settings, run_id: UUID, query_prompt: ObservePrompt) -> RunDetail: ...
def list_runs(database: Database, workflow_id: UUID, *, limit: int = 50, offset: int = 0) -> RunPage: ...
def list_previews(database: Database, run_id: UUID) -> list[PreviewSummary]: ...
def read_preview(database: Database, settings: Settings, run_id: UUID, preview_id: UUID) -> tuple[bytes, str]: ...
async def save_output(database: Database, settings: Settings, run_id: UUID, body: SaveOutput) -> OutputSaveResult: ...
def latest_node_test(database: Database, definition_id: UUID) -> NodeTestResult | None: ...
def find_definition_usage(database: Database, settings: Settings, definition_id: UUID, pages: Sequence[PageObservation]) -> list[WorkflowImpact]: ...
def find_input_usage(database: Database, settings: Settings, pages: Sequence[PageObservation], scope: LibraryRemovalScope) -> list[WorkflowImpact]: ...
def preview_workflow_change(database: Database, settings: Settings, change: WorkflowChange, pages: Sequence[PageObservation]) -> WorkflowChangePreview: ...
async def apply_workflow_change(database: Database, settings: Settings, change: WorkflowChange, preview: WorkflowChangePreview, apply_file_change: ApplyFileChange, *, operation_id: UUID, pages: dict[UUID, PageObservation], permits: dict[str, FileWritePermit]) -> list[WorkflowChangeResult]: ...
async def get_implementation_usage(database: Database, settings: Settings, query_prompt: ObservePrompt, *, package_ids: list[str], definition_ids: list[UUID]) -> list[RunImplementationUse]: ...
```

execute_node的私有token、实际动态科学／scalar求值与manifest核对见第15节；采用值固定进同次RunContext，③回调更新最新真实观察，不建队列／逐帧账本。
save_output先核CheckedOutput，短事务为OutputLocator固定唯一task_id，提交后交②register_output；续查／补登记用同task，不重算。preview_workflow_change只读当前原生JSON及页面观察，提取APF节点／固定引用所需字段，其余JSON保留；apply_workflow_change重核change／impact及草稿，调用app注入的apply_file_change经同一原生最终guard保存，逐图返事实。普通Agent依活动页；明确批准维护仅作用已确认保存图。
显式测试组合及latest_node_test语义见第13节；不创建第二运行／测试权威。

get_agent_context及在线get_workflow先从已绑定页面发送read，取得本次actual current_graph再投影；PageObservation缓存只用于定位／断连判断，不冒充最新图。未绑定或离线时current_graph为null并说明原因，保存图仍单独读取；读取不授权。PreparedCanvas另含`native_client_id: str`，仅由引擎实际socket补入，供NativePromptRequest.client_id路由，不能作为用户认证。queue_number为0省略number，为-1置front=true，其余沿原生number；不把None发送为number:null。


执行时固定InputReference必须匹配本run已经固定的ResolvedAssetInput；不能在排队后再次resolve_inputs读取新的Asset.parameters/revision或重新物化。只有新run才采用新纠正资料。同run上游OutputLocator仍按固定连线及真实输出动态解析，连线scalar实际值照常记录。get_run及get_implementation_usage使用显式Settings调用③inspect_operation，并结合query_prompt刷新实际占用；app仅注入固定settings/原生回调，不写⑤ORM或凭新进程空句柄表判闲。


外部get_agent_context始终针对用户已明确绑定的目标：current_graph非null必须属于同一target；绑定页从A切到B时返回A不活动/current_graph=null及实际原因，不能把B内容拼到A或读取时重新绑定。get_workflow(A)仍可读A保存文件。当前未关联或临时图只保留原生草稿/页面观察，MCP不读成可写目标；给Agent前先按首次保存流程完成关联。


### 从所选完整结果反查运行

```python
def find_saved_output(database: Database, asset_version_id: UUID) -> OutputLocator | None: ...
```

该⑤公开只读查询匹配同库run.result_json中真实OutputRegistration.asset_version_id，返回原OutputLocator或None，不按名称/相同hash/Header推断来源。HTTP为`GET /api/v1/runs/outputs/by-asset-version/{asset_version_id}`，200为定位或null；不以结果版本当前是否仍存在去改写历史登记事实，也不声称该文件仍可读。客户端增加同名具名查询，GUI素材详情由宿主组合此只读回查与RunPanel，MCP读定义后可调用；②不反向读⑤ORM或为此添Lineage表。原始导入/外部接纳的新内容版本无本平台产出登记时返回null，不把同Asset的旧版本来源冒充新内容来源。得到run_id后沿现有get_run查实际图、输入/参数、软件/调用和输出。该route在动态/runs/{run_id}前明确注册。

验收归P-RUNS/P-INTEGRATION：用户所选保存完成后按准确asset_version_id可回查相同run/node/output/member；普通导入或同Asset外部新版本返回null，旧run不变。UI只查看，不换画布或授控制，读取不新增运行/资产。

### `routes.py` 与原生钩子

HTTP路径委托上述函数；agent-context须先于/{workflow_id}注册，预览返回image/jpeg，内部页事件／运行观察不进能力目录。Agent来源与原生人工来源由第15节专用链派生，软件确认仅由app交③。

| 原生已有位置与函数 | 必要新增钩子／保留行为 |
|---|---|
| `frontend/src/platform/workflow/core/services/workflowService.ts` 的 `afterLoadNewGraph`／`activateLoadedWorkflow`（现约703／716行） | 导入或加载只更新该页面活动图观察；临时图不得立即冒充已保存项目工作流。首次成功保存再建立关联；已有持久图读取原生 `id`，不用 `instanceId` |
| 同文件 `saveWorkflow`（现约320行）、`saveWorkflowAs`（现约266行） | 保留原生提示／覆盖／Store保存；挂接同一托管 userdata before／after guard及项目关联 finalize。返回 false／文件失败／关联失败都阻止运行；明确区分文件已写但关联未完成 |
| `frontend/src/platform/workflow/management/stores/workflowStore.ts` 的 `saveAs`（现约220行） | 复用原生另存生成新 UUID；首次临时图保存沿 `saveWorkflowAs` 的实际路径，不额外再造身份 |
| `workflowService.ts` 的 `renameWorkflow`（现约603行）、`deleteWorkflow`（现约618行）及 Store 同名方法 | 在成功的实际原生 move／delete 后更新关联或清理专属预览；失败如实保留已发生事实。`engine/ComfyUI/app/user_manager.py` 的实际 `post_userdata/move_userdata/delete_userdata` 使用公共集成 guard，不能仅在按钮处检查 |
| `frontend/src/scripts/app.ts` 的 `queuePrompt`（现约1715～2083行） | 保留现有每批次 seed／控件顺序、原生排队UI和 queued job 关联；托管分支把实际提交替换为 `submitNativeRun`，不再调用 `api.queuePrompt` 第二次。非托管原生行为按既有范围保持 |
| `frontend/src/scripts/changeTracker.ts` 的 `captureCanvasState/updateModified/undo/redo` 与原生 graph intent／布局入口 | 在真实人工参数、节点、连线、布局及撤销变化处调用桥接接管；Agent操作和本次运行控件准备标明自己的实际来源。仅查看／缩放／平移／切页签不接管；继续用原生撤销，不以所有 `graphChanged` 无差别认定人工变化 |
| `frontend/src/scripts/app.ts` 的 `executed/execution_start` 事件消费（现约785／802行）、`nodeOutputStore`、`ChangeTracker` 已有按 `prompt_id` 查 queued job 的路径（现约714行） | 统一从 prompt→运行→工作流取目标；A结果先写A的运行及预览，只在A实际为活动图时更新当前画布，B不调用A节点 `onExecuted`。缓存回放不登记为新处理 |
| `frontend/src/scripts/api.ts` 与 `engine/ComfyUI/server.py` 的既有 `/ws` handler | 增加有限 `apf.command/apf.result/apf.page`，复用当前连接及定向返回；现有 feature_flags 消息不变。具体内部认证／一次文件 write token 由公共桥接协议规定 |

### 宿主与UI的TypeScript入口

UI的api/contracts.ts／api/client.ts沿第10节公开DTO与FetchApi；只验证原生JSON为对象，宿主才用原生类型。
```typescript
export interface WorkflowsClient {
  listWorkflows(projectId: string, options?: { limit?: number; offset?: number }): Promise<WorkflowPage>
  getWorkflow(workflowId: string): Promise<WorkflowDetail>
  getAgentContext(): Promise<AgentContext>
  edit(body: EditRequest): Promise<EditResult>
  save(guard: WorkflowGuard): Promise<SaveResult>
  replace(body: ReplaceRequest): Promise<ReplaceResult>
  submitRun(body: RunSubmit): Promise<RunDetail>
  getRun(runId: string): Promise<RunDetail>
  listRuns(workflowId: string, options?: { limit?: number; offset?: number }): Promise<RunPage>
  cancelRun(runId: string): Promise<CancelResult>
  listPreviews(runId: string): Promise<PreviewSummary[]>
  readPreview(runId: string, previewId: string): Promise<Blob>
  saveOutput(runId: string, body: SaveOutput): Promise<OutputSaveResult>
  findSavedOutput(assetVersionId: string): Promise<OutputLocator | null>
}
export function createWorkflowsClient(fetchApi: FetchApi): WorkflowsClient
```

modules/workflows/index.ts及包根公开上述类型／createWorkflowsClient；原生导入仅在workflowBridge.ts：
```typescript
import type { ComfyApiWorkflow, ComfyWorkflowJSON } from '@/platform/workflow/validation/schemas/workflowSchema'
import type { NodeId } from '@/types/nodeId'
import type { NodeExecutionId } from '@/types/nodeIdentification'
import type { ExecutedWsMessage } from '@/platform/remote/comfyui/execution/types'
export interface NativePreparedCanvas {
  guard: WorkflowGuard
  path: string
  workflow: ComfyWorkflowJSON
  prompt: ComfyApiWorkflow
  saved_content_token: string
}
export interface NativeRunOptions {
  scope: { mode: 'all' } | { mode: 'targets'; node_ids: NodeExecutionId[] }
  input_mode: 'reproducible' | 'reference'
  queue_number: number
  node_test?: NodeTestAssociation
}
export function installWorkflowBridge(client: WorkflowsClient): () => void
export function giveToAgent(projectId?: string): Promise<AgentContext>
export function noteManualChange(): void
export function applyLocalEdits(body: EditRequest): Promise<EditResult>
export function saveCurrentCanvas(guard: WorkflowGuard): Promise<SaveResult>
export function prepareRun(runId: string, guard: WorkflowGuard, options: NativeRunOptions): Promise<NativePreparedCanvas>
export function checkRunCanvas(guard: WorkflowGuard): Promise<AgentContext>
export function submitNativeRun(options: NativeRunOptions | NodeTestCreate): Promise<RunDetail>
export function receiveExecuted(message: ExecutedWsMessage): void
```

宿主内部节点用NodeId、运行定位用NodeExecutionId，线上保留原生字符串。NativeShell安装／卸载桥接；giveToAgent仅网页按钮，noteManualChange先使本地旧权失效再发页事件。queue_number沿原生该轮位置。
### 单次运行的固定顺序与异常副作用

1. submit_run以唯一run_id短事务建立preparing；同ID／原请求只查既有，不同内容RUN_ID_CONFLICT。原生batch每轮新UUID，origin由受控入口派生。
2. 宿主核target／content／control，提交控件值后仅一次beforeQueued／promoted准备、一次graphToPrompt（尚未科学执行）。用原生ChangeTracker／序列化语义核对转换等待期间无人工变化且参数／拓扑一致；UI本地化／规范化差异不要求字节相同，不建第二serializer。不确定异步语义返回GRAPH_CHANGED，不再准备或转换。
3. 原生saveWorkflow一次成功（新图先落实位置／关联）后再核对；失败则failed、零/prompt并保已发生文件／草稿。⑤经②准备实际ResolvedInputs及成本，固定RunContext、私有token和UUID prompt_id；已有固定字节不复制、保证不降级。长准备后checkRunCanvas仅核对，不改／重存／重算。
4. ⑤唯一POST原生/prompt；第15节最终guard核托管上下文与范围后才入队，返回真实prompt、终点／依赖／未执行部分。宿主只更新queued job／显示和一次afterQueued，不再api.queuePrompt双投。断连unknown先查固定run/prompt，不自动重投。
5. ③观察与原生事件更新同次run，按prompt归原图，当前页仅显示；实际完成图像自动轻量预览，失败与科学／停止事实分开。只有用户选择完整输出才用固定task交②保存。

运行正常转移为 `preparing→submitting→queued→running→completed/failed/cancelled`；准备失败可直接failed，已入队前实际移除可直接cancelled。有副作用结果不明转unknown，后续只按真实观察恢复到已证明状态，不从unknown自动发起新执行。取消请求本身不改变为cancelled。公开受理202之后的准备失败写入RunDetail.status/error，不把原202改成后来的HTTP错误；调用方按run_id查询。受理前的无效请求／冲突仍直接返回对应HTTP错误，不改已有同ID运行。

| 具体失败 | 对外结果及已发生事实 |
|---|---|
| 未绑定／页面离线／依赖桥接不可用 | 503 `PAGE_UNAVAILABLE`／`NATIVE_UNAVAILABLE`；不重选页面。已受理运行继续 |
| 目标、内容或控制过期 | 409 `TARGET_CHANGED`／`CONTENT_CHANGED`／`CONTROL_REVOKED`；未开始局部操作或提交时无新图变更／入队 |
| 转换等待中人工改图或无法证明采用值一致 | 409 `GRAPH_CHANGED`；本次运行失败，保留用户实际图，不再次准备或自动重提 |
| 已有部分局部操作成功后下一项失败 | 返回真实 `EditResult`，保留已应用操作及保存情况；不伪装整批回滚，不自动继续剩余项 |
| 保存文件成功、关联失败 | `SaveResult.file_saved=true/association_saved=false`，保存整体未完成并阻止运行；不谎称文件未变化，不自动覆盖恢复 |
| 原生拒绝输入／目标／节点或科学输入无法满足 | 422，保留所属模块 code／fields；运行记录 failed，不安装替换或缩小范围 |
| `/prompt` 或软件调用结果不明 | 运行 unknown／真实观察；先查询，不转成已失败并自动重跑，不提前释放使用中软件 |
| 完整输出已清理或结果保存失败 | 422 `OUTPUT_UNAVAILABLE` 或真实②错误；读取已有 task／asset 关联后核对，完整科学处理不重跑 |

错误沿公共envelope，跨模块保留code／fields／request_id。实现与测试归属统一见第17节。

~~~mermaid
sequenceDiagram
  participant A as 外部Agent／MCP
  participant D as FastAPI领域⑤
  participant E as ComfyUI原生桥接
  participant B as 目标网页宿主
  participant S as ③软件操作
  A->>D: runs(run_id,guard,scope)
  D-->>A: 202 preparing
  D->>E: page-command prepare_run
  E->>B: 原生WS apf.command
  B->>B: 原生准备／转换一次，核对后保存一次
  B-->>E: 同WS apf.result
  E-->>D: 实际准备／保存结果
  D->>D: ②固定输入与实际实现
  D->>E: POST /prompt
  E->>D: prompt-check，入队前核对
  D-->>E: 允许或明确拒绝
  E->>E: 原生校验／唯一队列调度
  E->>D: 受控节点实际调用
  D->>S: invoke_operation
  S-->>D: 实际观察与产物
  D-->>E: 科学locator及轻量UI输出
  E-->>D: 实际引擎事件，关页仍回传
  A->>D: 查询／选择完整结果保存
  D->>D: 仅所选结果交②登记
~~~

<a id="native-design"></a>

## 15. 原生消息、最终写入与引擎调用

### 2. 一个原生跨进程适配文件和组合根

#### 2.1 文件落点

| 文件 | 作用及允许依赖 |
|---|---|
| `src/astrophotoflow/interfaces/comfyui.py`（拟新增） | 单个具体适配文件：领域→引擎 HTTP、引擎路由／WS 消息分派、托管文件操作交接、入队前范围检查、节点注册／执行和事件转发。可以依赖 core 配置／认证和 contracts，不导入业务私有 ORM；不承载⑤运行规则或③软件实现 |
| `src/astrophotoflow/comfyui/proxy.py`（已有） | 保留浏览器→领域服务的明确 HTTP 白名单；新增真正公开的业务路由才逐项加入，不扩大成任意 URL 代理；使用当前采用地址 |
| `engine/ComfyUI/server.py`（已有） | 在既有 `/ws` 入站和关闭处调用有限分派；在 validate_prompt 后、queue.put 前调用受托管范围 guard；send_sync 触发有限运行事件观察。注册有限引擎桥接路由，其余 WS／队列行为保留，逻辑不堆入 server.py |
| `engine/ComfyUI/app/user_manager.py`（已有） | 托管图实际写／移动／删除前调用文件 guard，完成后回传事实；原生其余 userdata 行为保留 |
| `engine/ComfyUI/execution.py`（已有） | 仅增加一个私有执行 token 的原生敏感数据／hidden 输入交接；图执行、缓存、UI 输出仍归原生 |
| `src/astrophotoflow/interfaces/http/app.py`（已有） | 领域组合根：构造具体 HTTP 客户端，将有限适配函数绑定实际地址和认证后交⑤，装配领域内部回传路由、生命周期和维护检查 |
| `frontend/src/platform/astrophotoflow/workflowBridge.ts`（拟新增） | 宿主组合：当前原生图、原生 Store、ChangeTracker、原生转换、WS 命令处理、文件请求钩子、交给 Agent 按钮及人工运行入口 |
| `frontend/src/platform/astrophotoflow/NativeShell.vue`（已有） | 安装／卸载该宿主桥接；继续挂载原生 GraphView |
| `frontend/src/scripts/api.ts`（已有） | 注册 `apf.*` 事件类型和有限 userdata 前后钩子；复用现有 socket／HTTP，不建立第二连接 |
| `frontend/src/scripts/app.ts`、原生 `workflowService.ts`、`changeTracker.ts`（已有） | 在实际队列入口、文件操作结果和原生编辑事务处接薄钩子，继续使用原有编辑／保存／撤销能力 |

本稿所称 `workflowService.ts` 的实际路径是 `frontend/src/platform/workflow/core/services/workflowService.ts`；保存调用 `useWorkflowService().saveWorkflow(workflow)`。`ComfyWorkflow` 位于 `frontend/src/platform/workflow/management/stores/comfyWorkflow.ts`，不是旧路径。持久 ID 使用原生 JSON `id`，不使用 `ComfyWorkflow.instanceId`。另存新 ID 沿 `workflowStore.saveAs`，实际入口 `frontend/src/platform/workflow/management/stores/workflowStore.ts:220-229`。

业务模块不能反向导入 `interfaces/comfyui.py`。领域组合根只向⑤传具体调用函数，不创建 Protocol、插件容器或通用 RPC 框架。contracts 中的命令／结果类型只包含下节有限业务字段；HTTP 客户端与 PromptServer 类型留在适配文件，不进入 contracts。

此文件会被领域解释器和 ComfyUI 固定解释器分别导入。领域函数使用正式依赖 `httpx.AsyncClient`；引擎函数使用其 runtime 已有的 `aiohttp.web` 和原生 PromptServer。类型只放 `TYPE_CHECKING` 并用延后／字符串注解，依赖在相应入口局部导入；引擎导入节点包时不能被顶层 httpx／FastAPI 导入阻塞，领域导入适配时也不要求原生 `server` 或 aiohttp 已安装。不因此新增依赖或修改 runtime 锁。

#### 2.2 适配公开签名

```python
async def page_command(client: "AsyncClient", command: PageCommand) -> PageResult: ...
async def post_prompt(client: "AsyncClient", request: NativePromptRequest) -> NativePromptReply: ...
async def query_prompt(client: "AsyncClient", prompt_id: str) -> dict[str, JsonValue]: ...
async def apply_file_change(client: "AsyncClient", change: NativeWorkflowChange) -> NativeWorkflowChangeResult: ...

def register_native(server: "PromptServer") -> None: ...
async def receive_workflow_change(server: "PromptServer", request: "Request") -> "Response": ...
async def handle_socket(server: "PromptServer", socket: "WebSocketResponse",
                        message: dict[str, JsonValue]) -> bool: ...
async def forward_page_event(server: "PromptServer", socket: "WebSocketResponse",
                              event: NativePageEvent) -> None: ...
async def socket_closed(server: "PromptServer", socket: "WebSocketResponse") -> None: ...
async def guard_file(request: "Request", operation: Literal["save", "move", "delete"], path: str,
                     destination: str | None, content: bytes | None) -> FileWritePermit | None: ...
async def file_finished(permit: FileWritePermit, result: NativeFileResult) -> FileWriteResult: ...
async def guard_prompt(server: "PromptServer", request: NativePromptRequest,
                       outputs_to_execute: list[str],
                       node_errors: dict[str, JsonValue], *,
                       validation_error: JsonValue = None) -> None: ...
def observe_native_event(server: "PromptServer", event: NativeExecutionEvent) -> None: ...
async def forward_native_event(server: "PromptServer", event: NativeExecutionEvent) -> None: ...
def register_nodes() -> tuple[dict[str, type], dict[str, str]]: ...
async def execute_node(execution_token: str,
                       scientific_values: dict[str, ScientificValue | list[ScientificValue]],
                       parameter_values: dict[str, JsonValue]) -> NativeNodeResult: ...
```

`post_prompt` 只做原生 `/prompt` HTTP 适配；请求只能来自⑤已经固定的运行内容，MCP 不能调用它指定任意 URL。`query_prompt/cancel_prompt` 包装原生 queue/history/jobs 的真实观察，不推断完成或停止。有限返回中保留原生 `prompt_id/node_errors` 和业务错误，不把异常转为成功。

`PageCommand/PageResult` 放 `contracts/workflows.py`，复用⑤的 `target/content_token/control_token` 和原生 JSON 载荷；不再定义一组长期“命令实体”。同文件的两个原生传输类型只描述固定 RunContext 的提交投影，不新增运行权威：

| 类型 | 完整必要字段与含义 |
|---|---|
| `NativePromptRequest` | `prompt_id: UuidInput`；`prompt: dict[str, dict[str, JsonValue]]` 为原生执行图，每项的 class_type/inputs/_meta 继续遵守原生校验；`client_id: str` 为当前原生路由 sid；`extra_data: dict[str, JsonValue]` 只由⑤按固定运行构造，含私有 apf_execution_token 及原生编辑图／必要元数据；`partial_execution_targets: list[str] \| None = None` 只由已确认 scope 产生；`number: float \| None = None`、`front: bool = False` 仅保留原生排队位置语义 |
| `NativePromptReply` | `prompt_id: UuidInput`、`number: float`、`node_errors: dict[str, JsonValue]`；仅入队成功返回这个类型，拒绝走原生／业务错误响应，不用缺省 prompt_id 假装失败对象 |

`JsonValue` 为 JSON 值类型；原生执行图不重复定义完整业务 schema。`NativeExecutionEvent` 见第5.3节。⑤内部运行操作负责事务、状态、防重和选择范围，适配文件不复制这些规则。①的 `ConfigState/WorkbenchState/WorkbenchResult` 完整字段类型统一放①契约字段表，本节只引用这些公开类型，不能把前述摘要当作可直接生成代码的完整 schema。

该原生投影中的可空可选字段在未采用时不发送，尤其不能把 `number=None` 原样发送为 JSON null 交原生 float 解析；这只落实既有原生请求形态，不改变业务 PATCH 的省略／null 约定。

### 3. 选定的消息方向与页面存活

#### 3.1 固定路线

只复用原生 `/ws`。命令经领域→引擎受控 HTTP 进入，再用原生 socket 定向发送；浏览器结果经同一个 WS 返回，由引擎结束该次等待中的 HTTP 响应。无需新增领域 WS、长轮询或连接服务。

```text
外部 MCP／CLI → 领域 /api/v1 工作流操作 → ⑤
⑤ → POST engine /astrophotoflow/internal/page-command
engine → 原生 /ws 的 apf.command → 指定页面 workflowBridge
页面 → 同一 /ws 的 apf.result → engine
engine → 原来等待中的 HTTP PageResult → ⑤ → 调用方

用户页面动作 → 同一 /ws 的 apf.page → engine
engine → POST domain /internal/native/page → 领域应用组合根
组合根分派③软件确认或⑤画布操作 → engine
engine → 同一 /ws 的 apf.page_result → 该页面
```

内部 HTTP 均限定当前 workspace 的本机地址、校验 Bearer，不走浏览器公开代理白名单、不进入精简 MCP 目录。engine 向领域转发时附实际 socket 观察，不能原样相信浏览器填写的 clientId。浏览器不持有服务 Bearer。

#### 3.2 必要字段与有限动作

| 消息 type | 方向 | 唯一 data DTO；wire统一为 `{type, data}` |
|---|---|---|
| `apf.page` | 页面→engine→领域 | `NativePageEvent`，即下面有限页面动作的唯一载荷 |
| `apf.page_result` | 领域→engine→页面 | `NativePageReply`，回应同一个页面 event |
| `apf.command` | 领域→engine→页面 | `contracts/workflows.py` 的 `PageCommand`，完全复用⑤定义 |
| `apf.result` | 页面→engine→领域 | `contracts/workflows.py` 的 `PageResult`，完全复用⑤的 action 判别结果 |

`PageCommand` 以⑤接口稿为唯一结构：read 使用 target，其他动作使用 guard，结果是各动作的明确类型；本表不另外定义 page_id/target/token 平铺版。`NativePageEvent/NativePageReply` 也在 workflows 契约统一定义，仅命名既有页面动作载荷：event 带 `event_id/page_id/action`，首次 open 由 engine 分配 page_token，其后带当前 page_token；画布动作附⑤定义的目标／控制观察或对应请求，`confirm_software` 仅带 operation_id，允许无 workflow target。action 仍只取 `open/state/changed/handoff/submit_run/authorize_file/confirm_software/associate_workflow`。page result 回同一 event_id/page_id/page_token，带该动作的实际控制／保存／③当前动作结果或结构化错误；open 仅登记在线观察，不授权 Agent。命名不是新的业务实体，也不允许不同接入层各自复制一份字段版本。

`target` 使用既定 `project_id/workflow_id/page_id`，进入子图时附原生子图路径。`page_id` 由宿主桥接在该网页生命周期内创建，只定位页面；engine 在实际 socket 上登记它并产生新的随机 `page_token`，回包只能来自登记的这个 socket 和当前 token。页面自行填入相同 sid 不得接管另一个 socket 的页记录。token 不持久化，也不是身份认证或业务控制权。

页面连接登记本身不要求存在项目或工作流；`confirm_software` 只要求实际软件页及存活的 page/token，不套用活动图、画布 content_token/control_token 或 Agent 交回门槛。①控制、②导入等其他非画布业务仍按所属模块规则运行，不因为共用这条页面连接而依赖⑤活动画布。

`content_token` 由宿主创建为当前图的 opaque 随机标记：首次读取该图时产生；每次原生变更后，用已有 `ChangeTracker.graphEqual` 比较上一份当前状态和实际新状态，语义不等才更换。比较忽略 viewport 的 `extra.ds` 和原生执行顺序，保留节点布局、控件／参数、连线、分组和子图变化；不由 Python 重做跨语言 canonical JSON。服务将该当前标记连同已确认内容观察用于冲突检查，不把它解释为字节散列、永久 revision 或认证。离线已保存图可返回保存内容，不能凭服务自己造一个 token 冒充在线当前图。`control_token` 由⑤在真实 handoff／人工接管时更换并保存当前值，open／读取／重连不更换。④定义 JSON 的服务端内容校验与这套画布标记分别定义。原生比较依据 `changeTracker.ts:761-799`。

引擎只保留 `page_id→实际socket/page_token/活动目标观察` 和 `command_id→等待中HTTP响应` 的当前内存关联。浏览器为当前 page 事件保留有限等待关联。结果返回、连接关闭或等待结束即移除；无永久命令表、回执表和自动重放。页面关闭时 engine 向领域报告离线；即使这条通知丢失，下一次写入仍须在实际 socket 中核对，不能只信缓存 online。

原生/ws只有一个reader。open/state/changed/handoff是同socket有序短控制事件，领域处理不得反向等待页面或外层请求，reader有限await以免先前接管在后来的handoff之后乱序落地。submit_run/associate_workflow/authorize_file/confirm_software可能反向同页，使用连接内Task转发后立即释放reader，apf.result即时完成等待future，不能在reader等待领域结束。否则同一人工 submit_run 会等待领域，而领域的 prepare_run 又等待同 socket 的 apf.result，造成实际自锁。收到 apf.result 时即时校验 PageResult 并完成其 command_id 对应 future，不经过 page-event 的 HTTP 等待任务。转发任务完成后将 NativePageReply 发回原 socket 并移除当前任务关联，异常记录真实失败，不能伪造成功或自动重发。

`socket_closed` 清理该实际 socket 的当前 page-event 任务和待决 command future，标结果未知并移除旧关联；这只结束连接等待，不取消领域已经受理的运行或软件动作。之后按已有 run_id／operation_id 查询，不重放页面事件。这里没有新增命令队列、第二个 reader 或永久事件账本。原型必须证明同一 socket 上人工 submit_run→领域 prepare_run→浏览器 apf.result→原始 page_result 能完成，且关闭时不会留下等待不释放。

WS 重连换 `page_token`，旧 pending 结果成为未知而不是重放；读当前上下文取得新观察，不改变 SQLite 内的 `agent_allowed/control_token`，也不能用 state/open 建立新的 Agent 交回。已有同页面绑定须先核对活动图与离线期间人工变化；新网页/另一个图不能自动成为目标；服务重启可据SQL原绑定和真实同页恢复观察，不改允许状态。页面重连只更新当前连接观察，不复制控制权。

画布写入在领域处理前和宿主实际操作前均核对 target、内容和控制。切页签只改活动目标观察并暂停后续写／新提交，不改控制为人或 Agent；迟到命令不能落入新图。手动节点／参数／连线／布局／撤销先在宿主标为人工接管并阻止本地后续 Agent 命令，再经 `changed` 更新领域当前控制。离线时明确“接管尚未服务确认”，重连首先报告这项变化。Agent 自身有限编辑加入同一原生撤销事务，但不误当成人工接管。

#### 3.3 真实交回与人工提交

只有宿主的“交给 Agent”按钮处理当前真实用户动作时发 `handoff`；领域通过实际页面交接确认 project／图／内容后，绑定该 page 并更新当前 `control_token/agent_allowed`。MCP 目录没有 handoff 或恢复控制操作，公开 edits/runs 正文也不能自填 human 来源绕过检查。Origin、clientId、cookie 或 `confirmed:true` 都不单独视为真实交回证据。

原生人工按钮／快捷键／自动队列统一通过 `workflowBridge.submitNativeRun` 发 `apf.page action=submit_run`，engine 附当前 socket 事实，领域内部入口据该专用页面链路派生 human 来源；外部 `POST /workflows/{id}/runs` 按 agent 检查。`origin` 只能由组合入口传入⑤内部函数，不能由公开请求正文赋值。人工提交无需先把控制交回 Agent。连接能否可靠区分真实 UI 动作、伪造页面消息和脚本调用仍属原型门槛，当前不宣称这套来源证明已经成立。

软件安装／更新采用同一个具体计划的网页确认：公开软件 POST 只请求③当前动作并返回 202、`operation_id`、同份不可变 plan 和 `confirmation_url`，不视为已经确认或已经安装。软件页先读取并显示该 operation_id 的具体 plan，只有该页真实确认按钮发送 `apf.page action=confirm_software`，动作参数仅 `operation_id: UUID`；不新增 plan_token、客户端 confirmed 布尔值、审批实体或审批账本。engine 附实际 page/token 事实，领域 `/internal/native/page` 的应用组合根将这条专用消息交③执行当前动作，不经 MCP 可调用能力目录，也不让⑤拥有软件安装规则。

③在执行当前批准动作前重新核对该 operation_id 仍为当前 pending、展示的同份 plan 未替换、包／定义和已确认图影响校验未变且无运行阻塞；变化则返回 409 expired，不能重算计划后沿旧点击执行。`apf.page_result` 返回③当前动作的实际状态或 rejected／expired／错误，前端按事实显示，不把传输到达称作安装成功。公开 MCP 请求不能自带 true 或调用 confirm_software 完成敏感确认；确认不会授予 Agent 当前图写权。安装／更新执行及后续查询沿③当前动作能力，没有新增任务队列；确认来源能否可靠绑定平台软件页按钮仍须同一 UI 来源原型验证。

#### 3.4 错误与结果未知

目标／内容／控制或连接 token 过期返回 409；画布命令未建立所需绑定，或实际页面已离线／桥接不可用时返回 503 并给实际原因；对象不存在 404；不支持的编辑／控件／目标 422。有限命令正常返回实际结果；HTTP 或 WS 在副作用附近断开时只能标“结果未知”。Agent 先 read 核对，不自动重放 edits、保存或运行。局部批次返回已应用项目和失败位置，不承诺批次回滚。命令等待不是图运行队列。

### 4. 原生局部编辑、文件操作和提交

#### 4.1 宿主和文件请求钩子

宿主统一采用⑤的公开函数；api.ts另提供以下真实文件请求钩子。NativeFileResult／FileWriteResult字段见本节领域消费者。

```typescript
export function registerNativeFileHooks(
  before: (operation: 'save' | 'move' | 'delete', path: string,
           destination?: string, content?: string) => Promise<string | undefined>,
  after: (writeToken: string | undefined, result: FileWriteResult) => Promise<void>
): () => void
```

#### 4.2 托管图实际文件 guard

只在保存后更新关联不足以满足“实际写入处核对”。采用以下有限接入，不扩展成通用文件授权／锁服务：

1. `api.ts` 在 `storeUserData/moveUserData/deleteUserData` 的实际请求处调用上述 before 钩子，传本次实际 path、destination 和正文；宿主以 `authorize_file` 页面事件向⑤申请一次 `write_token`。它绑定操作、路径、原生图 ID、当前项目、拟写正文的 UTF-8 bytes SHA-256、已有文件 bytes 校验以及页面／控制观察，不由客户端自行声明已确认。该正文摘要只比这次真实传输字节，和 opaque 画布 `content_token` 不混用，不定义新的 JSON canonicalization。
2. 该 token 仅附于这一次 userdata HTTP 请求的 `X-APF-Write-Token`；不使用全局“当前保存 token”，避免并发自动保存、改名和其他图互串。未经平台管理的 userdata 不得到 token，保持原生行为。
3. `user_manager.py` 的 POST userdata、move、DELETE 实际修改前调用 `interfaces/comfyui.py.guard_file`。适配调用领域 `POST /internal/native/file-check`；领域按已有关联的源路径／图 ID 和 token 判定是否托管，校验实际正文和目标，检查一次授权仍有效。已托管图不能靠省略 header 变为普通文件。未托管新图首次保存没有permit，保存后按[首次保存专节](#首次保存、项目关联与交给agent)明确关联；不得先要求不存在的控制token，或由普通保存自动授Agent权。
4. 对托管操作，guard 与紧接的原生文件修改按该引擎内当前操作串行完成；不在服务端持有数据库写事务等网络或文件。原生保存仍使用临时文件和 `os.replace`；move/delete 仍用原生实现。该临界区不能被解释为跨 SQLite 和文件的分布式事务。
5. 已托管图的原生文件成功后经 `POST /internal/native/file-finished` 回传事实，⑤才更新关联，托管图另存接受原生新 ID，删除清理专属预览。未托管首次保存沿前项专节的associate_saved_workflow，不双发file-finished建立同一关联。after 钩子据实际 native 结果展示保存与关联分别状态。文件失败不更新为已保存；文件已成功但关联回传失败时明确分开，先读文件与关系核对，不声称已回滚或自动重放。

`write_token` 只存在当前业务操作的短命内存关联。页面写入的 token 随操作、页面连接或当前控制失效；下节受控维护的 token 由应用确认流程逐文件产生，绑定当前批准动作及准确文件内容，不要求每个被改图各有活动页面或发 authorize_file。两种来源都由领域保存的当前 permit 判断，客户端不能自填来源类型扩权；不加入运行记录、永久审批或永久文件回执。匹配到已有托管图的最终 guard 必须覆盖原生快捷保存／自动保存／改名／另存／删除和受控维护，不仅覆盖 MCP。源码实际入口：`app/user_manager.py:364,403-408,427,437`、`scripts/api.ts:1644,1672,1714,1730,1741`。

#### 4.3 唯一运行顺序

见[⑤详细设计](#workflows-design)：一次准备／转换，原生保存一次成功后由领域最终提交，不双投。

#### 4.4 原生校验之后、实际入队之前的范围 guard

原生 `validate_prompt` 只要仍有有效终点，就可能允许丢弃无效终点后入队；`node_errors` 会随已入队响应返回。⑤拿到响应之后才检查为时已晚。既有行为证据是 `execution.py:1205-1258` 记录 good_outputs／dependent_outputs 并忽略失败输出，`server.py:1203,1222-1230` 立即使用有效 outputs_to_execute 调 queue.put。

在 `server.py` 中调用现有 `execution.validate_prompt` 后、任何 `prompt_queue.put` 之前调用 `interfaces/comfyui.py.guard_prompt(server, payload, valid[2], valid[3], validation_error=valid[1])`；payload是原生on_prompt／replacement实际处理后的NativePromptRequest。不再次校验、不复制图遍历或调度器。携带私有token或含实际平台注册节点的请求都核对；缺token不能作为裸任务绕过，其他原生请求保持。

guard 通过受认证 `POST domain /internal/native/prompt-check` 将实际提交投影、原生已校验的 `outputs_to_execute: list[str]` 和 `node_errors: dict[str, JsonValue]` 交⑤。⑤以 token／prompt_id 读取已固定 RunContext，核对实际执行图、保存的请求范围／明确终点、节点绑定与此次投影相符；有限范围判定直接消费原生校验结果，不重新实现 validate_prompt：

- 请求中的明确目标不存在、不属于当前支持的原生可执行目标，或原生实际终点集合与本次固定终点集合不同，返回 `422 RUN_SCOPE_UNSUPPORTED`，附请求终点、实际终点和未满足部分。
- 请求范围内节点的 native node_errors 非空，或其 dependent_outputs 涉及本次固定终点，返回 `422 RUN_VALIDATION_FAILED`，保留原生 node_errors；即使其他终点有效也不排队。
- token／prompt_id／固定执行内容不匹配返回 `409 RUN_CONTEXT_CONFLICT`；内部检查不可用返回 `503 NATIVE_CHECK_UNAVAILABLE`。这些失败发生在 queue.put 之前，原生队列不出现该运行。

`guard_prompt(...) -> None` 的成功表示允许继续使用原生已算出的 outputs_to_execute，任何拒绝由引擎适配转换成对应 HTTP 错误后立即结束 /prompt。scope=all 的“固定终点”是本次明确保存的原生终点集合，不是把所有普通节点标为 OUTPUT_NODE；targets 仍包含必要依赖，不在 guard 中发明中间节点终点转换。⑤始终是最终 POST /prompt 的调用方；这里补的是引擎最终入队前的检查点，不是第二次提交或第二队列。

这条链路是领域→引擎→领域的实际嵌套请求：⑤外呼 /prompt 前已经短事务保存固定上下文和“正在提交”状态，等待引擎响应时不能持有供 prompt-check／事件／实际节点调用使用的数据库事务或跨请求锁。prompt-check 读取这份既有上下文并立即判定，不等待外层 submit 返回；原生事件／实际节点调用先于 /prompt 响应到达时，同样按已固定 prompt_id/token 关联，不因尚未收到受理回包而拒绝真实调用。

#### 4.5 已确认软件／节点维护的受控保存入口

`ApplyFileChange` 不是没有实现落点的任意 callback。领域组合根将 `interfaces/comfyui.py.apply_file_change` 绑定已核对的引擎 `httpx.AsyncClient` 后交⑤；该函数只调用受控 `POST engine /astrophotoflow/internal/workflow-change`。引擎 `register_native(server)` 注册该单一 POST，交 `receive_workflow_change(server, request)`，检查当前 workspace Bearer。此入口不进入浏览器公开代理或 MCP 能力目录，不接受普通 Agent 借维护名义编辑任意图。

下列类型放 `contracts/workflows.py`，只承接一次已批准文件写入，没有独立可编辑图实体或维护计划对象：

| 类型 | 完整字段与语义 |
|---|---|
| `NativeWorkflowChange` | `operation_id: UuidInput` 为所属模块当前已批准动作；`impact_token: str` 为该动作确认时的⑤图影响校验；`project_id: UuidInput`、`workflow_id: UuidInput`、`path: str` 为已批准的已保存原生图及 userdata 相对路径；`base_file_sha256: str` 为预览／确认采用的当前文件 bytes SHA-256；`json_text: str` 为⑤构造、已序列化的一份拟保存原生 JSON 正文；`write_token: str` 为领域应用确认流程对此准确文件及 UTF-8 正文签发的一次 permit |
| `NativeWorkflowChangeResult` | `operation_id: UUID`、`project_id: UUID`、`workflow_id: UUID`、`path: str`；`file_saved: bool \| None`、`association_saved: bool \| None`，None 只表示缺少真实结果而未知；`saved_file_sha256: str \| None` 为实际成功保存时的 bytes 校验；`error: ErrorDetail \| None = None`。文件成功但关联失败分别表达，不用虚构 page_id 构造在线 SaveResult |

⑤在已确认的 `WorkflowChange/WorkflowImpact` 范围内读取当前保存 JSON，只修改这次 APF 节点、默认参数及允许变化的端口连线；其余原生字段原样保留。⑤将这份结果序列化成 `json_text` 一次，确认流程签发的 write_token 绑定该正文的 UTF-8 bytes 摘要；引擎不得再解释 change、重建图或生成另一份 JSON。`operation_id/impact_token` 不是调用方自行声称已确认：领域应用必须能定位仍有效的当前批准动作及确切图清单，才能签发 permit。软件确认仍来自平台软件页，节点更新仍沿所属模块已确认流程；不增加通用审批服务。

实际调用和副作用固定为：

1. 应用组合确认影响后调用⑤，由⑤逐图重新核对已保存身份／路径、原文件 bytes、批准的影响校验和已知页面草稿。任何相关页面为 unsaved／同步未知，或保存内容、定义、确认影响已变，均在写入前返回 409；不存在相关活动画布本身不是阻塞。permit 来自这个已批准动作，不要求逐图页面 authorize_file，不取得 Agent 控制权。
2. `apply_file_change` 把准确 `NativeWorkflowChange` 发往上述内部引擎入口；引擎只接受批准范围中的既有 workflow 路径，不能用于创建、另存、改名、删除、任意路径或任意 HTTP 方法。
3. 引擎入口用同一引擎现有 aiohttp 客户端向自身原生 `POST /userdata/{encoded_path}` 发 `json_text` 的原始 UTF-8 正文，附本次 `X-APF-Write-Token`，使用固定本机原生地址和工作台用户上下文；不接受正文指定 URL 或用户，不调用 Path.write_text／open 自建写入器。原生 origin 检查使用该引擎的实际本机来源，不放宽来源列表。
4. 原生 user_manager 的同一个最终 guard 调领域 file-check，重新核对 token 所属已批准 operation_id、impact_token、该图／路径、旧文件和拟写正文的 bytes 校验，以及维护期间出现的草稿／新变化。随后仍由原生临时文件及 os.replace 保存，file-finished 回传真实保存／关联结果。领域服务或引擎在这条嵌套调用中都不能持有等待回调所需的数据库事务或跨请求锁。
5. native userdata 的实际结果和领域关联结果组成 `NativeWorkflowChangeResult`，⑤据此返回逐图 `WorkflowChangeResult`。维护保存结果不强制在线 WorkflowTarget/page_id；普通在线 SaveResult 和它不能靠伪造页面混用。成功只表示已保存图及关联的实际结果，不宣称所有页面已经加载；现有页面下次交互重新核对保存内容，未同步草稿不被替换，也不抢视图。

错误与失败边界：批准动作／影响／旧文件／草稿或一次 permit 已失效为 409；图／关联不存在为 404；越出批准路径或非本次 APF 变更为 422；最终 guard／引擎暂不可用为 503。写入前拒绝不得产生文件副作用。原生写失败保留真实错误；文件已经成功而 file-finished 失败时返回 `file_saved=true`、实际关联状态及错误，不能把它描述成已回滚。若 userdata 请求或回执在不能判断的位置断开，结果保留 None／未知，先读取实际原生文件和领域关系核对，不自动重放或重算。某图已保存、后续图失败时保留各图事实，不承诺跨图事务；正在运行的固定实现和旧运行事实不改。

该入口仅写已批准的已保存图，不加载画布、不调用 graphToPrompt、不排队执行；没有新增 headless editor、第二转换器、通用文件 RPC 或维护任务队列。它与普通 Agent 依赖活动页面的改图接口职责不同，但共享同一个原生 userdata 最终 guard。

### 5. 白名单节点包与 engine→③受控执行

#### 5.1 布置与加载

`core/workbench.py` 的 initialize／安装网页资源同处写入固定薄引导至：

```text
workspace/comfyui-data/custom_nodes/astrophotoflow_nodes/__init__.py
```

固定内容为以下导入和原生映射赋值；没有把定义或执行代码生成到 workspace：

```python
from astrophotoflow.interfaces.comfyui import register_nodes
NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS = register_nodes()

```

core 只写固定文本，不导入 interfaces 或引擎；不新增 vendor 资源、package-data 配置或 `engine/ComfyUI/custom_nodes` 产品源码树。启动继续保留 `--disable-all-custom-nodes`，增加 `--whitelist-custom-nodes astrophotoflow_nodes`，仍禁用任意扫描包。UI 继续来自完整网页构建，不从该包加载第二个应用。

`register_nodes()` 在原生注册时通过受认证领域内部 `GET /internal/native/definitions` 取④实际定义和软件就绪观察，返回原生类映射；definition_id 为 UUID 时注册 class_type 为 `APF_` 加该 UUID 的无连字符 hex，显示名仍用定义名称。④权威仍是 `workspace/nodes/{definition_id}.json`；引擎不读 JSON 后自行猜业务语义，也不写定义或 SQLite。③配套定义和用户自制定义用已确认来源字段区分，③卸载不删除自制定义。

首次只注册受支持的③软件操作节点与所需固定科学引用节点；原生 INPUT_TYPES／RETURN_TYPES／控件和执行类接口继续使用。保存、实际注册、前端定义刷新和可执行状态分别报告。`register_nodes` 不执行科学处理。动态新增／修改后的刷新或受控重启条件，以及运行中已采用定义不变均待原型；本稿不额外注册一个未经验证的热加载路由。

已核对：工作台 `--base-directory` 指 `workspace/comfyui-data`，原生 custom_nodes 路径从该 base 派生；白名单在 prestartup 和正常加载都生效。证据：`core/workbench.py:282-297`、`folder_paths.py:45`、`comfy/cli_args.py:218`、`main.py:607`、`nodes.py:2304-2314,2381-2396`。

#### 5.2 私有执行 token 和实际调用方向

```text
⑤固定run/prompt/节点内容及私有execution_token
  → 最终 POST engine /prompt
  → 原生队列调度白名单平台节点
  → interfaces/comfyui.py.execute_node
  → POST domain /internal/native/call
  → ⑤核对已保存运行上下文
  → ③公开执行能力
  → 实际科学输出／观察交⑤保存
  → engine原生节点返回科学引用及必要UI输出
```

`/internal/native/call` 正文为原生实际 `prompt_id/node_execution_id/list_index`、`execution_token`、`scientific_values` 和 `parameter_values`。`node_execution_id` 从原生执行上下文的 node_id 原样映射，保留子图执行定位；身份不取页面填写的 node_id。动态连线值必须来自这次原生求值，不能假定保存图时已经知道上游运行结果。

`ScientificValue` 统一引用 `contracts/inputs.py` 的唯一类型定义，不在引擎适配或本稿另造别名：

- `ScientificValue = InputReference | OutputLocator`；`InputReference` 为固定 asset／dataset 引用，字段沿②科学输入契约。
- `OutputLocator`：`kind="run_output"`、`run_id`、`node_execution_id`、`output_index`、`member_index`，类型／可省字段沿 inputs.py；不改成另一个 kind 或普通画布 node_id。
- `scientific_values: dict[str, ScientificValue | list[ScientificValue]]`：按已保存端口名传一个值或有序组；④定义决定单个／组及类型，不能靠数目猜语义。固定 dataset 引用由②解析已选成员／顺序，不自动追加。
- `parameter_values: dict[str, JsonValue]`：按本次控件和连线解析的有效 scalar／参数值；每项按已保存操作 schema、节点映射和连接核对，不接受不相干参数覆盖。`JsonValue` 是 JSON 值类型，不是任意 Python 对象。

⑤按 prompt_id 定位已准备并提交的 run，核对 token、保存的节点 binding／schema／拓扑、实际请求范围和运行状态；从保存的 binding 取得③ operation，解析已准入资产或本 run 已检查输出，按③ `SoftwareInvocation` 交 `inputs: dict[str, list[ResolvedInput]]` 和实际参数，各端口组保持明确顺序。`ResolvedInput` 沿②的资产／运行输出变体，②不读⑤ ORM。实际端口值和参数随这次调用写入同次运行事实。文件路径只在②内部解析结果和受控③调用中出现；节点间只传轻量引用，不传 tensor、完整图像或科学字节。工作目录由⑤固定 `workspace/runs/{run_id}/work`，原件只读。正文不能另带 shell 命令、下载 URL、任意 operation/workdir/path；S6 跨 run 固定结果续跑不提前扩大到本接口。

每个 run 的私有 token 只支持这一受托管调用边界，关联 run_id/prompt_id，不进入网页／MCP／运行导出／日志。传引擎时放专用 `apf_execution_token`：将其加入原生 `execution.SENSITIVE_EXTRA_DATA_KEYS`，复用 `server.py` 队列敏感数据分离和 `main.py` 执行时合回；不可放在普通 extra_pnginfo／工作流 JSON 或复用 ComfyOrg 凭据字段。平台 V1 节点增加一个 `APF_EXECUTION_TOKEN` hidden 输入读取它；仅此一项原生交接增量，不新增执行上下文框架。

hidden参数名固定为`apf_execution_token`，自建节点的输入／参数不能占用该内部键。现有execution.py:633–656会把input_data_all全部格式化进current_inputs，再由约704–714行发送execution_error；因此本次执行文件增量还必须在格式化、错误事件／history及相应日志之前剔除这个新增私有hidden键。只加入SENSITIVE_EXTRA_DATA_KEYS不能保护此异常路径。用一次真实受控节点失败测试核对queue/history/WS异常/日志/图均不含该token字面值，不改变其他原生节点错误格式，也不新增身份系统。

原生已有 `CurrentNodeContext`，可取得真实 prompt/node/list index；不使用全局 last_prompt_id 猜当前调用。证据：`comfy_execution/utils.py:4-19`、`execution.py:302-314`。敏感数据现有处理：`execution.py:162,216-228`、`server.py:114-116,1224-1229`、`main.py:376-383`。实际实现还须检查 history／错误等所有原生公开返回也不泄露新增 token，不能只验证 queue。

③执行成功／失败、日志、实际输出和停止观察经⑤保存为同次运行事实；同一运行节点调用未知或已经发生时先核对，不能因内部 HTTP 超时再执行一遍。长调用不持有数据库写事务。取消仍针对该 prompt 和③实际调用，不用全局 interrupt 误停其他运行。白名单节点没有 token 或上下文不匹配时在实际软件调用前失败，因此裸 `/prompt` 的任意 extra_data 不能自行创建托管运行。

#### 5.3 无浏览器时的运行观察和预览回传

页面 WS 只承接在线画布控制和显示，不是运行记录的必经环节。已受理运行在网页关闭后仍须把终态、日志关联、实际产物检查和完成预览交⑤，因此在 `PromptServer.send_sync` 保留原生消息发送的同时，加一个有限托管事件观察钩子调用 `observe_native_event`，最终以受认证 HTTP `POST domain /internal/native/event` 交⑤。内部 HTTP 复用引擎现有 aiohttp 客户端／事件循环；没有新的 WS、事件队列、常驻服务或永久事件账本。

`NativeExecutionEvent` 在 `contracts/workflows.py`，字段为 `prompt_id: UuidInput`、`event: Literal["execution_start", "execution_cached", "executing", "executed", "execution_success", "execution_error", "execution_interrupted", "progress", "progress_state", "logs"]`、`data: dict[str, JsonValue]`。只转发具有真实 prompt_id 且属于已登记托管运行的这些事件；不把全局日志或没有关联的消息按最后一次 prompt 猜归属。节点定位和错误／UI输出继续消费原生 data，token 不进入事件。

`observe_native_event` 只把这次有限 HTTP 转发安排在原生 server.loop 中并立即返回；转发失败记录可诊断错误，不阻塞 send_sync、不替换原生 UI 消息、不把元数据传递失败变成图调度失败。`forward_native_event` 的失败可观测，但不自动重试或重放；这不是可靠事件投递承诺。⑤按照 prompt_id 定位原图和运行，幂等地核对当前事实；event 先于 /prompt HTTP 响应到达也不能丢到当前其他图。

⑤收到终态／executed 后检查实际输出清单和科学文件，再更新必要运行状态及完成预览索引；③调用日志和本次运行日志路径保持关联。自动缩图在本次实际执行完成的图像节点产生轻量 UI 输出，不依赖浏览器回执、不重跑图、不扩大分支。缓存回放不是新处理；progress/progress_state 只更新当前可观察进度，不逐帧持久化。专属预览落盘和索引按运行／节点执行 ID／输出位置保存，完整科学结果仍只在用户选择时交②。

完成 JPEG 预览固定放 `workspace/output/apf-previews/{run_id}/{preview_id}.jpg`；原生 `ui.images` 使用 `filename="{preview_id}.jpg"`、`subfolder="apf-previews/{run_id}"`、`type="output"`，继续走原生 `/view`。⑤ SQLite 索引记录同一份文件和输出定位，不另放一份到 runs 目录、不新增文件根挂载。科学工作目录仍为 `workspace/runs/{run_id}/work`；轻量预览位置不改变科学输入或结果保存规则。原生消费依据 `frontend/src/stores/nodeOutputStore.ts:143-150`。

事件转发中断、网页关闭、领域或引擎重启后，⑤查询接口必须用已保存 prompt_id 经 query_prompt 核对原生 queue/history/jobs 及③实际调用，而不是等待浏览器补发；查询不自动重复提交、软件调用或事件投递。history 已清除、进程重启或证据不足时保留 unknown 及缺失依据，不推断完成／失败，不用内存 history 永久兜底。已记录状态和已存完成预览仍可查询；丢失且不能核对的预览不能宣称已经补齐。

### 6. 精确原型接口与阻塞出口

下表是必须补证据的原型，不是当前已支持行为；不据此改变已确认产品规则。

| 原型 | 明确文件／接口 | 通过条件与阻塞出口 |
|---|---|---|
| ①默认目标与当前采用值 | core/config.py、workbench.py、HTTP CLI、proxy.py、AssetClient；settings/workbench、internal/maintenance | 配置默认位置正确；保存后当前连接／并发保持，重启采用新值；双服务自动端口核对及写回不覆盖新保存；服务未启动时本机MCP仍能控制。阻塞①最低联调出口 |
| 页面和真实 UI 交回 | workflowBridge.ts、api.ts、server.py入站钩子、interfaces/comfyui.py；apf.page/handoff、page-command | 两个页面不会串目标；自报 clientId／human／confirmed 不能授权；真实按钮来源可验证；旧socket／token、切页签、离线人工变化、重连不恢复已撤销控制。阻塞最小在线编辑和完整双入口 |
| 同socket嵌套命令 | 原生ws单reader、handle_socket／forward_page_event／socket_closed | 人工apf.page submit_run等待领域时，reader仍能即时接收同socket的prepare_run结果；原page_result可完成；关闭清理待决Task／future并保留未知，不自动重放、不取消已受理运行。阻塞人工托管运行与真实桥接出口 |
| 软件页敏感确认 | 平台软件页确认按钮、apf.page/confirm_software、domain internal/native/page 应用组合根、③当前动作 | MCP仅请求并拿202／confirmation_url；软件页显示同一operation.plan后真实确认才执行；伪造confirmed或MCP调用确认无效；旧plan／包／图影响变化返回expired而不沿旧点击执行；无活动图仍可安装／更新。阻塞软件安装更新双入口出口 |
| 原生保存和实际文件 guard | workflowService、api userdata hooks、user_manager、file-check／file-finished | 快捷保存／自动保存／新图／另存／改名／删除都覆盖；并发手改或内容变化使旧许可拒绝；文件已成但关联失败不假报回滚，之后能读取核对；普通userdata保持。阻塞项目原生图保存联动 |
| 已批准维护文件保存 | ⑤构造APF局部变化→typed apply_file_change→engine internal/workflow-change→原生userdata同一guard | 无活动canvas也只改批准的已保存图；不要求逐图页面authorize_file；未同步草稿／影响／旧文件变化或过期permit在写前拒绝；其余原生字段保留；文件／关联／每图结果及未知如实表达。阻塞软件／节点更新影响落地 |
| 一次准备保存后入队 | app.queuePrompt、workflowBridge.prepareRun、graphToPrompt、⑤submit；apf.command prepare_run/check | beforeQueued只一次；applyToGraph及异步serializeValue之后保存；保存false／异常不提交；执行参数／拓扑一致，纯规范化字段不误冲突；三种人工入口和MCP只由领域最终POST一次。阻塞真实托管运行 |
| 最终入队范围 | server.py validate_prompt→guard_prompt→queue.put、internal/native/prompt-check | 一好一坏两个请求终点时整个托管提交拒绝且队列无该prompt；不支持目标不被忽略；固定内容冲突／内部检查失败均不入队；非托管原生行为保留。阻塞范围不缩小的真实运行出口 |
| 白名单装配和更新 | initialize固定薄引导、interfaces/comfyui.register_nodes、原生nodes注册 | 只加载平台目录；定义JSON保存后实际注册／刷新条件明确；缺依赖可见；参数新默认和端口重排规则成立；运行中实现不被改写。阻塞首节点联调，未证明热加载时不宣称支持 |
| 受控软件调用 | execution敏感hidden、CurrentNodeContext、internal/native/call、⑤→③公开入口 | 原生真实prompt/node与运行快照相符；伪造或缺token阻止实际调用；token不进queue/history/图/日志/MCP；未知不自动重放；真实取消与停止分开。阻塞首个实际软件闭环 |
| 无网页运行观察 | PromptServer.send_sync→observe_native_event／forward_native_event→internal/native/event、⑤query_prompt | 关闭网页后已有运行仍更新必要状态／日志／实际产物与完成预览；A结果不归B；HTTP观察失败不阻塞原生执行和UI，之后查询核对且未知不猜；不逐帧落库。阻塞关页继续运行与持久结果出口 |
| 原生目标、缓存和预览 | 既有executionUtil／execution、⑤运行关联和UI事件 | 目标含所需依赖，范围不静默缩小；cache-none等机制真实避免跨运行科学复用；自动缩图不加终点、不增执行分支，A结果归A。阻塞真实处理与自动预览出口 |

本稿未决定首软件／准确发行版、目标中间节点实现、缓存采用方式、科学缩图算法或热加载细节；这些项在相应原型／实施任务锁定。Python与复合、节点分发、完整比较和Judge仍按既定后续范围，不因本稿新增接口或空目录。

### 实际节点加载事实的生产者

`interfaces/comfyui.py.register_nodes()` 从实际采用的 `SavedDefinition` 生成类时，在类上保存静态 `APF_DEFINITION_ID: UUID` 和 `APF_CONTENT_TOKEN: str`，随后仍由原生 loader 注册进 `nodes.NODE_CLASS_MAPPINGS`。打标记或保存 JSON 本身都不能报告 loaded；标记不是动态读取 JSON 的 property。固定科学引用节点的 registry key 统一为 `APF_DATA_REFERENCE`，由同一白名单包注册。

新增只读 `GET engine /astrophotoflow/internal/node-loads`，重复 query `definition_id=<uuid>` 指定要观察的定义。`register_native(server)` 注册该有限路由，校验当前 workspace Bearer，不进入浏览器公开代理或 MCP 目录；不写定义、registry 或 SQLite。

```python
async def read_node_loads(client: "AsyncClient", definition_ids: Sequence[UUID]) -> NativeLoadReport: ...
async def receive_node_loads(server: "PromptServer", request: "Request") -> "Response": ...

async def get_node_details(
    definition_id: UUID, *, database: Database, settings: Settings,
    native_client: "AsyncClient"
) -> NodeDetails: ...
```

引擎对每个请求 ID 只读取真正的 `nodes.NODE_CLASS_MAPPINGS['APF_' + definition_id.hex]`：不存在则返回 not_loaded／token=None；存在且两个静态标记可识别、定义 ID 相符时返回 loaded 和**类上实际 token**。标记缺失或身份不可确认则返回 unknown／token=None 和实际原因，不能读 `workspace/nodes` 补值。仅 registry 缺项不能推断一次加载曾经 failed。`data_reference_loaded` 直接检查实际 registry 中 `APF_DATA_REFERENCE` 是否存在；没有另一个推测性的就绪索引。

适配查询失败返回 503 `NATIVE_LOAD_UNKNOWN`，不合成一份空 report 冒充“确定未加载”。`app.get_node_details` 读取④当前 `SavedDefinition`、③对应包／操作的真实就绪和这次 `read_node_loads`；已知连接／查询失败时详情保留定义和软件事实，将 load 明确置 unknown／None 并给出原因。无效 query UUID 422；不存在定义仍按④404，不伪造已保存节点。

NodeDetails的ready／reason由组合根按本次实际观测提供。ready 只在 `software_ready`、load.state=loaded 且 **实际类 token 等于当前 SavedDefinition.content_token** 时为 true；其余为 false 并说明未加载、加载内容较旧、软件未就绪或观察未知。当前 JSON 更新但 registry 仍是旧类时，load 仍如实报告旧 token，不能改报新内容 loaded。最近测试继续独立查询和显示；没有测试／测试失败不成为保存或 ready 的额外门禁。

领域组合根将这个具名 async 函数装配给节点列表／详情及保存后的详情查询；`NodeUpdateResult` 也使用同一真实报告，不把保存成功推成注册成功。图运行预检对本次采用的④定义读取同一 registry 事实和③就绪，token 不匹配／not_loaded／unknown 时阻止提交并给准确原因；使用固定科学引用节点的图还要求 report.data_reference_loaded。查询失败不猜就绪，不通过自动刷新、重启或换实现静默恢复。

最小验证：①保存定义但 registry 无类，not_loaded／ready=false；②registry 类仍带旧 token，load 报旧值且 ready=false；③冷启动经真实白名单 loader 注册当前类后 loaded／token相符，③就绪时 ready=true；④查询断连为 unknown；⑤固定科学引用类缺失时相关图预检阻塞。均需真实 registry 和领域组合验证，不能以 mock 返回文件 token 代替；是否可热刷新仍留既定原型，不新增能力选择。

### 首次保存、项目关联与交给Agent

**拟实现闭合；不支持Agent编辑未保存临时图。** GUI先明确选择项目并完成原生保存，再建立⑤关联，最后由真实“交给Agent”动作交回控制。未托管文件保留原生保存行为，没有APF permit，也不预建Workflow行／临时control_token。

#### 最少类型与公开入口

以下追加到现有`contracts/workflows.py`，沿StrictModel／UuidInput及当前WorkflowSummary，不增加平行Target／Guard类型。

| 类型 | 字段 |
|---|---|
| `AssociateSavedWorkflow` | `project_id: UuidInput`、`workflow_id: UuidInput`、`path: str`、`file_sha256: str`、`content_token: str`；path为实际保存后的userdata相对路径，file_sha256为该实际文件原始bytes的SHA-256，content_token仍是宿主当前内容标记 |
| `AssociateWorkflowResult` | `workflow: WorkflowSummary`、`control_token: UUID`；此token是当前人工控制值，不表示已经handoff或允许Agent写入 |

`modules/workflows/public.py`新增唯一入口，app内部路由只装配调用，不写ORM：

```python
async def associate_saved_workflow(
    database: Database, settings: Settings, body: AssociateSavedWorkflow,
    page_command: PageCall, *, page: PageObservation,
) -> AssociateWorkflowResult: ...
```

1. 调用`data.public.get_project(database, body.project_id)`核对真实项目，沿其既有范围／错误，不导入Project ORM或调用data路由。
2. `page`必须来自NativePageForward的真实引擎连接。以该page_id及正文明确的项目／图构造现有read目标，通过PageCall读取当前实际页面；不要求尚不存在的WorkflowGuard／control_token。核对在线／活动、原生当前图UUID和content_token，不能只信缓存PageObservation或浏览器自报saved。
3. 按原生已有userdata路径范围读取`settings.workspace/comfyui-user/default/<path>`实际文件。核对文件存在、其原生JSON `id`等于workflow_id、原始bytes SHA-256等于file_sha256，并与该页面实际保存后的图／位置一致；不重新规范化JSON来猜文件hash，不写／复制／替换图内容。
4. 页面／文件核对完成后才短事务建立唯一Workflow关联：原生workflow_id、project_id、实际path及saved_content_token；生成当前control_token，`agent_allowed=False`、`bound_page_id=None`。不持事务等待页面或文件读取，不宣称SQLite关联与原生保存是一个原子事务。
5. 已有同图同项目同路径只返回当前关联／control_token，不改控制；同workflow_id或path已归另一关联则409，不自动改项目、覆盖、另存或迁移。关联读取／重复消息不构成handoff。

#### 同一原生连接的专用事件

在现有`NativePageEvent.action`追加`associate_workflow`，其`payload`唯一为`AssociateSavedWorkflow.model_dump(mode='json')`。外层event_id/page_id/page_token、WS `{type, data}`包装及实际socket核验保持；首次关联允许外层target为空，不以不存在的SQL关联或控制nonce作为前置。

`POST /internal/native/page`收到该动作后，把引擎核验的page和PageCall交给上述⑤入口。`NativePageReply.result`追加`AssociateWorkflowResult`分支，必须回应同一event_id/page_id/page_token；错误仍用ErrorDetail，不新增关联回执／任务资源。

该动作只由GUI首次关联流程发出，不注册公开HTTP、CLI或MCP能力，不进入能力目录；关联不编辑图、不执行图，也不因连接重开／读取而授予Agent控制。

#### 宿主giveToAgent顺序

在现有`workflowBridge.ts`把公开签名明确为：

```typescript
export function giveToAgent(projectId?: string): Promise<AgentContext>
```

1. 对未关联的新图，要求GUI先选择明确projectId（省略时由GUI选择），调用现有原生saveWorkflow／首次saveWorkflowAs并等待成功。取消项目选择、取消另存、保存失败均停止，不用Agent edits代替首次保存。
2. 保存成功后从实际保存后的ComfyWorkflow／原生文件结果取UUID、path和真实bytes SHA-256；另存可能换UUID，不能使用保存前临时ID或instanceId。发送associate_workflow并等待对应成功回复，完成关联仍保持人工控制。
3. 再以关联结果及当前真实页面发既有handoff；⑤按当前目标／内容核对后更新控制nonce并允许Agent，返回AgentContext。首次关联成功不自动等同交回；handoff失败则没有Agent写权。已关联图沿原handoff流程；传入另一projectId不能隐式改变归属。

文件bytes基准在原生实际载入文件时取读取的原始bytes，在原生保存成功时取实际请求正文／写入结果并核对；API响应若未给摘要，读取实际保存文件核对。不得使用graphToPrompt、graph.serialize或规范化／重新stringify后的JSON代替这些bytes。已有托管图后续写入继续使用原文件permit／base_file_sha256检查，首次未托管保存不强行走该闭环。

#### 失败与验收

- 项目不存在沿404；页面离线沿503；页面／原生ID／内容／bytes变更或归属冲突沿既有409目标／内容冲突。失败不创建可供Agent写入的临时关联，不猜另一文件或项目。
- 原生文件已保存但关联失败必须明确分别显示，保留真实文件／草稿；不删除文件假报回滚，不发handoff，也不给Agent写权。关联成功而handoff未成功同样仍由人工控制。
- 验证新图无SQL行／nonce时仍可原生首次保存；选项目→保存→实际UUID/path/hash→关联→handoff同序，关联与交回之间Agent写入仍拒绝。
- 验证另存换UUID、真实文件bytes与规范化JSON不同、旧hash／错项目／错页／路径归属冲突、关联失败但文件仍在；重复关联／重连／read不改权限，不新增临时控制表、服务器草稿或第二份图。


### 共享图控制与最少当前状态

2026-10-27用户选择按图共享控制，不区分Agent客户端身份。同一个已绑定目标仍在线/活动且agent_allowed=true，换客户端或连接恢复可继续，无需再次交回；手动改图撤销后保持false，读取/重连/新上下文不能将false改true。不增加客户端账号、角色、会话登记或独立权限对象。另一个页面/图仍须用户按钮指定，不自动跟随。

handoff在短事务中保持唯一当前绑定：旧目标bound_page_id清空、agent_allowed=false并更换旧control_token，再给本次已保存目标绑定实际页、设true及新token。当前目标人工接管时保留bound_page_id供只读核对但置false。get_agent_context据此定位；普通切页仅暂停，没有新handoff就不换绑定。领域重启/WS重连若可核对同一页面与目标，只恢复路由观察、读取原SQL状态，不虚构授权；新网页page_id不同仍需用户指定。

workflow_sync只列原生Store已打开持久图的UUID→同步状态，含后台标签页，来自实际isModified/保存结果，不传全部草稿。维护/移除只按已保存权威及可核对在线观察工作，相关图unsaved/unknown或有待确认修改/写入时报告冲突，不假报无影响；不持SQLite写事务读取页面，不承诺发现任意离线客户端未提交的本地编辑。永久清理另走同Session活动输入guard。

SoftwareObservation.runtime_ref仅为实际适配器产生的必要调用定位（如进程身份/应用任务号），随call观察写⑤，不建③会话表；inspect_operation据此前证据只观察，不能从文件名猜成功。RunDetail.active是当前是否仍有准备/队列/软件活动（无法核对为null），与历史结果status独立；活动输入保护看active非false及未决提交，已核实停止的历史unknown不永久占用。reference_observations沿准入ResolvedInputs.items顺序公开执行后检查；变化据实显示，不自动重算/降级/改旧AssetVersion。

迟到progress/start不得把引擎终态回退为running，非终态通知触发原生/软件只读核对，不以到达顺序猜活动；相同输出按唯一定位去重。删图只清图文件/专属预览/关联，不取消已受理原生运行或删其事实；该图删除后不再保留后来专属预览，科学输出和日志仍按run记录。



### 平台节点在原生图中的必要约定

科学引用节点固定type=`APF_DATA_REFERENCE`，一个名为reference的STRING输入保存InputReference的JSON字符串（编辑图widgets_values[0]，执行图inputs.reference）；单个输出类型APF_SCIENCE，执行只返回该固定引用，不读预览作为科学数据。此固定选择控件不接受连线供值，导入有动态绑定时明确阻塞，不猜材料范围。add_data/set_data走同一字段，不在properties另存第二份引用。素材静态缩图从②现有同源预览接口显示，属于查看缓存，不伪造executed或新run；可视控件接入归workflowBridge及原生Widget机制，不为显示再登记资产或复制科学原件。

库节点type仍为APF_{definition_id.hex}。创建时在原生properties.apf_definition_token记录当前实际定义校验；确认更新默认值/端口时同步新值。这不是历史版本选择或旧定义库。预检核对实例标记、④当前定义、原生实际加载三者相符，缺失/不符明确要求确认更新或重建，不把旧widgets_values按新schema静默解释。运行中和历史内容不改，实际定义及参数仍随run保存；此标记不充当身份或授权。

### 校验值的使用范围

WorkflowGuard.content_token是当前页语义opaque标记；saved_content_token、WorkflowImpact.content_token和base_file_sha256用于已保存文件时均指实际UTF-8 bytes的SHA-256，不能与前者比较相等。原生实际GET载入/POST成功保存记录该页面所见文件bytes基准，后续写许可带此基准；不能在写前偷偷读取最新磁盘值替代旧页面基准以绕过冲突。Node内容校验来自当前定义JSON，科学内容仍沿既有blake3，不拿任何校验当用户授权。

原生user_manager在领域file-check返回后、无await的实际文件修改前再次核对本机文件基准，防两个并发请求都在旧bytes上取得许可后相互覆盖；该段与原子替换按当前引擎写入临界区完成，不长持数据库事务或另建分布式锁服务。

### 内部交接的领域消费者

内部 HTTP 也必须调用所属模块公开入口；app.py只装配，不直接写⑤ORM。下列类型放contracts/workflows.py，都是当前操作DTO，不增加持久对象或回执表。

| 类型 | 精确字段和条件 |
|---|---|
| `NativeFileResult` | `operation: Literal['save','move','delete']`、`project_id: UUID`、`workflow_id: UUID`、`path: str`、`destination: str \| None`、`succeeded: bool \| None`、`actual_file_sha256: str \| None`、`error: ErrorDetail \| None`；None仅表示实际结果不明，不填false冒充明确失败 |
| `FileWriteResult` | `result: NativeFileResult`、`association_updated: bool \| None`、`error: ErrorDetail \| None`；通用于save/move/delete的实际文件与关联结果；在线SaveResult与维护NativeWorkflowChangeResult按真实动作投影，不虚构page_id |
| `FileWriteRequest` | `project_id: UuidInput`、`workflow_id: UuidInput`、`operation: Literal['save','move','delete']`、`path: str`、`destination: str \| None`、`body_sha256: str \| None`、`base_file_sha256: str \| None`、`guard: WorkflowGuard \| None`、`maintenance_operation_id: UUID \| None`；正文是实际UTF-8 bytes的摘要。页面保存使用guard；受控维护只使用app批准动作内生成的maintenance_operation_id，两种来源互斥，不能由公开MCP指定维护来源 |
| `FileWritePermit` | `write_token: str`、`request: FileWriteRequest`；仅当前内存关联，绑定准确路径、正文、已有文件及批准来源。检查、消费及完成属于一次实际写入，不作为可重用权限 |
| `NativeFileCheck` | `write_token: str \| None`、`operation: Literal['save','move','delete']`、`path: str`、`destination: str \| None`、`body_sha256: str \| None`、`base_file_sha256: str \| None`；实际路径／摘要由原生最终写处观测并附入；不能只相信申请许可时的正文 |
| `NativeFileFinished` | `write_token: str`、`result: NativeFileResult`；原生写完成后回传，不能由普通MCP调用 |
| `NativeValidation` | `outputs_to_execute: list[str]`、`node_errors: JsonObject`、`error: JsonValue = None`；原生已完成校验的必要投影，不重定义其内部错误schema |
| `NativePromptCheck` | `request: NativePromptRequest`、`validation: NativeValidation`；现有原生validate_prompt结果的有限投影，不是第二图校验器 |
| `BrowserPageState` | `target: WorkflowTarget \| None`、`content_token: str \| None`、`control_token: UUID \| None`、`active: bool`、`sync_state`沿AgentContext枚举、`supported_operations: list[EditOpName]`、`workflow_sync: dict[str, Literal['saved','unsaved','unknown']]`、`current_graph: JsonObject \| None`；浏览器不提供online/实际sid等服务观察 |
| `NativePageForward` | `event: NativePageEvent`、`page: PageObservation`；引擎为领域HTTP补入实际socket的page/token/native_client_id/online，不能照抄客户端自报值 |
| `NativePageEvent` | `event_id: UUID`、`page_id: UUID`、`page_token: str \| None`、`action: Literal['open','state','changed','handoff','submit_run','authorize_file','confirm_software','associate_workflow']`、`target: WorkflowTarget \| None`、`payload: JsonObject`。payload的唯一形态按动作：open/state/changed/handoff为BrowserPageState，submit_run为RunSubmit或显式NodeTestCreate（按是否为节点测试的实际内部来源区分），authorize_file为FileWriteRequest，confirm_software为ConfirmSoftwareEvent，associate_workflow为AssociateSavedWorkflow；action与payload必须匹配。首次open没有page_token，其余由实际连接核对 |
| `NativePageReply` | `event_id: UUID`、`page_id: UUID`、`page_token: str`、`result: AgentContext \| RunDetail \| FileWritePermit \| PendingSoftwareAction \| AssociateWorkflowResult \| None`、`error: ErrorDetail \| None`；结果严格对应上述动作，不用任意dict冒充其他操作 |

组合根只保留当前页面、等待回包和文件permit的内存。⑤公开函数需要这份具体dict时显式传入，不建立StateManager或持久表；内存键为page_id/write_token，值为前述DTO。类型简记为`pages: dict[UUID, PageObservation]`、`permits: dict[str, FileWritePermit]`。

```python
def authorize_file_write(database: Database, settings: Settings, body: FileWriteRequest, *, pages: dict[UUID, PageObservation], permits: dict[str, FileWritePermit]) -> FileWritePermit: ...
def check_file_write(database: Database, settings: Settings, body: NativeFileCheck, *, pages: dict[UUID, PageObservation], permits: dict[str, FileWritePermit]) -> FileWritePermit | None: ...
def finish_file_write(database: Database, settings: Settings, body: NativeFileFinished, *, permits: dict[str, FileWritePermit]) -> FileWriteResult: ...
def check_native_prompt(database: Database, body: NativePromptCheck) -> None: ...
async def apply_native_event(database: Database, settings: Settings, body: NativeExecutionEvent) -> None: ...
```

| 内部路由 | 领域消费者与副作用 |
|---|---|
| `POST /internal/native/page` | app接收NativePageForward，先取得实际引擎连接补入的PageObservation；open/state/changed/handoff交⑤apply_page_event，submit_run按既定payload分型：NodeTestCreate交test_node(origin='human')，普通RunSubmit交submit_run(origin='human')；authorize_file交authorize_file_write；confirm_software交③应用组合，associate_workflow交associate_saved_workflow。只分派固定动作，不反射任意函数 |
| `POST /internal/native/file-check` | ⑤check_file_write重新检查实际文件／准入。没有token且路径未经平台管理返回None沿原生行为；已有托管图缺token或失效则409，不能降为普通写入。成功200返回FileWritePermit并消费一次准入，非托管200/null；保留当前完成关联 |
| `POST /internal/native/file-finished` | ⑤finish_file_write根据原生实际成功／失败建立或更新关联、清专属预览，200返回FileWriteResult。已消费操作的完成回传不因为随后关页就谎称未写；回传未知先读取实际文件／关系核对，不重放 |
| `POST /internal/native/prompt-check` | ⑤check_native_prompt核对已固定run、私有token、投影和原生范围／错误；真实NativeValidation保存到同run，HTTP错误只传摘要，GET run可取完整node_errors给原生错误显示。成功204；409／422／503拒绝发生在queue.put之前，无新持久对象 |
| `POST /internal/native/event` | ⑤apply_native_event关联已记录prompt更新真实状态、当前进度／日志和已完成输出；成功204。长检查／缩图在现有工作线程执行，不持数据库事务；不保存每帧进度或事件历史。关页仍接收，UI仅显示已有事实 |

这些内部入口不进入同源公开代理或MCP目录。引擎先核对响应才报告关联成功；file-check失败不写文件，file-finished失败必须分别报告文件已写／关联未成。服务重启使尚未消费的内存许可失效；对已发生或结果不明的写入先查实际文件，不以重新签发许可自动重放。

维护许可只由app当前已批准的动作调用authorize_file_write产生，body的maintenance_operation_id从此闭包取得而不是从模型请求取。check_file_write只核对现有操作归属，不重新申请外层维护锁；不能在domain→engine→domain回调链中等待自己持有的事务或跨请求锁。普通Agent改图不具备这个来源，也不能借维护入口绕过活动画布规则。

apply_native_event只消费真实引擎事件，不以一次executed重建软件调用事实；③实际调用仍以同run记录为准。相同run/node/output/member的预览只对应一个preview_id，重复事件／缓存回放不得再次登记处理或再生成一条完成记录。Preview状态统一`generating/available/unsupported/failed`，科学产物可用、预览可读与素材保存分别表达。事件遗漏时get_run查询原生队列／history及实际调用，缺证据保留unknown；没有通用事件重放器。

当前许可、WS routing token和run执行私有token各用于已明确的实际边界，不增加作者／角色、版权身份或恶意本机用户隔离体系。可靠按钮来源、异步控件一致性、原生装载及实际停止仍按原型门槛验证，不能以DTO已定义宣称这些功能已通过。

### 显式节点测试与同次运行受理

节点测试必须在任何试验图编辑之前按run_id登记/核对同次请求，不能先加节点再发现这个run已经存在。⑤提供下面的必要组合入口，app中的submit_node_test仅核对路径definition_id并委托它；④仍不依赖⑤或新增执行器。

```python
async def test_node(database: Database, settings: Settings, body: NodeTestCreate, page_command: PageCall, post_prompt: SubmitPrompt, *, origin: Literal['human', 'agent'], preparations: dict[UUID, Task[None]]) -> RunDetail: ...
```

test_node与submit_run共用同次运行受理/准备实现：先以唯一run_id和原始测试内容短事务建立preparing；同ID同请求只返回既有事实，不再次改图；不同请求409。然后核对④当前定义、目标和控制，把明确输入/参数及被测实例落实到指定测试图，记录实际node_execution_id和NodeTestAssociation，再经过同一转换、单次保存及最终提交。测试不是全图普通运行，也不隐藏覆盖别的画布。public的普通submit_run不接受客户端伪造被测关联；普通包含该定义的运行不会覆盖最近显式测试。失败记录留在⑤，保存定义不以测试通过为门槛。

人工节点测试在目标网页通过原生submit_run页面链携带明确NodeTestCreate，由内部入口派生human；公开nodes/test按agent受理。NodeEditor测试按钮经NativeShell注入的宿主回调（NodeTestCreate→Promise<RunDetail>）调用同一submitNativeRun(body)，不直接调用agent来源的NodesClient.test。submitNativeRun的普通NativeRunOptions分支构造RunSubmit，显式NodeTestCreate分支保留同run_id和测试正文；同一个apf.page submit_run入口按已定载荷调用test_node或submit_run，不新增公开桥接函数／网络入口。人工接管状态仍可测试，不因此授予Agent写权；test_node在修改测试图前先登记／核对同次请求。source字段不由请求自行赋权。实现所需共享私有函数随这两个真实调用者提取，不在本设计预建另一组运行框架。

### 当前占用与历史结果分别核对

SoftwareObservation另含`active: bool | None`：真实仍占用为true、已核实退出/操作结束为false、无法核对为null；这与完成结果未知不是同一个概念。③提供一个只观察的必要入口，⑤按已保存调用信息查询，不能只查看新进程里的空句柄表。

```python
async def inspect_operation(settings: Settings, invocation: SoftwareInvocation, previous: SoftwareObservation | None) -> SoftwareObservation: ...
```

该函数只核对实际软件支持的调用/进程/结果观察，不启动软件、不重跑、不发送取消。首软件原型须证明如何恢复必要调用定位；无法证明时active=null、说明原因，不能凭日志缺失或句柄消失填false。get_run及维护准入组合原生当前队列/准备状态和各call的最新active；任何true或null仍阻塞替换，已核实无活动工作后可释放当前占用，即使旧run结果继续unknown。历史结果unknown不被改为成功/失败，也不独自成为永久繁忙。此为原有状态查询与重启核对所需的实际边界，不增加软件会话库或恢复调度器。

### 长准备的HTTP受理与生命周期

公开runs及nodes/test返回202，不等待大科学文件复制或软件处理。submit_run/test_node先短事务建立唯一run_id，再在应用持有的`preparations: dict[UUID, asyncio.Task[None]]`中启动这个run的一次准备协程，立即返回preparing的RunDetail。该协程沿前述页面准备、单次保存、输入固定、预检和原生提交顺序工作；不是另一条图调度队列。重复同ID只读原记录，不再启动协程或改图。所有异常都结束为实际failed/unknown/cancelled并写日志；不能使用丢失句柄的fire-and-forget任务。

组合根创建并持有此当前Task字典，submit_run/test_node签名增加keyword-only preparations；工作完移除内存项，运行事实留SQLite。初始化时对无法确认仍在执行的旧preparing/submitting记录标unknown并核对原生/实际调用，不自动重启准备。服务关闭沿维护排空等待当前实际工作，不能以页面关闭或MCP断连取消已受理运行。取消先写同run标记，准备协程在任何新调用/入队前核对；仍在复制但尚未核实结束时只报告待停止，不能因为尚无prompt_id就假报已停。

原生人工batch循环每次提交独立UUID；submitNativeRun收到202后查询同run直到真实入队/执行或失败/未知，再结束本轮UI排队动作。beforeQueued和afterQueued各只一次，不能立即开始第二个batch准备去改第一轮正在使用的画布。新输入准备期间未固定实现集合时，get_implementation_usage将该运行作为实现未知的阻塞项；固定后只保护真实引用。新增字段`RunImplementationUse.binding_unknown: bool`表达这个事实，不用猜测的package_ids替代实际绑定。

原生受理回包前到达的托管事件先按已固定prompt/原生workflow元数据归属；不能因为浏览器尚无queuedJobs项就写当前rootGraph。无法确定页面归属时先只记录领域事实，得到真实run/图关联后读取预览显示，不重放执行或持久化每帧事件。原生排队仍是唯一图执行队列，UI的查询/准备Task仅负责已有异步交接。

### 科学端口的实际封装

NativeNodeCall.scientific_values的键是节点输入名，parameter_values的键是节点可编辑参数名；⑤按已固定SoftwareBinding映射到SoftwareOperation名字，固定参数取定义，不由body覆盖。SoftwareInvocation.inputs及parameters使用软件操作名，NativeNodeResult.outputs则映回节点输出名；output_index按本次节点输出定义顺序，member_index按软件实际输出成员顺序。

集合是一次软件操作的一份有序科学值，不把成员交给ComfyUI隐式逐文件调用。适配返回的tuple每个位置对应一个声明输出：单文件是一个locator，集合是locator列表作为该位置的一个值；科学集合不设置OUTPUT_IS_LIST使引擎自动拆开。输入也保持这一层封装，③收到该端口完整有序ResolvedInput列表。单个/集合语义由准确操作声明，不由返回数量猜测。首软件原型必须用至少两成员证明一次调用及成员顺序，不拿普通IMAGE tensor列表代替。

NodeTestCreate.inputs每个输入名只传一个InputReference；多文件用现有固定DatasetInputReference表达，不为测试临时建素材组／集合管理对象。测试组合用同一add_data建立该固定引用并连到被测节点；实际科学输入展开仍由②处理。工作流一般连线可传同run上游OutputLocator，测试请求不接受任意path或历史预览。

文件完成回传唯一由user_manager→engine适配→domain执行。浏览器after钩子不再次POST file-finished，只读取这次userdata响应的事实。托管userdata保持原响应正文和文件HTTP结果，附`X-APF-File-Changed`及`X-APF-Association-Updated`（值为true/false/unknown），必要时附`X-APF-Association-Error`的错误code；Api层据此构造FileWriteResult给after钩子。非托管响应保持原状。文件成功但关联回传丢失时文件结果仍true、关联unknown，不让saveWorkflow的文件成功单独放行运行；维护adapter读取同一结果，不再发送第二次完成回传。


### 定向取消与实际停止

### 2. 最小增量：一个受控内部动作回执

旧 `POST /api/jobs/{id}/cancel` 和 batch 响应继续保持原状，不扩字段、不换语义。仅在已规划的 `interfaces/comfyui.py:register_native` 增加：

`POST /astrophotoflow/internal/prompts/{prompt_id}/cancel`

- 只供领域服务用已固定的原生URL和workspace Bearer调用，沿原生内部端点认证；不加入浏览器同源代理公开白名单或MCP能力目录。
- 路径是规范UUID，正文为空。不是可指定任意method／URL／执行命令的通用入口。
- HTTP 200返回 `NativeCancelResult`。401／422在任何动作前明确拒绝；无此原生任务仍200返回no_action。未预期执行错误不伪造“没有动作”。
- 路由直接调用原来的 `cancel_job`，传入原队列的 `interrupt_if_running` 和 `delete_queue_item` 回调。无需复制分类／竞争处理逻辑，也无需将该逻辑搬到新的取消类。

内部认证失败为401 `AUTHENTICATION_REQUIRED`；路径在动作前调用现有 `validate_job_id` 验证规范UUID，失败为422 `VALIDATION_ERROR`。原生内部route缺失／不可用不表示任务不存在：适配保留 `NATIVE_CANCEL_UNAVAILABLE`，不改调旧public route。发送后断连／超时为 `NATIVE_CANCEL_UNKNOWN`；成功体类型或prompt_id关联不符合契约为 `INVALID_NATIVE_RESPONSE`，动作同样unknown。只有明确的受理前拒绝可证明本次没有动作；500等可能已经发生副作用的响应不能映射成False。

`contracts/workflows.py` 拟新增有限类型，使用已有 `StrictModel/UuidInput/ErrorDetail`；不导入原生queue类：

| 类型 | 精确字段 |
|---|---|
| `NativeCancelResult` | `prompt_id: UUID`；`outcome: Literal['dequeued','interrupt_sent','terminal','no_action','unknown']`；`observed_at: datetime`；`error: ErrorDetail \| None` |
| `NativePromptObservation` | `prompt_id: UUID`；`state: Literal['queued','running','terminal','missing','unknown']`；`terminal_status: Literal['completed','failed','cancelled'] \| None`；`observed_at: datetime`；`error: ErrorDetail \| None` |

`outcome='unknown'` 只供领域侧适配表达动作响应不明，例如POST发送后断连／超时或成功体不符合契约；原生正常处理的200只返回其余四种。原生有明确的受理前拒绝时，用 `no_action` 并保留实际错误。`terminal`只证明原生任务已在history，不代表科学结果成功或③软件已退出。

| 既有helper返回 | 内部outcome | 本次动作的 `queue_removed` | 本次动作的 `interrupt_sent` |
|---|---|---|---|
| `CANCEL_PENDING` | `dequeued` | True | False |
| `CANCEL_RUNNING` | `interrupt_sent` | False | True |
| `CANCEL_TERMINAL` | `terminal` | False | False |
| `CANCEL_UNKNOWN` | `no_action` | False | False |
| 无可靠动作响应 | `unknown` | None | None |

`CANCEL_UNKNOWN → no_action` 表示这次helper没有真实删除或发出中断，**任务现状仍可能未知**；不能把no_action解释为已经停止。pending→running竞争必须映射为 `interrupt_sent/False/True`，不能沿最初的pending分类填写queue_removed。

实现可直接用 `cancel_job` 的返回值作上述映射，因为其代码已依据回调的真实bool修正竞争。如果工程上选择在回调内记录动作，也只能在原 `delete_queue_item(...) is True`／`interrupt_if_running(...) is True` 后记实；不得重新实现另一套取消判断。两种写法不并存；优先直接映射现成返回值。

### 3. 准确的适配与⑤公开签名

以下替换的是草案中的拟签名，不是修改现有public接口。`interfaces/comfyui.py` 保持双解释器的局部依赖边界；标准库UUID和contracts可直接使用，`PromptServer/AsyncClient/Request/Response` 沿既定TYPE_CHECKING及相应入口局部导入规则。

```python
def cancel_native_prompt(
    server: "PromptServer", prompt_id: UUID
) -> NativeCancelResult: ...

async def receive_prompt_cancel(
    server: "PromptServer", request: "Request"
) -> "Response": ...

async def cancel_prompt(
    client: "AsyncClient", prompt_id: UUID
) -> NativeCancelResult: ...

async def observe_prompt_state(
    client: "AsyncClient", prompt_id: UUID
) -> NativePromptObservation: ...
```

- `cancel_native_prompt` 为原生队列实际动作的同步薄适配：同原生现有路由取running／queued／history，调用一次helper并映射返回。它没有await，不等待任务退出，不读领域数据库，不访问③。内部route只认证、解析UUID、调用它及序列化结果。
- `cancel_prompt` 只调用上述固定内部POST，不再把 `/api/jobs/{id}/cancel` 的bool当业务事实。已发送后无法确定结果返回 `unknown` 和具体错误，绝不猜dequeued或自动重发。内部route不可用也不回退到旧bool响应。
- `observe_prompt_state` 复用已有 `GET /api/jobs/{id}` 取得归一终态，再读已有 `GET /queue` 核对该ID当前running／pending；不增加第二个内部route。最终queue仍有目标时优先返回running／queued，不能被较早history覆盖；目标已不在queue且job有明确终态时返回terminal并保留原completed／failed／cancelled。两处都没有为missing；只知曾活动、现已不见却无终态证据为unknown，读取失败同样unknown并保留错误。这个有限投影只供停止判断，不复制完整job schema，也不将completed当作科学结果检查通过。
- **GET只提供当前停止观察，永远不填写queue_removed或interrupt_sent。** 即使取消前是pending、取消后404，也不能证明本次发生了排队移除。

上述两个GET不是推断取消动作的前后比较：其作用是避免已观察到的get_job优先history规则掩盖仍活动的目标。提交是否仍在途中继续由⑤本次run的真实提交状态约束；有未决提交时，不因一次queue为空就宣布停止。

queue响应沿源码 `server.py:1155-1161` 的 `queue_running/queue_pending` 数组；队列项索引1是prompt_id，按规范UUID字符串精确匹配。job字段 `status='pending'/'in_progress'` 对应queued／running；不根据显示名称、最后运行任务或数组顺序猜目标。响应缺少这些已约定字段时保留契约错误及unknown，不替换为空队列。

应用组合根绑定native client后，把有限callable交给⑤；⑤不导入interfaces：

```python
CancelPrompt = Callable[[UUID], Awaitable[NativeCancelResult]]
ObservePromptState = Callable[[UUID], Awaitable[NativePromptObservation]]

async def cancel_run(
    database: Database,
    settings: Settings,
    run_id: UUID,
    cancel_prompt: CancelPrompt,
    observe_prompt_state: ObservePromptState,
) -> CancelResult: ...
```

③继续复用已经拟定的同进程公开函数，不新建软件取消route：

```python
async def cancel_operation(call_id: UUID) -> SoftwareCancelResult: ...
```

`SoftwareCancelResult` 沿原③草案：`call_id`、`request_state: sent/not_supported/not_running/unknown`、`stop_state: stopped/running/unknown`、`observed_at`、`reason`。`request_state='sent'`不等于stopped；找不到句柄或 `not_running` 本身也不能证明此前已开始的进程不会继续，须有真实退出／未启动且已终止的观察。

### 4. `CancelResult` 与同次运行保存

`contracts/workflows.py` 的拟 `CancelResult` 最小修订：

| 字段 | 类型与含义 |
|---|---|
| `run_id` | `UUID` |
| `requested` | `bool`；200受理时为True，表示⑤已经记录用户取消意图，不表示命令已送达或实际停止 |
| `queue_removed` | `bool \| None`；严格沿第2节动作回执，不来自运行状态猜测 |
| `interrupt_sent` | `bool \| None`；同上，独立表达原生定向中断是否实际发出 |
| `native` | `NativeCancelResult \| None`；没有进入原生提交的运行可为None；已尝试动作即保留回执／unknown及错误 |
| `software` | `list[SoftwareCancelResult]`；本次对实际call的停止观察，不以一个总bool覆盖各软件的不同结果 |
| `stop_state` | `Literal['stopped','running','unknown']`；下述整体停止结论 |
| `reason` | `str \| None`；准确解释仍在软件内运行、仍在队列、停止证据缺失等原因 |

`native`、各call最新停止观察和总体结果写回原 `WorkflowRun.result_json`／同次calls事实，沿现有字段关联，不新增取消事件账本或任务表。读取后续真实状态可以更新stop_state，不能把此前已确认的dequeued／interrupt事实抹成False，或从后来404补造True。

### 5. `cancel_run` 调用顺序与聚合

1. 在现有认证和run归属检查后读取固定prompt_id。run不存在返回404，受理前拒绝不触碰引擎或软件。短写事务记录 `requested=True`；运行准备／实际节点受理共享此标记，取消后不得再开始新的软件call或把尚未提交的准备结果继续入队。
2. 取同次运行所有已经受理的call，包括starting／running／unknown，不只看③此刻是否有进程句柄。取消标记与新call登记在同一短准入边界核对；取消前已登记但尚在启动中的call也必须纳入核对。
3. 已有prompt_id且提交可能发生时，调用一次typed `cancel_prompt`；同时针对该run实际call调用③ `cancel_operation`。各call的unknown或不可停止不能阻断其他call的停止请求；可以用普通async gather处理独立调用，不引入另一队列。不持数据库事务等待这些操作。
4. 再用typed `observe_prompt_state` 只读核对原生当前执行事实，并读取实际call最新退出／停止观察。网络中断、无句柄或history缺失仍是unknown，不重跑软件、不重投prompt、不做无目标全局interrupt。
5. 短写事务保存实际回执及聚合结果。`POST /api/v1/runs/{run_id}/cancel` 在取消意图已受理后返回200 `CancelResult`，即使部分／全部停止结果未知；不会把unknown包装成“已取消”。GET run继续读真实观察并核对。

两条分支独立：原生取消失败／失联仍应停止能明确定位的③call，某个③call未知仍应核对原生并处理其余call。无法取得的事实保留对应unknown/error，不用一个HTTP异常丢弃已经得到的其他真实回执。取消本身仍是对明确run的操作，不进入软件安装确认流程，也不要求给每个call弹确认。

聚合采用以下精确规则，不能只看原生 `cancelled` 或HTTP200：

- **已确认任何实际软件call仍running，或当前原生观察为running，整体为running。** 原生任务已终态但某软件仍在运行时同样为running，不能报告stopped或释放其包占用。
- 软件call处于starting且不能确认不会启动、失联、无法核对停止，属于未解决工作。没有其他已确认running但有未解决工作时，整体为unknown。
- 原生 `dequeued` 是已移除目标排队项的直接停止证据；在本次固定提交没有未决提交／新call、无仍活动／未知软件call时，整体可为stopped。取消后GET404在此不撤销正面的移除回执；相反，404本身没有这一证明力。若后续真实观察仍发现该prompt在队列／执行，则保留queue_removed=True这项历史动作事实，同时整体不能报stopped。
- 原生已有真实终态观察，且全部实际call均确认退出／停止时，整体为stopped。单纯 `interrupt_sent` 不满足这个条件。`terminal/no_action`可能是自然完成，保留本次运行真正的completed／failed事实，不因用户随后点击取消就回写成cancelled。
- 原生missing／unknown且没有正面的dequeued／终态证据时，整体为unknown；仅剩排队但本次未确认移除时也不报停止，reason明确“仍在队列，未确认停止”。
- 准备阶段确定尚未进入原生提交时，本次queue_removed和interrupt_sent可为False、native为None；只有准备任务已确认停止且受理边界确保不会再提交时才报stopped。准备仍在进行或提交位置不明时保留unknown，不能凭prompt_id暂缺就宣称停止。

已经由真实停止证据结束的call不必再次发送软件停止；其退出事实参与聚合。`not_supported`并不自动等于running或unknown：有实际仍运行观察则running，没有可靠现状则unknown；已真实退出才stopped。

`RunStatus` 与这些取消字段分开：取消请求不能直接改为cancelled；真实队列移除／原生中断终态与软件停止全部满足后才按实际取消结果更新。不得把已确认的自然完成或原有失败改写为取消。**包／节点繁忙检查还必须考虑同次calls中starting／running／unknown的实际占用，即使原生图已经终态或run记录已有错误；不能仅按原生queue或顶层RunStatus释放使用。**

### 6. 文件与必要测试

| 文件 | 最小变更责任 |
|---|---|
| `src/astrophotoflow/contracts/workflows.py` | 有限NativeCancelResult／NativePromptObservation和修订CancelResult；保留现有纯契约依赖 |
| `src/astrophotoflow/interfaces/comfyui.py` | 同文件同步helper薄适配、一个认证内部route、两个typed HTTP调用；register_native挂接，不新增取消器 |
| `src/astrophotoflow/interfaces/http/app.py` | 绑定固定native client到两个callable；公共run取消route和原有MCP业务ID保持 |
| `src/astrophotoflow/modules/workflows/public.py` | cancel_run的短事务／实际call聚合、后续只读核对及使用保护；不访问③私有句柄 |
| ③既定public实现 | 正常返回真实SoftwareCancelResult，包括不可停止／未知；不把发送中断当真实退出 |
| `engine/ComfyUI/server.py` 旧取消route、`comfy_execution/jobs.py` | **不修改public响应或helper逻辑**；继续复用其已有行为与竞争处理 |

以下为拟新增／扩展验收，不是本轮已执行证据：

| 用例与层级 | 输入／操作 | 唯一关键预期 |
|---|---|---|
| 实际排队移除，内部route适配 | 原生目标pending，真实dequeue返回True；取消后GET可为404，run无实际call | outcome=dequeued，queue_removed=True，interrupt_sent=False，stop_state=stopped；旧public仍只有cancelled=True。不能因为GET404而丢掉已确认移除事实 |
| pending→running竞争，复用现成helper | 初始queued快照，dequeue=False，定向interrupt=True | outcome=interrupt_sent，queue_removed=False，interrupt_sent=True；不得沿最初分类谎报移除 |
| **跨③⑤：cancelled=True但软件仍running** | 原生运行目标interrupt=True，故旧public取消bool=True；typed内部回执为interrupt_sent。即使原生后续已terminal，③返回 `request_state='sent', stop_state='running'` | ⑤requested=True、queue_removed=False、interrupt_sent=True、software保留该call、整体stop_state=running；不能标记已取消或释放软件／节点使用；不创建任何新运行／调用 |
| 上例后续真实退出 | GET run读到原生终态及该call真实stopped | 整体才变stopped；此前queue_removed=False、interrupt_sent=True不改变；只读核对不再次调用cancel／invoke／POST prompt |
| 动作响应丢失 | 内部POST可能已执行但响应断连；随后GET404，history无证据 | outcome=unknown，queue_removed=None、interrupt_sent=None、整体unknown；不以GET前后状态补造动作，不自动重发取消或重跑 |
| helper无动作且任务已自然终态 | helper终态／no_action，真实终态和所有call退出可查 | queue_removed=False、interrupt_sent=False、整体stopped，保持实际completed／failed；不是“取消成功导致取消终态” |

建议拟新增 `tests/interfaces/comfyui/test_cancel.py` 验证内部route／typed适配，并在⑤既定运行测试中新增跨软件case；复用已有helper测试而不复制一套分类器。真实外部软件的停止能力仍按首软件原型验证，本设计不宣称某软件可以强制停止。

<a id="mcp-design"></a>

## 16. 精简MCP的文件和协议

迁移时interfaces/mcp/server.py只装配三入口，移除tools/imports.py、library.py、organization.py旧注册／别名；58业务清单见第8节，HTTP／CLI与AssetClient仍复用。目录／检索归⑤。

### 目录类型和具名入口
| `contracts/workflows.py` 类型 | 必要字段 |
|---|---|
| `CapabilityKind` | `Literal['tool','node','software_operation']` |
| `CapabilitySummary` | `kind: CapabilityKind`、`id: str`、`name: str`、`description: str`、`source: str`、`content_token: str \| None`、`version: str \| None`、`ready: bool`、`reason: str \| None`；source 是实际所属模块／软件包，不增加作者、版权或角色资料 |
| `CapabilitySearch` | `items: list[CapabilitySummary]`（最多10）、`search_mode: Literal['hybrid','keyword']`、`degraded_reason: str \| None` |
| `ToolCapability` | 继承`CapabilitySummary`所有字段并收窄`kind: Literal['tool']`；增加`arguments_schema: JsonObject`、`result_schema: JsonObject`、`preconditions: list[str]`、`requires_confirmation: bool`；schema 从真实模型／具名操作派生 |
| `NodeCapability` | 继承`CapabilitySummary`并收窄`kind: Literal['node']`；增加`definition: contracts.nodes.NodeDefinition`，直接引用④最终DTO，不另造定义schema |
| `SoftwareOperationCapability` | 继承`CapabilitySummary`并收窄`kind: Literal['software_operation']`；增加`definition: contracts.software.SoftwareOperation`，直接引用③最终DTO，不声明可经MCP越过图执行 |
| `CapabilityDefinition` | 上述三种按顶层`kind`判别的联合；不再嵌套一份重复summary，不创建第二份可编辑目录权威 |

get_capability返回的arguments_schema／result_schema必须可独立解释：复用各操作Pydantic模型的schema及本次实际引用的传递闭包`$defs`，不返回离开OpenAPI后悬空的`#/components/schemas/...`，也不附带全部112份模型。上传客户端参数与服务端多阶段请求分别按原具名操作提供，图像输出仍用SDK ImageContent；schema完整性不改变业务权限。

```python
def search_capabilities(capabilities: Sequence[CapabilityDefinition], settings: Settings, query: str, *, kind: CapabilityKind | None = None, source: str | None = None) -> CapabilitySearch: ...
def get_capability(capabilities: Sequence[CapabilityDefinition], kind: CapabilityKind, capability_id: str) -> CapabilityDefinition: ...

def search_capabilities(self, query: str, *, kind: CapabilityKind | None = None, source: str | None = None) -> CapabilitySearch: ...
def get_capability(self, kind: CapabilityKind, capability_id: str) -> CapabilityDefinition: ...
def list_workflows(self, project_id: UUID, *, limit: int = 50, offset: int = 0) -> WorkflowPage: ...
def get_agent_context(self) -> AgentContext: ...
def get_workflow(self, workflow_id: UUID) -> WorkflowDetail: ...
def edit_workflow(self, body: EditRequest) -> EditResult: ...
def save_workflow(self, guard: WorkflowGuard) -> SaveResult: ...
def replace_workflow(self, body: ReplaceRequest) -> ReplaceResult: ...
def submit_run(self, body: RunSubmit) -> RunDetail: ...
def get_run(self, run_id: UUID) -> RunDetail: ...
def list_workflow_runs(self, workflow_id: UUID, *, limit: int = 50, offset: int = 0) -> RunPage: ...
def cancel_run(self, run_id: UUID) -> CancelResult: ...
def list_run_previews(self, run_id: UUID) -> list[PreviewSummary]: ...
def read_run_preview(self, run_id: UUID, preview_id: UUID) -> bytes: ...
def save_run_output(self, run_id: UUID, body: SaveOutput) -> OutputSaveResult: ...
```

目录HTTP仅GET /api/v1/capabilities/search?query=...&kind=...&source=...及GET /api/v1/capabilities/{kind}/{capability_id}。app从当前API／请求模型和明确业务映射、③④公开入口提供真实定义，⑤不import interfaces或反读MCP注册；目录无永久表，索引可重建，定义变化重建相关项。完整schema按外部请求返回，实际调用仍分派具名业务，不做任意URL代理。

<a id="capability-dispatch"></a>

### 本期新增业务ID到具名调用的固定映射

此表补齐前面行为表未逐项固定的目录ID；原58项仍为第8节唯一`data.<原名>`，不改名或机械改单HTTP。仅`kind='tool'`可call；③操作和④定义使用自身package／operation／definition身份供发现／入图，不另造可执行工具ID。相同业务只保留下表一个ID，②所选结果保存／查询统一使用⑤runs入口，不保留前期摘要中的data.save_output／data.output_save_status别名。

参数投影严格按表列字段及其已定DTO，额外字段拒绝；路径参数不再在正文重复。无参数用空对象；`?`表示可省略，默认值与对应签名一致。这里不新增HTTP或通用call接口，各行是MCP接入层的固定分派，实际业务检查仍在所属模块。Python客户端签名见[具名客户端](#python-clients)及本节；body是MCP的arguments对象，不要求客户端再包一层body键。

| kind=tool 的固定ID | arguments及唯一模型来源 | 唯一调用／结果 |
|---|---|---|
| foundation.start／status／stop／restart | `workspace_config?: str`，本机转换Path；省略按①默认配置 | 对应core.workbench同名函数；WorkbenchResult／WorkbenchState；创建在线AssetClient前分派 |
| foundation.config.get | `{}` | AssetClient.get_workbench_configuration()→ConfigState |
| foundation.config.save | ConfigSave本体 | AssetClient.save_workbench_configuration(ConfigSave)→ConfigState |
| data.observe_asset_content | `asset_id: UuidInput` | AssetClient.observe_asset_content(str(asset_id))→AssetContentObservation |
| data.accept_asset_content | `asset_id: UuidInput`及AssetContentAccept全部字段 | AssetClient.accept_asset_content(str(asset_id), AssetContentAccept)→AssetOut |
| data.removal_preview | LibraryEntriesRemove本体 | AssetClient.preview_library_removal(body)→LibraryRemovalPreview；原data.remove_library_items改用LibraryRemovalApply |
| software.list | `{}` | AssetClient.list_software_packages()→list[SoftwarePackage] |
| software.get | `package_id: str`、`operation_id?: UuidInput` | AssetClient.get_software_package(package_id, operation_id=...)→SoftwarePackageDetails |
| software.install | `package_id: str`及SoftwareInstallRequest字段 | AssetClient.install_software(package_id, body)→PendingSoftwareAction |
| software.prepare | `package_id: str` | AssetClient.prepare_software(package_id)→SoftwarePreparation |
| software.update_preview | `package_id: str`、`target_version: str` | AssetClient.preview_software_update(package_id, target_version)→PackageUpdatePreviewResult |
| software.update | `package_id: str`及SoftwareUpdateRequest字段 | AssetClient.update_software(package_id, body)→PendingSoftwareAction |
| software.uninstall | `package_id: str`及SoftwareUninstallRequest字段 | AssetClient.uninstall_software(package_id, body)→PendingSoftwareAction |
| nodes.list | `{}` | AssetClient.list_nodes()→list[NodeDetails] |
| nodes.get | `definition_id: UuidInput` | AssetClient.get_node(definition_id)→NodeDetails |
| nodes.save | `definition: NodeDefinition`、`operation_version: str`；仅首次custom保存 | AssetClient.create_node(...)→NodeDetails |
| nodes.update_preview | 同上及`expected_content_token: str` | AssetClient.preview_node_update(...)→NodeUpdatePreviewResult |
| nodes.update | 同上及`impact_token: str` | AssetClient.update_node(...)→NodeUpdateResult |
| nodes.test | NodeTestCreate本体 | AssetClient.test_node(body)→RunDetail |
| workflows.list | `project_id: UuidInput`、`limit?: int=50`、`offset?: int=0` | AssetClient.list_workflows(...)→WorkflowPage |
| workflows.get | `workflow_id: UuidInput` | AssetClient.get_workflow(workflow_id)→WorkflowDetail |
| workflows.context | `{}` | AssetClient.get_agent_context()→AgentContext |
| workflows.edit | EditRequest本体 | AssetClient.edit_workflow(body)→EditResult；路径取guard.target.workflow_id |
| workflows.save | WorkflowGuard本体 | AssetClient.save_workflow(guard)→SaveResult |
| workflows.replace | ReplaceRequest本体 | AssetClient.replace_workflow(body)→ReplaceResult |
| runs.submit | RunSubmit本体 | AssetClient.submit_run(body)→RunDetail；路径取guard.target.workflow_id |
| runs.get | `run_id: UuidInput` | AssetClient.get_run(run_id)→RunDetail，含真实输出保存状态 |
| runs.list | `workflow_id: UuidInput`、`limit?: int=50`、`offset?: int=0` | AssetClient.list_workflow_runs(...)→RunPage |
| runs.cancel | `run_id: UuidInput` | AssetClient.cancel_run(run_id)→CancelResult |
| runs.list_previews | `run_id: UuidInput` | AssetClient.list_run_previews(run_id)→list[PreviewSummary] |
| runs.read_preview | `run_id: UuidInput`、`preview_id: UuidInput` | AssetClient.read_run_preview(...)→bytes，再转真实ImageContent |
| runs.save_output | SaveOutput本体 | AssetClient.save_run_output(body.output.run_id, body)→OutputSaveResult；不再传一份可矛盾的run_id |
| runs.find_saved_output | `asset_version_id: UuidInput` | AssetClient.find_saved_output(asset_version_id)→OutputLocator或null |

foundation本机定义可在服务离线时读取，不把离线全目录假装在线；软件／节点读取及业务能力由实际客户端／路由模型派生。B56可构建当前已实现业务的真实目录，B57完成上表及原58项的最终协议映射；尚未实现的S6能力不进入可调用列表。schema引用只带必要传递闭包，分派表不提供任意URL、函数路径、确认入口、软件直接执行、文件path或控制权自授操作。

### `interfaces/mcp/server.py` 的完整工具签名

```python
from mcp.types import CallToolResult

def search_capabilities(query: str, kind: CapabilityKind | None = None, source: str | None = None) -> CallToolResult: ...
def get_capability(kind: CapabilityKind, id: str) -> CallToolResult: ...
def call_capability(id: str, arguments: dict[str, JsonValue]) -> CallToolResult: ...
```

三入口统一CallToolResult；成功structured_content分别为CapabilitySearch／CapabilityDefinition／具名业务JSON，SDK无output_schema注册参数。call按固定业务ID→真实请求模型→具名AssetClient映射，无任意URL/method/Python/shell；node／software_operation须④封装／⑤入图，不直接call执行。
import_photo/import_photos保留客户端Path读取及PhotoImportOptions／既有参数语义，继续批次→PUT文件→start，不把58项机械改为单HTTP／服务任意path。读display/run preview返回真实bytes编码的ImageContent，不以URL或JSON字符串代替。
foundation.start/status/stop/restart及其已知定义在构造在线AssetClient前本机分派，参数／返回沿①；其他需在线能力如实不可用，不静默启动或改默认指针。
成功结果保留结构和简短文本；业务失败用真实envelope返回 `CallToolResult(is_error=True, structured_content=envelope.model_dump(mode='json'), content=[TextContent(...)])`，保留code/message/fields/request_id，HTTP状态可附加、不改envelope；避免ToolError(str(exc))丢字段。Python用SDK snake_case，wire别名由SDK处理。断连无服务回执则只报传输unknown及已知run/task，不伪造request_id／重试副作用。requires_confirmation仅说明，实际业务仍核确认／目标／内容／控制。


### CLI的必要观察入口

沿现有interfaces/cli/commands.py注册具名只读操作：`apf runs get RUN_ID`调用AssetClient.get_run，`apf runs list --workflow WORKFLOW_ID --limit N --offset N`调用list_workflow_runs。沿ASTROPHOTOFLOW_CONFIG及①默认解析定位同一workspace，不虚构当前apf已有全局--config参数；输出对应RunDetail／RunPage的JSON，业务错误保留code／fields／request_id，不直接读SQL。①仍由main.py接本机init/start/status/stop及拟新增restart；定向启停不顺带改默认。此为拟新增协议，不是当前已存在命令；没有为节点/软件另外穷举CLI。

<a id="verification-design"></a>

## 17. 接口到测试与需求追踪

### 测试文件与证据边界

已有仅指文件存在及静态读取，不代表本次通过；拟新增实施前不列可运行命令。每模块至多两个后端文件，宿主／浏览器各集中一处；UI可见事实由P-BROWSER、纯原生由P-HOST验证，具体组件回归出现后再补相称测试。

| 标识 | 状态与文件 | 维护范围 |
|---|---|---|
| E-FND | 已有：[tests/core/test_config.py](../../../../tests/core/test_config.py)、[tests/core/test_workbench.py](../../../../tests/core/test_workbench.py) | 扩充配置、端口、实际地址／身份、启停／重启；既有mock不证明新增生命周期。 |
| E-DATA | 已有：[tests/modules/data/test_ingestion.py](../../../../tests/modules/data/test_ingestion.py)、[test_import_pipeline.py](../../../../tests/modules/data/test_import_pipeline.py)、[test_calibration.py](../../../../tests/modules/data/test_calibration.py)、[test_equipment_snapshots.py](../../../../tests/modules/data/test_equipment_snapshots.py) | 保留导入、固定组、revision、接收快照、校准、原件；已有项目固定版本不证明运行采用。 |
| E-PROTECT | 已有：[tests/modules/data/test_service.py](../../../../tests/modules/data/test_service.py)、[test_display_previews.py](../../../../tests/modules/data/test_display_previews.py) | 认证／OpenAPI／清理／共享路径和素材显示缓存回归，不代替图引用与运行预览。 |
| E-TRANSPORT | 已有：[tests/interfaces/comfyui/test_proxy.py](../../../../tests/interfaces/comfyui/test_proxy.py)、[tests/integration/test_client_operations.py](../../../../tests/integration/test_client_operations.py)、[test_cli_mcp_protocol.py](../../../../tests/integration/test_cli_mcp_protocol.py) | 代理、具名客户端、CLI／真实stdio及ImageContent；迁移tools/list断言为精确三入口。 |
| E-BOUNDARY | 已有：[tests/architecture/test_import_boundaries.py](../../../../tests/architecture/test_import_boundaries.py)及[前端依赖规则](../../../../frontend/.dependency-cruiser.json) | 随实现补③④⑤公开入口／依赖，现规则已覆盖data公开入口及nodes不依赖workflows／接入层；其他增量随实现补齐。 |
| E-NATIVE | 已有：[useWorkflowAutoSave.test.ts](../../../../frontend/src/platform/workflow/persistence/composables/useWorkflowAutoSave.test.ts)、[workflowStore.test.ts](../../../../frontend/src/platform/workflow/management/stores/workflowStore.test.ts)、[changeTracker.test.ts](../../../../frontend/src/scripts/changeTracker.test.ts)、[executionUtil.test.ts](../../../../frontend/src/utils/executionUtil.test.ts)、[litegraphService.lateRegistration.test.ts](../../../../frontend/src/services/litegraphService.lateRegistration.test.ts)、[nodeOutputStore.workflowSwitch.test.ts](../../../../frontend/src/stores/nodeOutputStore.workflowSwitch.test.ts)、[jobs_cancel_test.py](../../../../engine/ComfyUI/tests-unit/jobs_cancel_test/jobs_cancel_test.py) | 原生回归基础；现新图不自动保存、迟到注册不自动升级占位实例、切图缓存与假取消队列均不证明业务闭环。 |
| E-BROWSER | 已有：[tests/browser/native-web.mjs](../../../../tests/browser/native-web.mjs) | 侧栏／画布／保存加载／CPU／素材基础；现直接queuePrompt不证明⑤统一入口或真实科学软件。 |
| E-DELIVERY | 已有：[tests/packaging/test_layout.py](../../../../tests/packaging/test_layout.py)、[test_engine_build.py](../../../../tests/packaging/test_engine_build.py)、[scripts/verify_distribution.py](../../../../scripts/verify_distribution.py) | 资源及仓库外安装；历史范围不作为本次构建／Windows发行通过。 |
| P-DATA | 已有：`tests/modules/data/test_science_inputs.py`；后续⑤联调断言待补 | ②科学输入／当前资料／范围、移除影响、所选输出及内容接纳。 |
| P-SOFTWARE | 已有：`tests/modules/software/test_service.py`；真实调用及后续维护断言待补 | ③包／网页计划确认／安装维护／许可／真实调用；替身仅单元，真实软件另证。 |
| P-NODES | 已有：`tests/modules/nodes/test_service.py`；加载／测试／画布更新断言待补 | ④JSON／校验／保存与加载／显式测试关联／确认更新。 |
| P-WORKFLOWS | 拟新增：`tests/modules/workflows/test_service.py` | ⑤SQLite关联／控制、局部结果、保存及目录检索。 |
| P-RUNS | 拟新增：`tests/modules/workflows/test_runs.py` | 运行／快照／未知重复／取消／多次预览／输出保存防重。 |
| P-HOST | 拟新增：`frontend/src/platform/astrophotoflow/workflowBridge.test.ts` | 有限连接操作、定向响应／共同撤销、端口参数／动态控件／单保存／归图。 |
| P-INTEGRATION | 拟新增：`tests/integration/test_platform_workflow.py` | 隔离workspace贯穿真实首包、离线MCP启停、取消保存、重启/history缺失及58业务协议。 |
| P-BROWSER | 已有：`tests/browser/platform-workflows.mjs`；后续跨模块场景待扩展 | 唯一跨模块浏览器文件，验软件／节点／项目图／真实运行预览／结果选择／接管交回／换客户端；不碰正常dev。 |

### 最小夹具

| 标识 | 内容 | 约束 |
|---|---|---|
| F-WORKSPACE | 隔离W1／W2，各自配置／令牌／进程；端口冲突用测试监听器 | 固定W1、不激活默认、不误动W2；凭据只核散列／出现与否 |
| F-SCIENCE | 少量合成FITS及Header；有序dv1两成员、dv2追加；P绑定dv1，Q查范围；managed/reference各一 | 原件hash／数值不变，JPEG非输入；真实素材另锁来源、许可、hash、尺寸／HDU／参考值 |
| F-PACKAGE | 清单准确版本／新版、一个操作及配套节点；新版改默认并删节点 | 替身只算单元；真实软件另证；请求202与网页确认分开，确认前零变更 |
| F-NODE | 一个custom JSON跨两项目；分别重排／改名／类型／删除／新增端口 | 使用真实端口类型，同方向唯一；参数化复用，package沿③规则 |
| F-GRAPHS | P.A与Q.B含相同节点ID；未存新图／缺依赖JSON／子图／不同持久与会话ID | SQLite只关联唯一原生JSON；分别观察save／rename／saveas／delete／草稿 |
| F-CONTROL | 绑定pageA、未绑定pageB及两token；可延迟／断开实际操作与回包 | 覆盖迟到写／未知，不以clientId／布尔值或永久回执授权 |
| F-RUN | 依赖、两个图像输出／成员及非请求分支；已知run/prompt；保存／提交／登记边界可暂停 | 假引擎只验次数，真实软件另证；未知百分比只断阶段／时间／日志 |
| F-DYNAMIC | beforeQueued s0→s1、异步serializeValue受控Promise、afterQueued s1→s2 | before／转换／save各一次；按科学参数与拓扑核对，UI表示差异可不同，不双保存／重算 |
| F-CATALOG | 58业务＋真实新能力；中英文／准确术语／相似项／模型不可用 | 锁查询及候选来源，不造分数／性能门槛；不索引偏好／聊天／科学原件 |

每次只组合证明该行为所需夹具；文件核字节／引用，运行核真实投递／调用。SQLite检查限所属模块，客户端／CLI／MCP仍走HTTP，无验收写库旁路。
### 五模块接口断言

下表引用前述唯一字段／流程，不重复DTO；零次／一次为本次可观察副作用，不承诺跨进程严格只执行一次。证据不足保持unknown。

| 编号／接口 | 场景与唯一通过条件 | 测试落点 |
|---|---|---|
| V01 ① start/status | HTTP离线且端口被占用时启动W1（W2在线）；两实际端口／Origin、身份／健康核对后才ready，重复start复用。回写失败仍报真实在线／未保存原因，不重启；partial不报ready，不改默认／W2。 | E-FND、P-INTEGRATION、E-TRANSPORT |
| V02 ①↔②③⑤ 配置／维护 | 改并发后保存值／采用值及restart_required分开，不重启换连接；旧token409不覆盖。导入／预览／软件／queued或unknown时拒restart且无自动请求，检查到维护期间不接冲突；stop排空至实退再清记录，断连先status。 | E-FND、E-DATA、P-INTEGRATION、P-BROWSER |
| V03 ② 导入／任务 | 按钮及MCP上传／授权目录；同批跳过、独立导入新身份、retry/resume沿已接受快照／阶段；修改设备预设不改历史，目录越界拒绝。登记／原件／解析／预览分开，现HTTP／CLI结果保持。 | E-DATA、E-PROTECT、E-TRANSPORT、P-BROWSER |
| V04 ②⑤③ 固定数据／内容接纳 | dv2追加不改变图中dv1成员／顺序，新run用纠正资料，旧run／接收不变。按AssetContentAccept三字段接纳201，同Asset新版本／revision+1，旧事实和其他固定引用不动；重复旧body409 REVISION_CONFLICT，再变409 SOURCE_CHANGED，断连GET核对。set_data只换指定节点reference，组须新DatasetVersion；缺失／错误项目／未确认／不支持阻塞，reproducible失败不降级，记录实际成本且固定字节不重复制。 | P-DATA、P-RUNS、P-INTEGRATION、P-HOST、E-DATA |
| V05 ③ 安装／准备／网页确认 | MCP请求202仅PendingSoftwareAction.awaiting_confirmation／plan／confirmation_url；确认前软件／定义／图零副作用。软件页显示同UUID计划后真实确认，MCP自报confirmed无效；过期／范围变409。GET回真实安装／位置／ready／错误，许可不ready、敏感值由用户直输无泄漏；无活动图可确认，不授画布权，不接任意URL／脚本／版本。 | P-SOFTWARE、P-INTEGRATION、P-BROWSER、E-TRANSPORT |
| V06 ③④⑤ 更新／卸载 | 两图预览后请求202；确认前图／包变或新run使旧计划409失效，busy/unknown拒绝无延后执行。有效确认只改已示范围，package变化参数新默认、缺失／卸载节点保留；逐定义／图报告部分事实，不改在途／历史／原件／custom。 | P-SOFTWARE、P-NODES、P-WORKFLOWS、P-HOST、P-INTEGRATION、P-BROWSER |
| V07 ④⑤ 保存／显式测试 | custom保存后跨项目使用，saved/loaded/ready分开；测试失败不阻保存。测试输入参数落实明确测试图，再沿唯一准备／保存／受理链；精确node_test关联被测内容，一般整图run不冒充测试，修改后旧测试不标新通过，不另存证据权威。 | P-NODES、P-RUNS、P-HOST、P-INTEGRATION、E-NATIVE |
| V08 ④⑤ 确认节点更新 | 预览列图／实例、默认及保断线；custom全部参数新默认。同方向同名同类型含重排保线，改名／类型／删除仅断对应线，新增不自连，同方向重名拒绝。冲突保草稿，在途／旧run不变；已固定preparing/queued/unknown也阻替换。 | P-NODES、P-WORKFLOWS、P-HOST、P-INTEGRATION |
| V09 ⑤ 原生文件联动 | 首次save落实原生ID／位置／项目，rename改关联、saveas新ID独立方案，重开保同图且不扩素材权限。缺依赖JSON保留、保存非可运行；delete清关联／专属预览但保已存素材／原件／run。草稿非保存，无第二JSON／永久编辑／服务端草稿。 | P-WORKFLOWS、P-HOST、P-BROWSER、E-NATIVE |
| V10 ⑤ 页面／当前控制 | 未绑需实际按钮，禁止猜页／自赋权；current_graph为本次真实最新页图，非saved_graph，离线未知null+reason。局部支持操作／原生撤销可用，整图仅明确导入替换。A切B暂停A新写／run且B不变，已受理继续；手动参数／节点／线／布局／撤销先失效旧权，查看缩放平移／切页不接管。读／重连／新上下文不恢复已撤销控制；同目标仍允许时换客户端可继续；非画布业务不受关页限制。 | P-WORKFLOWS、P-HOST、P-BROWSER、P-INTEGRATION |
| V11 ⑤ 部分应用／回包未知 | op0加节点成功，op1不支持失败，op2未执行；EditResult准确返实际ID、失败位置／原因、token与保存分别状态，不假回滚。丢响应先读，不重放或自动继续，ID不猜；错目标／前置token在op0前拒绝，零应用。 | P-WORKFLOWS、P-HOST、P-BROWSER、P-INTEGRATION |
| V12 ⑤ 单次准备／单保存／唯一提交 | 按钮／快捷键／auto/MCP均验第14节唯一顺序：beforeQueued、graphToPrompt、save各一次，保存成功且长准备后check才领域POST一次。快照／有效prompt采用s1；afterQueued的s2仅属下一编辑。允许UI规范化差异，无save(snapshot)／双保存／重转；异步科学语义不明或手改GRAPH_CHANGED，保存失败／切图／控制失效也零投递且保草稿。人工无需先交回Agent。 | P-HOST、P-RUNS、P-BROWSER |
| V13 ②③④⑤ 范围／保证／科学执行 | 整图／targets含必要依赖、准确终点及未执行部分；一好一坏请求终点也须全拒且队列无prompt，不支持／空输出不静默缩小或全设终点。连续同参确实科学重算，非run编号伪失效；缓存回放非新处理。原件只读，HDU／资料／校准／顺序同快照，产物完整／格式检查后可用，部分不报全成功；③只写work，裸extra_data不能绕托管上下文。 | P-DATA、P-RUNS、P-SOFTWARE、P-INTEGRATION、E-NATIVE |
| V14 ⑤ 重复／未知／持久事实 | 同run同候选仅查已有状态、无第二投递／调用；异内容409。固定prompt后及引擎受理回包前中断先核run/prompt／调用，无证据unknown不重提，query无执行副作用。history清除／重启不删既有SQLite事实；完整重跑新run并重新保存，旧图／参数／状态不覆盖；不承诺严格exactly-once。 | P-RUNS、P-INTEGRATION、P-BROWSER |
| V15 ③⑤ 定向取消／实际停止 | A执行B排队，取消B不误停A；分别验送达仍运行／不可中断／丢观察／真实停止。请求、移队、停止依据分开，HTTP200或native cancelled非软件已停；unknown仍占用，更新／重启不当空闲，实际停后释放。部分文件不算科学成功，重复cancel不建run。 | P-RUNS、P-SOFTWARE、P-INTEGRATION、P-BROWSER、E-NATIVE |
| V16 ⑤ 自动／多轮预览 | 两次不同参数、两图像输出／成员均按OutputLocator关联真实run参数，实际完成才缩图，不扩分支／逐帧落库。第14节唯一JPEG经原生/view及GET /api/v1/runs/{run_id}/previews/{preview_id}读同文件，不复制／挂载根。A完成归A，B同ID不串不抢视图；重开／history清除仍查已存预览。缩图失败独立、旧缩图不证明完整输出还在，MCP为ImageContent。 | P-RUNS、P-HOST、P-INTEGRATION、P-BROWSER、E-TRANSPORT |
| V17 ⑤② 所选输出／移除 | 只选一个完整成员命名托管，未选not_requested不登记。SaveOutput.output沿唯一OutputLocator且path/run一致；并发／断连／归位登记中断后同task/asset续查补关联，不多建／重算，不凭requestid或事务掩文件部分事实。preview/path／已清理输出不能冒原件。移除先列图节点，影响变旧确认409，确认留缺失节点且校准／任务保护仍在；删图不删已存素材。 | P-DATA、P-RUNS、P-INTEGRATION、P-BROWSER、E-PROTECT |
| V18 ⑤／MCP／Skill 客户端 | tools/list恰三入口，原58项data迁移子集精确相等，新增3项data.*及其他模块按本节固定表另验（data前缀当前设计合计61项），各ID真schema／固定映射／真实协议等价，HTTP／CLI语义／结构化错／ImageContent保持。已知直达，未知分型Top10，版本ready真实；模型故障显式keyword+原因、恢复据实hybrid。定义不可直接call，禁止任意URL/method/shell/Python。Skill／参考／配置同步并刷新列表；下一用户交互读最新目标／同步／控制，手改后安静，读不恢复控制。 | P-WORKFLOWS、E-TRANSPORT、P-INTEGRATION、P-BROWSER |

所有状态／code沿主类型，不由测试自造近义词；图应用／保存、run受理／执行、输出检查、取消请求／实际停止及素材保存分别断言。网页确认来源、白名单加载、最终入队guard和无网页运行观察均为首闭环原型阻塞项；通过一个子场景不能代签整条AT。

### FR全量追踪：近期与延期

近期指S1～S5中本次已定义的接口行为；表中“回归”仍需实施候选重新提供证据，不继承历史通过为本次通过。

| FR | 近期验证／文件落点 | 延期范围及静态保留方式 |
|---|---|---|
| FR-01 | V03／04／09／17；固定项目素材、唯一图关联、保存／改名／另存／重开；E-DATA、P-WORKFLOWS、P-BROWSER | S6完整归档／导出及跨次连续性；在当前上下文保留待办，链接AT-20／21／27，不创建空导出接口 |
| FR-02 | V04／09～12；原生保存／缺依赖JSON、局部编辑、共同撤销、网页目标；P-WORKFLOWS、P-HOST、P-BROWSER | S6复杂节点支持随对应任务补；不恢复永久逐编辑或服务端草稿要求 |
| FR-03 | V05／06／13；项目维护首包、网页具体计划确认、许可、目录、更新及实际调用；P-SOFTWARE、P-INTEGRATION | S6多软件／完整维护；首包未锁定不得记为ready或业务验收完成 |
| FR-04 | V03／04／17；既有导入／设备／校准回归及科学引用交接；E-DATA、P-DATA | S6整夜目标汇总／历史关联、标签、移动／重定位／完整治理；保留疑义不合并和今晚范围要求 |
| FR-05 | V03／16的既有显示预览及新增运行预览；E-PROTECT、P-RUNS | S6完整科学查看、ROI／配准／拉伸条件和指标；AT-19保持延期，不以缩图通过替代 |
| FR-06 | 保留编号，无测试或接口 | 静态检查其状态为reserved，不恢复旧需求 |
| FR-07 | V05／10／18；精简入口、58业务、Skill／workflow直达、分型检索、真实客户端；E-TRANSPORT、P-WORKFLOWS、P-INTEGRATION、P-BROWSER | S6完整背景／记忆随FR-12；Judge仅后续边界，不添加模型推理／聊天验收 |
| FR-08 | V10／11／12／16；实际写入处目标／控制、接管／交回、未知、原生撤销、后台归属；P-HOST、P-WORKFLOWS、P-BROWSER | S5完整客户端证据未具备前保留待验证；不新增通用协作账本 |
| FR-09 | V12～15；保存与动态参数、范围／保证、科学调用、run_id核对、持久事实、取消；P-RUNS、P-INTEGRATION | S6固定结果显式续跑及跨软件／完整故障恢复；继续保留AT-12／13／14／17／18的S6部分 |
| FR-10 | V04／13～17；当次事实、多轮逐节点预览、选择完整结果保存及来源；P-DATA、P-RUNS、P-BROWSER | S6完整比较及跨软件来源；不能为来源展示预建独立真相或自动登记所有文件 |
| FR-11 | V09／14／16／17；另存、运行事实／预览、原件保护、所选结果和删除联动 | S6完整治理／旧字节恢复／导出／固定结果续跑；旧文件不存在必须如实说明，不承诺靠预览复原 |
| FR-12 | S5只验证V18新客户端读取⑤已确认事实，读取不恢复已撤销控制；P-INTEGRATION、P-BROWSER | S6偏好历史／恢复／删除、项目背景／经验／摘要及作用域治理；保留AT-22／30／31，不提前创建记忆API或测试空壳 |
| FR-13 | V01／02／05／06；启动实际地址、配置、维护准入及首包准备；E-FND、P-SOFTWARE、P-INTEGRATION | S6完整安装恢复／升级维护；失败恢复边界逐包锁定，不从首包扩称全部软件支持 |
| FR-14 | V01～18各实际权限边界；E-TRANSPORT、E-BOUNDARY、P-INTEGRATION；错误目标／路径／来源、凭据和托管调用均有拒绝断言 | S6Python／复合执行范围随实际环境定；不虚构恶意代码沙箱，不添加通用角色平台 |
| FR-15 | E-BOUNDARY、E-DELIVERY及V01／02的固定资源／数据独立回归；记录Windows实际版本组合 | S6完整Windows发行／升级恢复；Linux／WSL后续独立验收，节点分发不前移；本轮不重建发行 |
| FR-16 | V07／08／12；JSON共享定义、可选测试关联、加载、跨项目参数／端口更新与在途保护 | S6Python／复合局部副本及运行环境，节点导出安装后续；不恢复测试门禁或旧版长期并存 |

### NFR与AT全量追踪

| NFR | 近期可判定检查 | 尚待测量／延期项 |
|---|---|---|
| NFR-01 | V01／02／06／09／17与E-DELIVERY；程序资源、workspace、原件、结果／预览和令牌边界准确 | S6完整升级恢复；无workspace搬迁服务 |
| NFR-02 | V03／04／13／16／18；网页／MCP只交必要资料和缩图，科学文件经受控文件交接；大文件操作异步 | 固定规模下的峰值内存／吞吐随首包和数据规模测量，门槛未定不报通过 |
| NFR-03 | V02／05／13／15／16与P-BROWSER；长任务中画布／侧栏仍可交互，进度有真实依据，无百分比时显示阶段／时长／日志 | S0建立机器／负载清单，相关功能可测后确定门槛 |
| NFR-04 | V01／02／11／14／15／17；中断窗口均先核对，未知不推断成功／失败、不重放 | S6完整故障恢复，不引入通用恢复对象 |
| NFR-05 | V13／18；无生成式模型配置仍可手动真实处理，embedding不可用明确关键词降级 | 本地模型具体后端／资源测量待原型；记忆不默认向量化 |
| NFR-06 | V01／04／10／13／16／18记录启动、导入、首次预览、图命令确认、事件重连、日志、内存和检索指标的测量条件 | 性能门槛依据固定基准补齐；文档静态检查不验证耗时或流畅性 |
| NFR-07 | V04～13／18；明确支持版本、格式、端口、控件和软件，不支持明确拒绝；E-DELIVERY保留构建资源范围 | 标准热加载、复杂节点及Linux各有原型／平台出口，不从网页刷新推定支持 |
| NFR-08 | V01／07／11～18；请求、run、prompt、调用、输入、定义、输出与日志能关联且无凭据 | S6诊断导出／完整治理；无实际调用不虚构调用记录 |

每个AT以下表一行作为主追踪，混合阶段明确分开；其他表可以引用，但不得仅因一个子场景通过把整条AT标完成。

| AT | 近期验证 | 延期或保留状态 |
|---|---|---|
| AT-01 | V01／02、E-DELIVERY；S1生命周期／实际地址／配置 | S6全新安装与最终交付；本轮未运行 |
| AT-02 | V05；缺软件／许可／实际所需资源的原因 | 首包外的资源组合随适配扩充 |
| AT-03 | V06／08；软件包与自制节点分别确认更新 | S6复杂节点及热加载组合另证，未验证明确刷新／重启条件 |
| AT-04 | V03／04；按钮／Agent现有导入、固定科学引用 | S6整夜目标／历史疑义汇总 |
| AT-05 | V04；观测hash＋资料revision接纳为同Asset新版本；重复确认／并发再变409、set_data仅选定节点 | S6完整旧内容恢复；旧字节缺失真实不可恢复，不因新版本接纳改旧run／其他refs |
| AT-06 | V09／10／12／16／18；S3保存、S4多轮预览、S5安静接续 | 各子阶段分别记待实现／待验证 |
| AT-07 | V10／11；旧写、离线草稿、重连核对 | S5真实客户端证据，不由mock替代 |
| AT-08 | V09／10／11；局部操作、共同撤销、另存 | 不恢复永久逐编辑／作者选择性撤销 |
| AT-09 | V04／10／16；固定数据及目标绑定、切图暂停、后台归属 | S5完整多页客户端证据 |
| AT-10 | V10／18；无网页仅查询、非画布业务按所属规则 | 无后台多画布写／转换能力承诺 |
| AT-11 | V09／10／13；缺依赖保留及不支持转换／控件拒绝 | 第三方特殊节点按受支持范围逐项验 |
| AT-12 | 无近期双软件完成声明 | S6两个实际外部软件交接，固定科学数据／精度／元数据／来源 |
| AT-13 | 近期首软件的调用观察由V13／15覆盖 | S6各实际支持的调用方式及取消组合 |
| AT-14 | V13／14；连续同参实际处理、不跨运行自动复用 | S6固定结果显式续跑记录复用 |
| AT-15 | V13；整图／受支持目标的依赖、终点、阻塞 | 视频具体软件／范围随适配，首帧预览不是整段处理证据 |
| AT-16 | V07／08／12／13；保存、动态参数、异步一致和在途快照 | 首次真实节点／软件组合必须补证 |
| AT-17 | V15；请求与实际停止、定向取消／占用 | S6更多软件不可中断及完整恢复组合 |
| AT-18 | V14／17；重复、提交未知、history缺失、补登记 | S6完整故障恢复；不承诺严格exactly-once |
| AT-19 | 仅保留输入／运行／预览关联基础V16，不算比较通过 | S6 ROI、对齐、拉伸、算法及原件保护 |
| AT-20 | V09／14／16；历史用图／参数、另存和完整重跑 | S6固定结果续跑；不从预览／内存缓存恢复 |
| AT-21 | V04／17的缺失事实表达保留 | S6引用旧字节恢复完整场景 |
| AT-22 | 无近期记忆治理完成声明 | S6候选／来源／作用域、启停删、偏好历史恢复／正文删除 |
| AT-23 | 编号保留 | 不创建测试或接口 |
| AT-24 | V10／11／18；连续普通操作、手改接管、明确交回 | S5真实客户端与断连证据；客户端预算不变成平台功能 |
| AT-25 | V05／06；POST202只请求、平台网页确认当前具体plan、确认前零副作用、过期409、GET package最终事实 | S6完整安装／升级恢复；busy不排自动更新，不建审批账本／任务队列 |
| AT-26 | V03～06／10／13／18；授权目录、清单包、托管调用及非任意URL／Shell | S6用户代码环境随实现确定，不扩称通用沙箱 |
| AT-27 | 保留E-PROTECT已有迁移备份和E-DELIVERY历史范围 | S6平台升级／恢复；本轮不执行迁移或备份 |
| AT-28 | V13、P-INTEGRATION／P-BROWSER；一个真实CPU／本机科学操作 | 无生成式图像模型；普通CPU演示图不足以通过 |
| AT-29 | V07／08；共享JSON定义、可选测试、更新端口／参数及保护 | S6Python／复合局部副本，导出安装后续 |
| AT-30 | 无近期偏好完成声明 | S6偏好／项目覆盖、用户表达与Agent分析区分 |
| AT-31 | V10／18；S5换客户端读⑤确认事实，共享当前允许状态但不恢复已撤销写权 | S6主动摘要及完整背景／记忆；无完整聊天存储 |
| AT-32 | V03／04／17与E-DATA；快照、固定集合／校准、引用保护 | S6完整治理组合；既有保护不得随新接口取消 |
| AT-33 | V05／06／18；固定包／配套节点／原因／网页计划确认／更新／卸载的双入口，MCP202不等于已安装 | S3补节点，S6扩软件／完整维护 |
| AT-34 | V18；exact3＋58、已知直达／分型Top10／显式降级／Skill客户端 | 中英文排名与性能随原型基准补，未测不报通过 |

### 真实证据出口

首包任务锁真实软件／输入／节点／图；P-INTEGRATION保服务协议，P-BROWSER保实际网页，不能用mock／CPU图代科学软件，或只在MCP／页面一侧检查。证据至少记录日期、候选提交及未提交差异、Windows／Python／Node／引擎／网页／软件／模型版本、隔离workspace／输入hash、入口及run／prompt／call／输出定位、预期／观察／限制和日志。报告进.artifacts，矩阵分列单元／契约、真实软件、浏览器、真实MCP及用户业务体验；后者不能自动代签。未验Linux／WSL／视频／软件组合继续未验证／跳过，不计通过。
