# 接口与契约

本文和 OpenAPI 描述已实现接口；[五模块接口契约与文件级详细设计](platform-contracts.md)维护未来操作、精确类型与签名、文件职责、调用流和测试条件。产品目标与后续 MCP 范围见[现行需求](../requirements/README.md)。拟新增文件与接口不代表已实现或注册。

数据引用、节点定义、当前工作流保存及运行结果的责任和语义统一见[总架构的四类边界](../architecture/overview.md#5-四类跨模块契约)。具体输入输出、失败含义及未来 HTTP／MCP 设计集中在[契约文档](platform-contracts.md)，不向 OpenAPI 添加占位。

M1新增 `GET/PATCH /api/v1/settings/workbench`：读取固定当前workspace的保存／采用值，PATCH携带config_token，冲突409、显式null默认位置或无效字段422；保存不重启。网页重启扩展后共82项公共HTTP操作。M2新增素材内容观察与确认两个HTTP操作，加上工作台目录选择后当前共85项；对应代理、Python客户端、前端确认交互及OpenAPI快照已同步。内部maintenance和shutdown不进入公共OpenAPI或MCP。

工作台目录选择：认证后的 `POST /api/v1/settings/workbench/select-directory` 接收 `{path: string}`，Windows本机选择窗口返回完整路径或取消时的null；失败503。选择只填表、不保存或迁移数据。配置响应的`data_dir_absolute`表示已保存数据目录的绝对路径；默认工作区只决定以后默认启动位置，当前工作区与数据库不搬迁。工作台配置从原生设置的“工作台”页进入，说明和完整路径通过提示查看。

网页重启新增 `POST /api/v1/settings/workbench/restart`（请求为 `{operation_id: UUID字符串}`，202受理）及 `GET /api/v1/settings/workbench/restart/{operation_id}`（当前网页请求回执，尚未登记为null）。前端先持有编号；POST断连只查询，不重发。控制互斥409、启动控制器失败503；子进程执行原有restart，繁忙／未知／实际完成分别回执。少量最新受理结果保存在workspace的`run/web-restart.json`，不建立历史账本。内部维护与shutdown仍不公开；现有MCP保持。
HTTP 服务前缀为 `/api/v1`；浏览器经原生网页服务的 `/astrophotoflow/api/v1` 同源代理访问。认证、版本冲突、错误 envelope 和请求 ID 延续当前实现。

[openapi.json](openapi.json) 是实际应用生成的契约快照。修改接口时同时核对处理逻辑、Pydantic 模型、代理白名单、前端 Zod 和相关测试；不能用路由数量相等代替行为一致。

```powershell
uv run --locked --no-sync python scripts/export_openapi.py
uv run --locked --no-sync pytest tests/modules/data/test_service.py -k openapi
```

CLI 提供 `apf init/start/status/stop/restart`、`mcp-config`、`mcp`、`import-photo`、`task`、`assets list/get/parameters`。服务 CLI 保留 `apf-service serve`、`db status/upgrade` 和 `previews backfill`。

单图自动显示拉伸：前端打开大图时调用 `/api/v1/library/assets/{asset_id}/versions/{version_id}/previews/display/auto-stretch`（POST，无用户参数），后台单独分析当前照片；RGB自动估计白平衡，并计算MTF曲线，同时更新该版本的大图和缩略图。已有结果直接返回200，已有生成任务复用并返回202，前端沿用状态轮询；不强制重新计算。`/display/status` 及已有生成接口返回 `stretch`：未执行或生成中为null，成功后为 `algorithm/input_offset/white_balance/shadows/highlights/midtones` 计算结果。前端等待旧基准大图任务时，会在该任务完成后补齐自动配方，再显示最终图像。项目固定引用在 `/projects/{project_id}/asset-references/{reference_id}/previews` 下具有同名POST接口，作用于引用版本。MCP工具集合、CLI命令及科学素材参数不变。

MCP 通过 `apf mcp` 提供 stdio 服务，现有五个名称保持兼容：`import_photo`、`get_import_task`、`list_assets`、`get_asset`、`update_asset_parameters`。结构化 HTTP 客户端、CLI 和 58 个 MCP 工具覆盖批量上传、配置根目录导入、任务、资产及逻辑组、项目固定版本引用、设备、使用组合／所属预设、校准关联、按需预览和回收站。

完整命令／工具清单、实际请求模型、配置与例子见[素材库 Agent 工具](../development/library-agent-tools.md)。项目内 [AstroPhotoFlow library Skill](../../.agents/skills/astrophotoflow-library/SKILL.md) 提供可复用工作流，无需全局安装。旧单图导入已去除 Light/subframe 强制分类，省略分类使用后端自动规则。

[③软件概要](../../src/astrophotoflow/modules/software/README.md)规定未来软件包／配套节点的安装更新和就绪，[④节点概要](../../src/astrophotoflow/modules/nodes/README.md#handoffs)规定可编辑定义、可选测试及确认更新。上述新增能力仍待实现，具体接口不预建占位。

[⑤概要](../../src/astrophotoflow/modules/workflows/README.md#handoffs)统一项目当前图、原生执行、运行记录、自动图像预览及Agent交互。当前图复用原生JSON文件，不另建可编辑副本；重要方案另存，会话撤销和本地草稿复用，不设计永久逐编辑修订、服务端草稿、转换实体或永久回执。首版Agent改图／新提交限明确活动网页，切走暂停，已有运行继续且预览归原图。当前目标／内容／控制须在实际写入和新受理处核对，原生userdata写入尚不提供这些规则。

调用、保存、实际显示、执行和所选完整结果保存分别返回真实情况；未知先查询，request ID和prompt_id不自动提供防重，取消受理不证明软件停止。预检、输入准备、任务关联、取消和素材保存情况合入同次运行，不预设独立资源类型。数据见[⑤设计](../architecture/data-models/05-workflows.md)，未来操作及字段见[⑤契约](platform-contracts.md#workflows)：局部改图为主，整图只用于导入或明确替换；目标网页点击“交给Agent”绑定，保存当前画布成功后运行。新增桥接仍待实现／验证。

⑤统一目录和[按需检索](../requirements/README.md#tool-discovery)沿用Skill直达、混合Top10及显式关键词降级。未来精简MCP整体替换58工具，不留旧入口／别名／双轨，数据业务仍共用HTTP／CLI，实施时同步Skill／参考／配置和真实客户端测试。本轮现有工具、五个兼容名称、注册及Skill保持，Judge不增加评分API或实际端口。

未提供的 PATCH 字段保持原值，null 清空，0 是有效值；revision 冲突和错误 request ID 明确传回。数据集发布同时接受固定校准版本、组默认和成员覆盖；永久清理仍必须提交当前回收站预览 fingerprint 并遵循引用保护。配置记录先移入回收站，再预览并确认永久删除。配置方式见[工作台使用](../development/workbench.md)。

设置回收站接口为 `GET /api/v1/settings/trash`、`POST /settings/trash/archive`、`POST /settings/trash/restore`、`POST /settings/trash/delete-preview` 和 `POST /settings/trash/delete`。设置永久删除必须携带预览 fingerprint；设备及导入任务的历史快照保留；项目内拥有的素材仍会阻止删除项目。旧 `/capture-profiles` 接口、项目 `capture_profile_ids`、版本 `capture_profile_id` 和旧能力字段已移除，不提供兼容别名。CLI 命令和 58 个 MCP 工具集合不变。
