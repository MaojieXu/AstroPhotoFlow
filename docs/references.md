# 接口参考

[English](references.en.md) | 中文

接口字段、类型、必填项与状态码以实际路由和 Pydantic 模型为准；文档不手抄 schema，统一指向生成物。

## 生成物

| 生成物 | 内容 | 生成入口 |
| --- | --- | --- |
| `docs/api/openapi.json` | HTTP 契约 | `scripts/export_openapi.py`（`pnpm docs:api`） |
| `src/astrophotoflow/vendor/http-routes.json` | 同源代理使用的公共路由清单 | 同上 |
| `docs/api/mcp-tools.json` | MCP 工具快照 | `scripts/generate_cli.py` |
| `src/astrophotoflow/interfaces/cli/generated.py` | 业务 CLI 命令 | 同上 |
| 前端 SDK | 由 OpenAPI 生成的 TypeScript 与 Zod 客户端 | `pnpm generate:sdk` |

## 查询入口

- HTTP：领域服务提供 `/openapi.json`；Swagger `/docs` 与 ReDoc `/redoc` 已关闭。
- 网页经 `/astrophotoflow/api/v1` 同源代理访问领域服务，CLI 与 MCP 直接访问 `/api/v1`。
- CLI：`apf --help` 查看命令，`apf call-tool TOOL --help` 查看单个工具的输入。
- MCP：服务 `tools/list` 返回注册工具与实际输入 schema。
- 原生页面消息：同一 OpenAPI 的 `x-apf-native-messages` 组件，来源是 `src/astrophotoflow/interfaces/http/schema.py`。
- Python 跨模块交接：看各模块的 `public.py` 与 `src/astrophotoflow/contracts`。

## 一致性

- 接口改动后重新生成并提交生成物，不手工编辑。
- 一致性测试 `tests/modules/data/test_service.py::test_openapi_snapshot_matches_service_and_proxy_allowlist` 比较实际 schema、快照与代理白名单，由 CI 执行。
