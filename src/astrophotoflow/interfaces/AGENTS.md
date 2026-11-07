# 接入层约束

- 本层只做适配、装配与薄编排，不复制所属模块的业务规则；HTTP、CLI、MCP 与原生协议不读写 SQLite、不导入模块私有 ORM 或辅助函数。
- HTTP 装配只调用模块公开入口；跨模块用例放 `application/`，不放路由函数。
- 保留公开入口 `AssetClient`、`ServiceApiError`、`apf`、`apf-service`；错误回执保持真实错误类型与状态码，不吞异常改写成成功。
- 原生节点注册、页面消息与软件计划确认等宿主协议薄适配留在 `native/`，服务端不承担工作流或调度权威。
- MCP 通过 `APF_WORKSPACE` 环境变量选择 workspace，不改全局注册与默认指针；工具清单以运行时 `list tools` 输出为准。
- 测试位置 `tests/interfaces/`、`tests/integration/`。
