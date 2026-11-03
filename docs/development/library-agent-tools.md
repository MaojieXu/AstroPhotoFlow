# Agent 数据与画布操作指南

字段和有效值由共享Pydantic契约与FastMCP函数定义。[生成目录](../api/mcp-tools.json)、tools/list、search_tools及apf call-tool TOOL --help是入口；不手抄全量schema。[项目Skill](../../.agents/skills/astrophotoflow-library/SKILL.md)提供任务路由与基本约束。

## 发现与工作区

工具按data／software／graph多层组合，运行在一个MCP进程。Agent列表为框架search_tools与call_tool；已知完整工具名可直接调用，陌生能力先以query检索，最多得到10项完整定义。BM25是词项检索，不是模型语义检索。graph_nodes_search检索节点目录，不与MCP工具检索混淆；不将Siril每个节点复制为一个工具。

业务CLI从完整目录自动生成。本机runtime、workspace、init、启停和状态使用Cyclopts；不另维护业务参数表。

```powershell
$env:ASTROPHOTOFLOW_CONFIG = 'C:/chosen-workspace/config.toml'
apf call-tool data_library_search --query '{"q":"M31","limit":50}'
apf call-tool data_assets_get --asset-id RETURNED_ASSET_ID
apf call-tool data_assets_update --asset-id RETURNED_ASSET_ID --expected-revision 3 --changes '{"parameters":{"gain":0,"exposure_seconds":null}}'
```

复杂对象用JSON。stdio子进程显式接收选定配置；此流程不注册全局MCP或修改默认workspace。重连后使用实际当前工具schema，不调用旧双网关、discover／describe或旧手工命令树。

## 图像导入、跨夜追加与校准

先用data_imports_inspect只读观察目录，记录scan_id；按需用data_imports_entries读取files／excluded／issues。结果是文件事实，不是后端分组建议。Agent根据参数、设备、目标和用户意图决定分组，展示数量、范围、未知项与冲突后确认。不能把文件名线索写成已观察到的科学资料。

导入前先汇总拟议分组、设备、校准及影响本次操作的疑问，由Agent向用户确认。同类疑问按明确文件范围合并。模型知识或可靠网络资料只能形成建议，用户确认后才能采用；设备能力不能证明实际曝光、gain、offset、温度或Master制作历史。用户可以明确保留未知或暂不绑定；仅指定Master不等于接受全部未知，不把accept_unknown默认设为true。来源、范围或选择发生变化时重新说明差异。平台不建立聊天或强制三阶段确认系统。

导入采用轻量登记：逐文件读取头与结构事实，来源未变时复用扫描资料，保留托管复制及哈希。新组仅生成封面，其他成员在查看时按需生成预览；导入完成不等待全体缩略图，不执行质量分析或实际校准。

明确文件名单使用扫描返回的file_id，顺序就是导入顺序。data_imports_import_asset导入独立单图；data_imports_import_dataset新建一个明确的组；data_imports_append_dataset向准确dataset_id及基础revision／version追加。每次预先记录request_id。同名组、同object和同文件hash都不表示可以自动合并。校准Master尚未入库时，先导入已制作完成的Master取得固定素材版本，再导入亮场并绑定。原始校准组仍可入库管理，但不能作为绑定目标。暂缺校准可未配置入库。

新组的calibration_defaults是组默认；追加的incoming_calibration只作用于本批新增成员。追加省略的槽位为unconfigured，不会自动继承旧夜flat；只有明确inherit才继承。文件自身的calibration可覆盖本批共同值。组成员及绑定在同一次版本发布中保存，旧成员关系不变。

未知受理查询data_tasks_status原request_id，不换ID重发。data_tasks_wait遵守next_poll_seconds；data_tasks_get按需分页读取文件结果。登记、原件、解析、发布、校准检查、预览分别报告。部分失败只发布满足条件的成功成员，预览失败不代表科学原件失败。来源变化重新观察；发布revision冲突先协调，再data_imports_retry_publication只补发布，不重新导入。恢复／重试保留原素材身份和受理快照。

data_assets_search按目标、用途、设备、参数和图片时间查找；data_assets_read_header读取准确版本文件头。图片拍摄时间、Master制作时间和入库时间不能替代。未知时标不按主机时区推定。设备应用使用data_assets_apply_equipment，只应用明确fields；直接选择设备或可选组合，不提供独立拍摄预设。曝光、gain、offset和实测温度属于图像资料，关联设备不能覆盖。换望远镜会清除不属于新望远镜的旧附件；不隐式选取新附件。

data_calibration_search只推荐对应Master候选，data_calibration_check检查明确消费对象和提议。未知不等于匹配；accept_unknown只允许保存已确认的未知项，不能绕过已知冲突。校准目标仅接受对应用途的masterframe固定素材版本，拒绝原始组及subframe；所有槽位均可不配置。保存关系不会制作Master或执行校准。

单图配置用get_image／update_image；组默认用update_defaults，成员用update_members。inherit恢复组默认、unconfigured阻断继承、disabled明确不用、target固定目标。成员选择统一使用asset_version_id，不使用每版重建的DatasetMember.id。update_defaults会影响继承该槽位的成员，局部变化应使用update_members。组不动态继承单图最新配置。同一目标组可以跨夜、跨曝光、跨设备保留成员，各成员采用自己的校准。

Master人工来源通过data_assets_get_master_provenance／update_master_provenance管理，与平台实际输出来源分开；计划绑定不能当成实际已应用校准。固定来源和旧声明可追溯，外部Master来源未知仍保留未知。

## 固定版本与资料编辑

省略、null、0按契约区分。先读当前revision，再提交用户意图；冲突后协调，不重试旧写入。元数据纠正不改原科学文件、旧版本快照或已有运行事实。

集合发布固定成员范围和顺序，data_datasets_members分页读准确版本。data_datasets_edit_members只增减明确成员，保留其余顺序及绑定，不删除素材原件。项目引用固定素材／集合版本，不关联工作流文件。

## 通过聊天登记设备

目标是把用户明确拥有、要求登记的器材可靠地加入数据库。聊天由外部Agent负责，平台不新增聊天服务、模型会话、硬件驱动或自动型号数据库。用户不需要知道工具名、UUID、成员ID或revision；Agent从当前工具定义与真实回执取得这些信息。

设备相关工具按任务组织，共16项：

| 任务 | 工具 |
|---|---|
| 查找、读取已登记设备 | `data_equipment_search`、`data_equipment_get` |
| 按种类登记设备 | `data_equipment_register_camera`、`data_equipment_register_telescope`、`data_equipment_register_filter`、`data_equipment_register_mount` |
| 按种类补充或修改设备 | `data_equipment_update_camera`、`data_equipment_update_telescope`、`data_equipment_update_filter`、`data_equipment_update_mount` |
| 查找、读取、创建、更新组合 | `data_setups_search`、`data_setups_get`、`data_setups_create`、`data_setups_update` |
| 设备、组合的共同删除流程 | `data_equipment_management_preview_delete`、`data_equipment_management_delete` |

准确字段、类型、必填项、有效值和结果结构以[生成目录](../api/mcp-tools.json)及实际工具schema为准。四种登记工具已确定设备种类，不需要再传`kind`或`body`；可选`specs`只接受该种类的规格。望远镜附件属于其内部规格，不是独立设备类别。

### 最少追问，按真实事实登记

先从用户话语拆出每件设备、数量、原始称呼和明确给出的参数。登记只要求名称，类别由所选工具确定；型号、像元、焦距、像素排列、滤镜Channel和带宽等可先保持未知。名称可以是用户自己的称呼，不要求提供精确商品型号。只在缺少可识别称呼、类别或数量有真实歧义时追问，不先让用户填写完整规格表。

用户说“把我的相机登记进去，名字叫聊天验证相机，规格以后补”，查重且没有歧义后可直接调用：

```json
{
  "name": "data_equipment_register_camera",
  "arguments": {"name": "聊天验证相机"}
}
```

这是`call_tool`的输入示例，不是在接收用户话语的另一个注册服务。用户已经明确要求登记且资料充分时直接执行，不重复要求确认保存。没有明确授权的器材清单或讨论，不自行解释为写入请求。

型号或名称不是精确科学规格的依据；不凭型号补猜像元、原生焦距、波长或像素排列，不把未知写成0。滤镜Channel是成像通道／通带自由文本；用户明确标签优先，Agent可依据明确用途、FITS FILTER或可靠产品资料填写。Lum→L、Red/Green/Blue→R/G/B、Ha/OIII/SII→H/O/S；三片SHO分别S/H/O，单片多通带SHO保留一件设备及SHO标签。明确的RGB或红外875nm通道可填RGB或Ir875nm；彩色相机不证明存在RGB滤镜，不从通道标签补造中心波长或带宽，未知省略。不批量规范旧值大小写。数值及单位先明确再写入；非法值应清晰失败，不自行改成“合理值”。

登记前用`data_equipment_search`查询相关类别和名称／型号候选，必要时包含归档记录。相同名称不证明是同一件实物，也不是数据库冲突；疑似重复时只问“补充已有这台，还是新增第二台？”。用户明确新增第二台时保留独立身份，允许重名；不自动合并、覆盖、恢复归档或强迫改名。

一次说多件时分别调用合适的登记工具并跟踪结果。明确数量的同型号设备逐件保存，不按型号或Channel合并。完成后按实际回执汇报成功设备、数量与已保存事实；未知规格直接说明可后补，不把“已发起调用”说成“已入库”。

### 补充资料与可选设备组合

用户要求补充已有资料时，先确认准确设备，调用对应`get`取得当前revision，再使用相应类型的更新工具，并将真实revision传给`expected_revision`。省略保持、可空字段null清空、0保留；冲突后重新观察并说明差异，不自动套用新revision重放旧写入。用户不需要手抄这些内部身份与并发参数。

赤道仪使用register_mount/update_mount，仅维护名称、型号、备注及状态，无specs或硬件控制字段。组合允许至多一台赤道仪（注册和内联合计），图像显式应用fields:["mount"]冻结其身份和资料，不改变拍摄参数，也不用于校准匹配。

只说“登记我的设备”时，不自动创建组合。用户明确说“把这些组成一套”才创建组合；上下文不明确时，只追问缺少的组合名称和成员身份。组合支持已登记引用`registered`和组合内设备`inline`；后者不会自动登记进设备库。读取真实组合的`components`及成员`id`，更新时将已有成员身份带入`members`中的`member_id`，保留未变成员身份及顺序；不用列表位置代替成员ID，也不把设备ID当成成员ID。

图像可直接选择已登记设备，也可通过组合快捷选择。组合包含多片滤镜时明确选择实际滤镜。每次应用只修改指定设备字段，冻结当时的设备资料；拍摄参数从文件读取或由用户确认后补充，不能按组合推算。批量补缺失与纠正已有值须明确区分，原始观察值保留。

### 部分成功、未知结果与删除

设备登记不是跨多件的原子事务。逐项报告“已成功且有ID”“明确失败”“待澄清”“结果未知”；某件失败不撤销或重放已成功条目，也不冒称整批全部完成。收到明确校验失败时只修正对应输入；写入回执未知时先查询核对，不能直接重复创建。若仍无法确认，保留未知并说明，不能仅凭同名候选断定本次已成功。

设备、组合删除统一走`data_equipment_management_preview_delete`与`data_equipment_management_delete`。先读取准确对象和revision、查看实际关联影响，再在用户已授权范围内使用同一选择及当前指纹执行；不要要求用户填写内部ID。预检指纹证明影响未变，不代替用户授权；指纹或revision变化时停止并说明。设备修改或删除不回写历史快照，不删除素材原件。

## ComfyUI原生画布和具体调用

ComfyUI拥有工作流文件、草稿、保存、撤销、转换、队列、执行历史、进度和取消入口。平台不建设另一套工作流生命周期、完整运行库、完整图副本或保存工程准入。

先读graph_nodes_search/get/get_many的真实定义、端口、参数范围及令牌，再用graph_canvas_pages/get观察用户指定画布。edit/add_data必须携带准确页面、工作流、子图和当前content_token。切图或内容变化停止；未知修改查graph_receipts_get原operation_id，不重发或跟随其他图。修改不会执行整图。

software_calls查询具体原生prompt/call的版本、参数、日志、过程观察及输出。进程退出、输出检查与结果登记分别表达。取消受理不等于已停止；无法核实时保持未知，不自动重跑，也不扫描其他模块私有文件猜测结果。

## 结果查看与显式保存

data_results_get读取实际Data执行。Data可以接固定APF_SCIENCE或原生IMAGE；连接输入优先，冲突明确失败。原生IMAGE固定为完整FITS成员，float16提升float32，float32／64保留；不自动登记到素材库。只有Data承担原生输出／预览行为，File保持原契约。

用户选定完整成员和目标后调用data_exports_submit。先记录request_id，未知导出查询原回执，不重跑上游。默认复制完整容器；显式格式／精度按当前schema选择，只影响副本。整数转换不隐式归一化、裁剪或开发RAW；非有限／越界／分数值、归一化范围和显示配方需明确决定。多HDU／视频需选准成员；复杂XISF、TIFF、RAW保留原容器或先做明确上游选择。预览JPEG不是科学输入。

## 显示预览与清理

data_media_schedule/status/read管理显示预览，read返回MCP图片。仅generating或已知活跃工作继续等待；failed／unsupported是终态观察，不借旧缓存假报科学就绪。data_media_export独占创建用户指定新JPEG，不覆盖已有路径。software_previews_render使用固定版本、准确成员、参数、consumer／generation；完成后release consumer，不将样本可见等同完整结果可用。

移除、恢复、永久清理分别操作。永久清理先取得有限范围的当前预检和指纹，解释引用／依赖，获得明确授权，再提交同一选择及指纹。报告部分失败，保留失败项。设备／组合／预设直接删除同样先看影响，保留原文件和历史快照。文件系统与数据库不是统一事务，不伪称跨两者原子完成。

## 素材表与累计曝光

校准信息合并进现有素材表，MCP仍复用现有读取及绑定工具；不增加另一套管理工具。Light可选暗场／平场／Bias，Flat可选Bias／暗平场，Dark／Dark-flat可选Bias。恢复继承仅适用于成员，未配置不等于不用。组消费者和Master的固定来源仍可使用dataset_version，不要与被取消的组校准目标混淆。

组的exposure_summary由后端对全部指定成员求和：只统计subframe的exposure_seconds，不加integration_seconds或Master。返回已知／未知数量和完整性；无已知值为null，合法0保留。当前组资料纠正后采用新汇总，明确历史版本使用冻结事实。外部MCP写入后当前可见页按现有轻量轮询自动更新，不触发科学计算。
