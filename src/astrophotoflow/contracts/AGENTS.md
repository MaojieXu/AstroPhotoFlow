# 契约包约束

- 只依赖标准库与 Pydantic；不导入 `core`、`modules`、`interfaces`，不导入 ORM 或 HTTP 框架。
- 模型按语义域放在对应文件，新增字段先确认服务端、Python 客户端、CLI、MCP、前端 Zod 与 OpenAPI 快照的消费方，再同步重新生成快照与前端 SDK。
- 保留省略、`null`、`0`、revision 的语义区别；不因目录调整重命名字段，不为旧导入路径保留兼容导出。
- 不在这里写编排、IO 或持久化逻辑；跨边界行为在 `tests/integration/` 验证。
