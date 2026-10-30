# 接入层

- `http/app.py`装配FastAPI、中间件与模块公开路由；`http/cli.py`提供服务命令。
- `cli`、`client`、`mcp`分别提供命令、具名HTTP调用和协议适配，实际清单由help／tools/list返回。
- 原生节点注册、受控页面消息及软件计划确认薄适配也位于本层，不复制所属模块业务权威。

HTTP装配通过公开入口组合模块；CLI、客户端、MCP经共享服务，不直接读写SQLite／ORM。根`client.py`和`cli.py`保留公开入口。

类型查 [contracts](../contracts)，HTTP查 [生成契约](../../../docs/api/README.md)，进度查 [当前上下文](../../../docs/development/current-context.md)。测试在`tests/interfaces`／`tests/integration`，是否执行遵循用户本次要求。
