# 接口与契约

HTTP 服务前缀为 `/api/v1`；浏览器经原生网页服务的 `/astrophotoflow/api/v1` 同源代理访问。认证、版本冲突、错误 envelope 和请求 ID 延续当前实现。

[openapi.json](openapi.json) 是实际应用生成的契约快照。修改接口时同时核对处理逻辑、Pydantic 模型、代理白名单、前端 Zod 和相关测试；不能用路由数量相等代替行为一致。

```powershell
uv run --locked --no-sync python scripts/export_openapi.py
uv run --locked --no-sync pytest tests/modules/data/test_service.py -k openapi
```

CLI 保留 `apf init/start/status/stop`、`mcp-config`、`mcp`、`import-photo`、`task`、`assets list/get/parameters`。服务 CLI 保留 `apf-service serve`、`db status/upgrade` 和 `previews backfill`。

单图自动显示拉伸：前端打开大图时调用 `/api/v1/library/assets/{asset_id}/versions/{version_id}/previews/display/auto-stretch`（POST，无用户参数），后台单独分析当前照片；RGB自动估计白平衡，并计算MTF曲线，同时更新该版本的大图和缩略图。已有结果直接返回200，已有生成任务复用并返回202，前端沿用状态轮询；不强制重新计算。`/display/status` 及已有生成接口返回 `stretch`：未执行或生成中为null，成功后为 `algorithm/input_offset/white_balance/shadows/highlights/midtones` 计算结果。前端等待旧基准大图任务时，会在该任务完成后补齐自动配方，再显示最终图像。项目固定引用在 `/projects/{project_id}/asset-references/{reference_id}/previews` 下具有同名POST接口，作用于引用版本。MCP工具集合、CLI命令及科学素材参数不变。

MCP 通过 `apf mcp` 提供 stdio 服务，现有五个名称保持兼容：`import_photo`、`get_import_task`、`list_assets`、`get_asset`、`update_asset_parameters`。结构化 HTTP 客户端、CLI 和 58 个 MCP 工具覆盖批量上传、配置根目录导入、任务、资产及逻辑组、项目固定版本引用、设备、使用组合／所属预设、校准关联、按需预览和回收站。

完整命令／工具清单、实际请求模型、配置与例子见[素材库 Agent 工具](../development/library-agent-tools.md)。项目内 [AstroPhotoFlow library Skill](../../.agents/skills/astrophotoflow-library/SKILL.md) 提供可复用工作流，无需全局安装。旧单图导入已去除 Light/subframe 强制分类，省略分类使用后端自动规则。

未提供的 PATCH 字段保持原值，null 清空，0 是有效值；revision 冲突和错误 request ID 明确传回。数据集发布同时接受固定校准版本、组默认和成员覆盖；永久清理仍必须提交当前回收站预览 fingerprint 并遵循引用保护。配置记录先移入回收站，再预览并确认永久删除。配置方式见[工作台使用](../development/workbench.md)。

设置回收站接口为 `GET /api/v1/settings/trash`、`POST /settings/trash/archive`、`POST /settings/trash/restore`、`POST /settings/trash/delete-preview` 和 `POST /settings/trash/delete`。设置永久删除必须携带预览 fingerprint；设备及导入任务的历史快照保留；项目内拥有的素材仍会阻止删除项目。旧 `/capture-profiles` 接口、项目 `capture_profile_ids`、版本 `capture_profile_id` 和旧能力字段已移除，不提供兼容别名。CLI 命令和 58 个 MCP 工具集合不变。
