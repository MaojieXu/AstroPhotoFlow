# 接口与契约

## Bundle 与节点目录

此节覆盖早期固定 Siril 原生节点描述。公开 `GET /api/v1/nodes?query=` 和 `GET /api/v1/nodes/{definition_id}` 提供 `NodeCapability`；`POST /api/v1/canvas/graph` 读取/修改在线图，`POST/DELETE /api/v1/software/preview` 处理 Bundle 轻量显示。原生执行切换至内部 `/internal/native/bundles/calls`，不作为公开任意执行 API。旧 Siril 预览及命令查询仍可消费。

CLI：`apf nodes list --query stretch`、`apf nodes get <definition_id>`、`apf canvas pages`、`apf canvas get <page_id>`、`apf canvas edit --data @edit.json`。MCP 对应 `list_nodes/get_node/get_canvas/edit_canvas`，已有工具保留。get_canvas 是读取，不取得控制。

编辑请求提供从 pages/get_canvas 取得的最新目标和内容标记；add_node 使用 definition_id，set_parameter 使用实际 node_id/name/value，connect 使用实际源/目标 node_id 和端口名。每次只做一个操作，使用返回的新 content_token；applied=null 时查询同一 operation_id，不自动重放。网页变更、撤销、切图或断连不会自动恢复授权。

软件包响应补充 bundle_version、bundle_commit、restart_required、migration_required。安装确认中明确 Git tag/commit 与重启；真实节点载入前为 not_ready，不以 checkout 完成代替可用。当前操作、节点与预览参数来自 Bundle 操作定义，旧命令资源仅为只读发布资料。
2026-10-29 Siril显示专用接口：`POST /api/v1/software/packages/siril/autostretch-preview` 接收固定InputReference、member_index、consumer_id、generation及linked／shadowsclip／targetbg，返回 image/png；不接受文件路径、脚本、URL或通用操作名。`DELETE /api/v1/software/packages/siril/autostretch-preview/{consumer_id}` 释放本次查看；认证及同源代理白名单保持。预览只调用固定AutoStretch处理平台生成的线性样本，不执行工作流，不登记新素材，不作为科学输出。未安装／维护／来源变化明确返回错误。正式原生执行接口保持内部使用；修复其HTTP会话跨事件循环复用问题。OpenAPI按实际路由生成。


2026-10-29 软件接口增量：`POST /api/v1/software/packages/{package_id}/uninstall` 接收 `{package_token}`，返回 202 `PendingSoftwareAction`；仍须同一原生页面确认，不提供公开 confirm HTTP。卸载只移除程序副本，定义及画布保留。安装／卸载共享包 token、动作去重和繁忙拒绝；OpenAPI 已按源码导出。首个 Siril 节点使用不经普通网页代理、未列入 OpenAPI 的 `/internal/native/siril/calls` 提交／状态／定向取消能力，不新增 CLI 或 MCP 直接执行工具。


2026-10-29 查看描述补充：MediaState新增可选phase（queued、preparing或null），只细分generating的排队／生成阶段，终态为null；既有status、接口地址和科学引用不变。未传consumer_id的调用保持完成语义；传入consumer_id时由generation或DELETE consumer释放兴趣，只有无人使用时取消共享任务。

2026-10-29 统一媒体查看候选：在共享素材版本和项目固定素材引用的既有`previews`作用域新增`POST /viewer`、`GET /viewer/{key}/status`、`GET /viewer/{key}/tiles/{level}/{x}/{y}`、`GET /viewer/{key}/{file}`（file仅overview／video）及`DELETE /viewer/consumer/{consumer_id}`。prepare返回200／202及MediaState，包含原尺寸、媒体种类、数组／切片选择、状态、错误、缓存key和读取URL；MediaSelection支持固定HDU、NumPy显示轴／切片、帧编号或呈现时间戳，以及代理请求。consumer_id／generation只管理内存中的当前观察，缓存返回清除这两个临时值；不产生新的任务实体。状态查询不启动解码，显式准备可重试失败／被回收缓存；无效瓦片／选择为422，原件变化或清理冲突为409，越权归属为404。瓦片为PNG，概览JPEG，视频支持Range／If-Range及206／416；ComfyUI网关按块转发媒体和范围头，不缓冲整份视频。旧display／上传／CLI／MCP接口保持，OpenAPI为当前精确类型。实现、编译和未执行验证分别见[查看流程](../development/library-preview.md)、[验证矩阵](../development/test-matrix.md#media-viewer)。

2026-10-28 选择器焦点／取消修订：imports/select-local绑定当前前台宿主并在打开时置前一次。同服务已有导入选择器时返回409 LOCAL_PICKER_BUSY，原请求及窗口保留。网页取消通过AbortSignal断开请求，网关关闭对应上游连接，服务关闭并回收该次选择器；正常系统取消仍返回cancelled=true。请求及响应字段不变，没有新增选择会话接口、存储或导入任务。

2026-10-28 本机直接选取修订：新增 `POST /api/v1/imports/select-local`，请求 `{mode:"files"|"folder"}`，调用Windows系统选择器，返回 `{cancelled,files:[{path,name,size}],name,folder}`。仅选择并列出文件，不复制、不建立任务；文件夹只取当前层支持格式，取消返回空清单。网关等待用户完成选择，不采用普通业务接口的10秒读超时。

`POST /api/v1/imports` 的sources现可省略root_id并提供本机绝对path，采用storage_mode=managed，无需配置任何根目录。绝对文件夹也是当前层枚举，受理时固定清单和来源size／mtime。任务内root_id为空字符串表示直接本机来源；登记、复制校验、恢复和重试使用保存的绝对路径，不动态登记授权根。保留既有root_id＋相对POSIX路径与reference模式；旧上传接口不删除。CLI `apf imports local --data '{"sources":[{"path":"C:/Images/a.fits"}],"storage_mode":"managed"}'` 与MCP import_local使用同一请求，不必经过选择窗口。此条覆盖下文较早的“网页必须在授权目录内选择”。

<a id="library-canvas"></a>

## 素材直接加入活动画布（本地候选）

Nodes 2.0 展示新增只读 `POST /api/v1/library/canvas-data/inspect`，请求为 `{reference:InputReference,member_index?:0}`。member_index是引用中选定成员列表的零基序号，不是原组position；单件只能为0。响应包括组标题、选定总数、当前序号、当前素材／固定版本ID、名称、原件availability、当前parameters／设备名称、固定版本format／原始width／height／BITPIX／像素类型，以及thumbnail的状态、同源URL及错误。组内所有引用的原始position／版本匹配检查保留，不跟随current_version追加或重排。不存在、越界、成员不匹配明确拒绝；原件当前缺失时可读现有资料，不能据此宣称可处理。

接口只查数据库，不读取原件、复制文件、创建任务或写资料。未记录的尺寸等返回null，不用缩略图尺寸代替。预览URL仅在对应固定版本已有预览时返回；无活动任务且无预览返回not_ready，不制造永久“生成中”。节点默认仅获取当前成员缩略图；用户显式重试可调用既有display调度／状态／读取接口，不调用auto-stretch改变配方。新增响应类型CanvasInspectOut及UI消费模型同步OpenAPI，原有加数据与MCP／CLI应用协议不变。

| HTTP | CLI | MCP | 真实结果 |
|---|---|---|---|
| GET `/api/v1/canvas/pages` | `apf canvas pages` | `list_canvas_pages()` | 仅当前连接实际报告的画布；含 page_id、workflow_id、graph_id、title、content_token、control_token。control_token 为 null 表示未授权 |
| POST `/api/v1/canvas/requests` | `apf canvas add-data --data @request.json` | `add_canvas_data(body)` | 指定目标画布添加一份固定素材／组引用；不会执行图或另存原件 |
| GET `/api/v1/canvas/requests/{operation_id}` | `apf canvas result OPERATION_ID` | `get_canvas_request(operation_id)` | 当前引擎会话的实际应用回执；断线／超时不等于未应用，引擎重启后无历史回执 |

请求为 `{operation_id,page_id,workflow_id,graph_id,content_token,control_token,source:{entry_type,id,version_id,member_indexes?}}`。先读当前列表，并在网页更多菜单明确“交给 Agent（加入素材）”；有多个目标时不能猜测。每个用户操作使用一个 UUID。成功为 `applied:true,node_id`；拒绝为 `applied:false,error`；未核对为 `applied:null,error`。相同操作 ID／相同完整命令在当前引擎内只发送一次，ID 被其他命令使用返回 409；未知后查询同 ID，不换 ID 盲目重试。

领域服务核对②的公开 `prepare_canvas_data`，通过现有原生服务／WebSocket向指定 socket 发送命令。原生连接提供页面身份，浏览器提交的 page_id 不能替代它；前端在实际写入前核对当前图、内容和控制标记，手动变化、切图和连接变化撤销授权。SHA-256内容标记排除视口缩放／平移和派生revision，保留节点参数、拓扑和布局。结果仅表示节点应用，不表示图已经保存到文件、科学输入已为某次运行固定或处理已开始。当前仅支持加数据，非完整B51／B52图编辑／运行协议。

内部原生路由 `/astrophotoflow/internal/canvas/*` 只接受服务令牌；不作为网页任意转发接口。会话页面观察及操作回执只在内存中，无新增数据库表、历史页或通用任务系统。MCP服务需重新连接／启动以加载新工具；保留既有数据工具。

素材入画布候选：`POST /api/v1/library/canvas-data` 接收 `{entry_type:"asset"|"dataset",id,version_id,member_indexes?}`，返回 `{native_type:"APF_DATA_REFERENCE",title,reference}`。必须明确固定版本；可选组成员索引为非负、升序、不重复的原始 position；省略即该固定版全部成员。服务核对归属、共享范围、active 和原件已就绪，不读取预览或复制大文件。空组、未就绪成员、过期归属明确失败，不静默减少组范围。准备引用不代表画布应用。CLI `apf library canvas-data --data @selection.json` 与 MCP `prepare_canvas_data(body)` 复用该 HTTP 能力；页面按钮／拖放复用原生节点创建及撤销，异步准备期间切图时拒绝落入新图。

本机托管导入候选：网页复用GET import-roots／entries及POST imports，传递明确的当前层文件清单和storage_mode=managed，既有上传及CLI／MCP接口不移除。POST imports在受理时将目录或文件范围冻结到task.sources.entries，并保存来源size／mtime，后续新增文件不自动加入。已有task报告JSON新增report.content（total、succeeded、failed、skipped、metadata_failed、bytes_total、bytes_copied、completed）和report.preview（total、available、failed、unsupported、completed），registration和终态协议保留；原件阶段就绪独立于预览完成。TaskOut.report的OpenAPI描述同步，不新增数据库表或HTTP路由。

本文和 OpenAPI 描述已实现接口；[五模块接口契约与文件级详细设计](platform-contracts.md)维护未来操作、精确类型与签名、文件职责、调用流和测试条件。产品目标与后续 MCP 范围见[现行需求](../requirements/README.md)。拟新增文件与接口不代表已实现或注册。

数据引用、节点定义、当前工作流保存及运行结果的责任和语义统一见[总架构的四类边界](../architecture/overview.md#5-四类跨模块契约)。具体输入输出、失败含义及未来 HTTP／MCP 设计集中在[契约文档](platform-contracts.md)，不向 OpenAPI 添加占位。

设备组合列表 `GET /api/v1/equipment-setups` 的 `sort_by` 支持 `created_at、name、camera、telescope、mount、filter、accessory`，默认仍为创建时间倒序；新增值仅用于组合接口。设备列按当前设备名称在服务端排序后分页，同类多件按组合内顺序拼接比较，空值在升降序中均放最后，相同值按组合名称及ID稳定排序；历史 `optical_system` 计入 `telescope` 排序。`q/status/component_kind` 继续先过滤再分页，响应结构不变，无新增HTTP操作。

M1新增 `GET/PATCH /api/v1/settings/workbench`：读取固定当前workspace的保存／采用值，PATCH携带config_token，冲突409、显式null默认位置或无效字段422；保存不重启。网页重启扩展后共82项公共HTTP操作。M2新增素材内容观察与确认两个HTTP操作；B31增加只读软件包列表和版本绑定的Siril 1.4.4命令目录（含逐命令参数、限制、风险、定义／registry／CLI状态备注），B32增加软件详情、安装计划请求和准备查询，当前加上设备直接删除预览／确认共92项；代理及OpenAPI快照已同步。安装请求只返回等待用户确认的计划；点击确认仍须真实工作台页面的同一WebSocket链路，当前尚未验证。内部maintenance、shutdown和page事件不进入公共OpenAPI或MCP。

网页重启新增 `POST /api/v1/settings/workbench/restart`（请求为 `{operation_id: UUID字符串}`，202受理）及 `GET /api/v1/settings/workbench/restart/{operation_id}`（当前网页请求回执，尚未登记为null）。前端先持有编号；POST断连只查询，不重发。控制互斥409、启动控制器失败503；子进程执行原有restart，繁忙／未知／实际完成分别回执。少量最新受理结果保存在workspace的`run/web-restart.json`，不建立历史账本。内部维护与shutdown仍不公开；现有MCP保持。
设备管理新增 `POST /api/v1/equipment-management/delete-preview` 与 `/delete`：选择仅含 equipment／equipment_setup／capture_preset，逐项提供 id 和 revision；确认请求携带当前 preview_fingerprint，引用变化返回409。设备关联从组合移除，预设设备默认值清除；素材、固定版本及已受理任务保留设备快照。删除组合连同所属预设，保留独立设备。Python客户端提供 preview_equipment_delete／delete_equipment_entries；本轮不扩展CLI或MCP工具，既有项目及归档接口保留。

HTTP 服务前缀为 `/api/v1`；浏览器经原生网页服务的 `/astrophotoflow/api/v1` 同源代理访问。认证、版本冲突、错误 envelope 和请求 ID 延续当前实现。

[openapi.json](openapi.json) 是实际应用生成的契约快照。修改接口时同时核对处理逻辑、Pydantic 模型、代理白名单、前端 Zod 和相关测试；不能用路由数量相等代替行为一致。

```powershell
uv run --locked --no-sync python scripts/export_openapi.py
uv run --locked --no-sync pytest tests/modules/data/test_service.py -k openapi
```

CLI 提供 `apf init/start/status/stop/restart`、`mcp-config`、`mcp`、`import-photo`、`task`、`assets list/get/parameters`。服务 CLI 保留 `apf-service serve`、`db status/upgrade` 和 `previews backfill`。

单图自动显示拉伸：前端打开大图时调用 `/api/v1/library/assets/{asset_id}/versions/{version_id}/previews/display/auto-stretch`（POST，无用户参数），优先复用缩略图已保存MTF（组内同Object兼容subframe可来自首张有效帧，masterframe各自测量）；没有MTF时后台分析当前原件，统计改为固定种子的空间分层随机样本，最多262144个空间位置，RGB背景白平衡及MTF算法保持。首次测量按既有事务更新该版本大图和缩略图；已有配方仅生成显示缓存，不重新测量。任务report可含preview_stretch_groups，每组保存auto_stretch与reference_version_id，不改变任务状态或请求响应模型。已有结果200、生成任务202、状态轮询及不强制重算保持；`stretch`仍为algorithm/input_offset/white_balance/shadows/highlights/midtones或null。项目固定引用的同名接口、MCP／CLI与科学参数不变。

MCP 通过 `apf mcp` 提供 stdio 服务，现有五个名称保持兼容：`import_photo`、`get_import_task`、`list_assets`、`get_asset`、`update_asset_parameters`。结构化 HTTP 客户端、CLI 和 58 个 MCP 工具覆盖批量上传、配置根目录导入、任务、资产及逻辑组、项目固定版本引用、设备、使用组合／所属预设、校准关联、按需预览和回收站。

完整命令／工具清单、实际请求模型、配置与例子见[素材库 Agent 工具](../development/library-agent-tools.md)。项目内 [AstroPhotoFlow library Skill](../../.agents/skills/astrophotoflow-library/SKILL.md) 提供可复用工作流，无需全局安装。旧单图导入已去除 Light/subframe 强制分类，省略分类使用后端自动规则。

[③软件概要](../../src/astrophotoflow/modules/software/README.md)记录B31命令目录及B32软件安装计划／准备查询；实际下载安装、网页确认和节点加载仍待真实验收。[④节点概要](../../src/astrophotoflow/modules/nodes/README.md#handoffs)规定可编辑定义、可选测试及确认更新；B41已有JSON定义存储，配套NodeDetails HTTP及原生加载仍待B42。

[⑤概要](../../src/astrophotoflow/modules/workflows/README.md#handoffs)统一项目当前图、原生执行、运行记录、自动图像预览及Agent交互。当前图复用原生JSON文件，不另建可编辑副本；重要方案另存，会话撤销和本地草稿复用，不设计永久逐编辑修订、服务端草稿、转换实体或永久回执。首版Agent改图／新提交限明确活动网页，切走暂停，已有运行继续且预览归原图。当前目标／内容／控制须在实际写入和新受理处核对，原生userdata写入尚不提供这些规则。

调用、保存、实际显示、执行和所选完整结果保存分别返回真实情况；未知先查询，request ID和prompt_id不自动提供防重，取消受理不证明软件停止。预检、输入准备、任务关联、取消和素材保存情况合入同次运行，不预设独立资源类型。数据见[⑤设计](../architecture/data-models/05-workflows.md)，未来操作及字段见[⑤契约](platform-contracts.md#workflows)：局部改图为主，整图只用于导入或明确替换；目标网页点击“交给Agent”绑定，保存当前画布成功后运行。新增桥接仍待实现／验证。

⑤统一目录和[按需检索](../requirements/README.md#tool-discovery)沿用Skill直达、混合Top10及显式关键词降级。未来精简MCP整体替换58工具，不留旧入口／别名／双轨，数据业务仍共用HTTP／CLI，实施时同步Skill／参考／配置和真实客户端测试。本轮现有工具、五个兼容名称、注册及Skill保持，Judge不增加评分API或实际端口。

未提供的 PATCH 字段保持原值，null 清空，0 是有效值；revision 冲突和错误 request ID 明确传回。数据集发布同时接受固定校准版本、组默认和成员覆盖；永久清理仍必须提交当前回收站预览 fingerprint 并遵循引用保护。配置记录先移入回收站，再预览并确认永久删除。配置方式见[工作台使用](../development/workbench.md)。

设置回收站接口为 `GET /api/v1/settings/trash`、`POST /settings/trash/archive`、`POST /settings/trash/restore`、`POST /settings/trash/delete-preview` 和 `POST /settings/trash/delete`。设置永久删除必须携带预览 fingerprint；设备及导入任务的历史快照保留；项目内拥有的素材仍会阻止删除项目。旧 `/capture-profiles` 接口、项目 `capture_profile_ids`、版本 `capture_profile_id` 和旧能力字段已移除，不提供兼容别名。CLI 命令和 58 个 MCP 工具集合不变。
