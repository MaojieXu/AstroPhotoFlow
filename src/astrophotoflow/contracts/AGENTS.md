# 契约边界

- 只依赖标准库、Pydantic 和本契约包的明确模型，不导入 core、modules、interfaces、ORM 或 HTTP 框架。
- 修改以真实接口需求为依据，保留未提供、null、0 和 revision 语义；不能随目录调整改变字段。
- 避免循环引用，按语义所在文件修改，不在旧路径添加兼容导出。
- 变更时核对服务端、Python 客户端、CLI/MCP、前端 Zod 与生成 OpenAPI。
