# 接入层边界

- 阅读 README、相关契约与实际服务端入口。
- CLI、客户端和 MCP 不读写 SQLite、不导入 ORM，不复制业务规则。
- HTTP 装配仅使用模块明确公开入口；不直接调用 data 私有辅助函数。
- 保持 AssetClient、ServiceApiError、apf、apf-service、现有 HTTP/MCP 契约与真实错误回执。
- MCP 通过环境选择 workspace，不修改全局注册或默认指针。
