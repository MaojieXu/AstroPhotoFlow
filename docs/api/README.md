# 接口从哪里查

接口字段、类型、必填项、路径和状态码由实际路由及Pydantic模型生成，不再手写全量接口表。业务限制见 [产品需求](../requirements/README.md)；未实现能力只在当前任务写必要交接，不提前定全量签名。

## HTTP：自动生成

所有公开operationId显式固定，默认及422错误均使用同一个ErrorEnvelope。生成入口仅做等价JSON Schema规范化（有限键map和递归JsonValue），不手改TS／Zod生成物。

- 当前契约：[openapi.json](openapi.json)。事实源是 [HTTP装配](../../src/astrophotoflow/interfaces/http/app.py)、`interfaces/http`中的实际handler及 [contracts](../../src/astrophotoflow/contracts)。
- 生成脚本：[export_openapi.py](../../scripts/export_openapi.py)，在临时目录创建应用并导出，不启动服务器或使用真实业务库。
- 同一脚本生成[网页代理公共路由清单](../../src/astrophotoflow/vendor/http-routes.json)。原生代理只注册明确清单，不再手写另一份业务路径，也不开放通配转发或internal路径。

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$PWD/.artifacts/venvs/dev"
pnpm docs:api
```

等价命令：`uv run --locked --no-sync python scripts/export_openapi.py`。生成物提交随接口改动更新，不手工编辑JSON。

真实原生画布／页面消息也从Pydantic纳入同一OpenAPI的components，由`x-apf-native-messages`列出消息根，供同一生成入口导出TS／Zod；这不新增HTTP端点。来源见[原生契约装配](../../src/astrophotoflow/interfaces/http/schema.py)。

服务提供`/openapi.json`；当前应用显式关闭Swagger `/docs`和ReDoc `/redoc`页面。无需为文档开放新的服务入口。

现有 [一致性测试](../../tests/modules/data/test_service.py) 中的`test_openapi_snapshot_matches_service_and_proxy_allowlist`比较实际schema、快照和代理白名单；[CI](../../.github/workflows/build-pipeline.yml)的Python产品测试已执行它。按需单独检查：

```powershell
uv run --locked --no-sync pytest tests/modules/data/test_service.py -k openapi_snapshot_matches_service_and_proxy_allowlist -q
```

接口修改同步更新处理逻辑、模型、生成的代理清单和实际消费者。OpenAPI不能证明业务语义自动同步；实际行为由对应测试覆盖，不再复制一份手工schema。

## 其他接口按需查询

| 想查什么 | 事实源 |
|---|---|
| Python跨模块调用 | 各模块`public.py`和`contracts`，从 [源码导航](../architecture/module-map.md) 进入 |
| CLI | `apf --help`、`apf call-tool TOOL --help`，不在文档复制完整命令树 |
| MCP | 服务`tools/list`返回的实际注册和输入schema；[现有用法与Skill](../development/library-agent-tools.md)补充业务流程 |
| 节点参数／就绪 | `graph_nodes_search/get/get_many` 或对应HTTP目录，完整定义按需读取 |
| 原生页面消息 | `contracts/canvas.py`、`contracts/native.py`及同一OpenAPI的原生消息组件 |

网页经`/astrophotoflow/api/v1`同源代理，CLI／MCP访问领域服务`/api/v1`；保留workspace认证和来源检查。内部维护、原生调用及页面确认不因此公开为任意执行接口。


MCP／业务CLI由固定入口`python scripts/generate_cli.py`从完整离线目录生成，输出[工具快照](mcp-tools.json)和interfaces/cli/generated.py；不从仅含search_tools／call_tool的Agent视图生成，不手改生成物。

CLI固定生成入口为`scripts/generate_cli.py`：完整97工具按名称排序，经FastMCP官方生成器生成，使用锁定Ruff统一导入布局，再写入生成文件及`mcp-tools.json`。排序／格式化属于生成入口，不手改生成物；执行入口需要已准备的开发依赖。
