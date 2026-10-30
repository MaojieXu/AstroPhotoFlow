# 接口从哪里查

接口字段、类型、必填项、路径和状态码由实际路由及Pydantic模型生成，不再手写全量接口表。业务限制见 [产品需求](../requirements/README.md)；未实现能力只在当前任务写必要交接，不提前定全量签名。

## HTTP：自动生成

- 当前契约：[openapi.json](openapi.json)。事实源是 [HTTP装配](../../src/astrophotoflow/interfaces/http/app.py)、模块`routes.py`及 [contracts](../../src/astrophotoflow/contracts)。
- 生成脚本：[export_openapi.py](../../scripts/export_openapi.py)，在临时目录创建应用并导出，不启动服务器或使用真实业务库。

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$PWD/.artifacts/venvs/dev"
pnpm docs:api
```

等价命令：`uv run --locked --no-sync python scripts/export_openapi.py`。生成物提交随接口改动更新，不手工编辑JSON。

服务提供`/openapi.json`；当前应用显式关闭Swagger `/docs`和ReDoc `/redoc`页面。无需为文档开放新的服务入口。

现有 [一致性测试](../../tests/modules/data/test_service.py) 中的`test_openapi_snapshot_matches_service_and_proxy_allowlist`比较实际schema、快照和代理白名单；[CI](../../.github/workflows/build-pipeline.yml)的Python产品测试已执行它。按需单独检查：

```powershell
uv run --locked --no-sync pytest tests/modules/data/test_service.py -k openapi_snapshot_matches_service_and_proxy_allowlist -q
```

接口修改同时维护处理逻辑、模型、代理白名单和实际消费者。OpenAPI不能证明前端Zod、内部WebSocket消息或业务语义自动同步；这些由对应代码和行为测试覆盖，不再复制一份手工schema。

## 其他接口按需查询

| 想查什么 | 事实源 |
|---|---|
| Python跨模块调用 | 各模块`public.py`和`contracts`，从 [源码导航](../architecture/module-map.md) 进入 |
| CLI | `apf --help`、`apf <分组> --help`，不在文档复制完整命令树 |
| MCP | 服务`tools/list`返回的实际注册和输入schema；[现有用法与Skill](../development/library-agent-tools.md)补充业务流程 |
| 节点参数／就绪 | 平台`list_nodes/get_node`或对应HTTP目录，完整定义按需读取 |
| 原生页面消息 | `interfaces`及宿主桥接的实际类型；此协议不属于OpenAPI |

网页经`/astrophotoflow/api/v1`同源代理，CLI／MCP访问领域服务`/api/v1`；保留workspace认证和来源检查。内部维护、原生调用及页面确认不因此公开为任意执行接口。
