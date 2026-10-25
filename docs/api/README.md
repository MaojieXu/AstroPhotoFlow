# 接口与契约

HTTP 服务前缀为 `/api/v1`；浏览器经 ComfyUI 的 `/astrophotoflow/api/v1` 同源代理访问。认证、版本冲突、错误 envelope 和请求 ID 延续当前实现。

[openapi.json](openapi.json) 是实际应用生成的契约快照。修改接口时同时核对处理逻辑、Pydantic 模型、代理白名单、前端 Zod 和相关测试；不能用路由数量相等代替行为一致。

```powershell
uv run --locked --no-sync python scripts/export_openapi.py
uv run --locked --no-sync pytest tests/backend/test_service.py -k openapi
```

CLI 保留 `apf init/start/status/stop`、`mcp-config`、`mcp`、`import-photo`、`task`、`assets list/get/parameters`。服务 CLI 保留 `apf-service serve`、`db status/upgrade` 和 `previews backfill`。

MCP 通过 `apf mcp` 提供 stdio 服务，当前严格为以下五个工具：

| 工具 | 能力 |
|---|---|
| `import_photo` | 复制一张本地照片并创建导入任务 |
| `get_import_task` | 查询任务状态和结果 |
| `list_assets` | 分页查询共享资产 |
| `get_asset` | 读取单个共享资产和当前参数 |
| `update_asset_parameters` | 按当前 revision 修改或清空指定参数 |

未提供的 PATCH 字段保持原值，null 清空，0 是有效值；冲突明确失败。素材库 UI 的全部功能尚未映射为 MCP 工具，本轮不扩充工具集。配置方式见[工作台使用](../development/workbench.md)。
