# Agent 数据与画布操作指南

字段和有效值由共享Pydantic契约与FastMCP函数定义。[生成目录](../api/mcp-tools.json)、tools/list、search_tools及apf call-tool TOOL --help是入口；不手抄全量schema。[项目Skill](../../.agents/skills/astrophotoflow-library/SKILL.md)提供任务路由与基本约束。

## 发现与工作区

工具按data／software／graph多层组合，运行在一个MCP进程。Agent列表为框架search_tools与call_tool；已知完整工具名可直接调用，陌生能力先以query检索，最多得到10项完整定义。BM25是词项检索，不是模型语义检索。graph_nodes_search检索节点目录，不与MCP工具检索混淆；不将Siril每个节点复制为一个工具。

业务CLI从完整目录自动生成。本机runtime、workspace、init、启停和状态使用Cyclopts；不另维护业务参数表。

```powershell
$env:ASTROPHOTOFLOW_CONFIG = 'C:/chosen-workspace/config.toml'
apf call-tool data_library_search --query '{"q":"M31","limit":50}'
apf call-tool data_assets_get --asset-id RETURNED_ASSET_ID
apf call-tool data_assets_update --asset-id RETURNED_ASSET_ID --body '{"base_revision":3,"parameters":{"gain":0,"exposure_seconds":null}}'
```

复杂对象用JSON。stdio子进程显式接收选定配置；此流程不注册全局MCP或修改默认workspace。重连后使用实际当前工具schema，不调用旧双网关、discover／describe或旧手工命令树。

## 整夜导入

先用data_imports_inspect只读观察目录，记录scan_id和分组ID。初始返回有限分组，按需用data_imports_entries读取groups／files／excluded／issues，不把全量文件头搬入上下文。以科学文件头事实为先，文件名／目录线索只形成建议。跨多夜目录需确认日期范围。

向用户展示分组、数量、未知、冲突和排除项，确认范围、排序、手工覆盖及可选项目后再受理。data_imports_submit一次提交，预先记录request_id。原组用group_id；明确拆分／排除／重排时才用ordered member_ids；成员不重复。options只放明确确认的覆盖，不自动写入猜测；只给预设ID可保留其默认优先级。项目关联需当前project_revision。

未知受理查data_tasks_status原request_id，不另造ID或自动重发。来源变化需重新检查和确认。data_tasks_wait聚合观察各组、阶段和项目关联，遵守next_poll_seconds。登记、原件、元数据、预览、关联分别报告；不把部分成功伪装为全部完成。成功成员明细按需读。

中断或失败按原因恢复／重试，SOURCE_CHANGED先复核来源。项目关联失败在协调项目revision后调用data_projects_retry_import_links，不重新导入。data_imports_local保留直接目录／配置根语义；upload_one/upload读取客户端本机文件。

## 固定版本、编辑和设备

省略、null、0按契约区分。先读当前revision，再提交用户意图；冲突后协调，不重试旧写入。元数据纠正不改原科学文件、旧版本快照或已有运行事实。

集合发布固定成员范围和顺序，data_datasets_members分页读准确版本。默认校准与成员覆盖区分继承、禁用、明确固定目标。项目引用固定素材／集合版本，不关联工作流文件。组合使用稳定成员ID，预设选择实际成员；不要猜测位置、把未知写成空串或把Gain／Offset0当缺失。删除前查看实际影响，保留既有快照。

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
