# 接口与契约

HTTP 服务前缀为 `/api/v1`；浏览器经 ComfyUI 的 `/astrophotoflow/api/v1` 同源代理访问。认证、版本冲突、错误 envelope 和请求 ID 延续当前实现。

[openapi.json](openapi.json) 是实际应用生成的契约快照。修改接口时同时核对处理逻辑、Pydantic 模型、代理白名单、前端 Zod 和相关测试；不能用路由数量相等代替行为一致。

```powershell
uv run --locked --no-sync python scripts/export_openapi.py
uv run --locked --no-sync pytest tests/backend/test_service.py -k openapi
```

CLI 保留 `apf init/start/status/stop`、`mcp-config`、`mcp`、`import-photo`、`task`、`assets list/get/parameters`。服务 CLI 保留 `apf-service serve`、`db status/upgrade` 和 `previews backfill`。

MCP 通过 `apf mcp` 提供 stdio 服务，现有五个名称保持兼容：`import_photo`、`get_import_task`、`list_assets`、`get_asset`、`update_asset_parameters`。结构化 HTTP 客户端、CLI 和 58 个 MCP 工具覆盖批量上传、配置根目录导入、任务、资产及逻辑组、项目固定版本引用、设备、使用组合／所属预设、校准关联、按需预览和回收站。

完整命令／工具清单、实际请求模型、配置与例子见[素材库 Agent 工具](../development/library-agent-tools.md)。项目内 [AstroPhotoFlow library Skill](../../.agents/skills/astrophotoflow-library/SKILL.md) 提供可复用工作流，无需全局安装。旧单图导入已去除 Light/subframe 强制分类，省略分类使用后端自动规则。

未提供的 PATCH 字段保持原值，null 清空，0 是有效值；revision 冲突和错误 request ID 明确传回。数据集发布同时接受固定校准版本、组默认和成员覆盖；永久清理仍必须提交当前回收站预览 fingerprint 并遵循引用保护。配置记录删除采用归档。配置方式见[工作台使用](../development/workbench.md)。
