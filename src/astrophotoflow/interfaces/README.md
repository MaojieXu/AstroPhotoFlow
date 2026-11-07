# interfaces 接入与装配

`interfaces` 把服务能力暴露为 HTTP、CLI、类型化客户端、MCP 工具与原生宿主协议，并承载跨模块用例编排；适配层不复制业务权威。

## 入口

- `http/app.py` 的 `create_app(settings, token)` 装配 FastAPI、中间件、错误处理与各模块公开路由；`http/cli.py` 提供 `apf-service`（`serve`、`db status`、`db upgrade`、`previews backfill`）。
- `cli/main.py` 是 `apf` 命令（cyclopts），业务命令按模块注册；`client/` 提供 `AssetClient` 类型化 HTTP 客户端，`client/errors.py` 的 `ServiceApiError` 是稳定错误类型。
- `mcp/server.py` 运行 FastMCP 服务，按 data、graph、software 分组挂载工具；工具清单以运行时输出为准。
- `native/` 是原生宿主协议适配（节点注册、页面消息、Bundle 加载观察），不承担工作流或调度权威。
- `application/` 放跨模块用例：`canvas.py` 组合 data、native 与 nodes，`package_actions.py` 协调已确认的包维护与原生节点刷新，`software_calls.py` 与 `software_previews.py` 组合调用与预览。

## 边界

HTTP、CLI、MCP 与原生通道不读写 SQLite、不导入模块私有 ORM；装配只调模块公开入口；错误回执保留真实状态码与错误码，不吞异常。

## 测试

`tests/interfaces/` 覆盖 HTTP、MCP、native 与 client；`tests/integration/` 覆盖跨进程与协议行为。模块职责见[架构](../../../docs/architecture.md)。
