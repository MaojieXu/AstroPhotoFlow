# 平台接入层

- http/app.py 装配 FastAPI、公共中间件与模块路由；http/cli.py 提供 apf-service，system.py 提供健康与真实能力信息。
- cli/ 保存 apf 参数与业务命令；根 cli.py 保留公开命令模块入口。
- client/ 保存具名 HTTP 领域操作；根 client.py 保留 AssetClient 和 ServiceApiError。
- mcp/server.py 与 mcp/tools/ 保存现有 58 个数据管理工具及协议适配。

接入层校验并转交请求，不直接操作业务 ORM。HTTP 应用装配通过 data.public 和 data.routes 使用模块；CLI、客户端和 MCP 通过共享 HTTP 服务操作数据。

验证：`uv run --locked --no-sync pytest tests/integration tests/interfaces -q`。
