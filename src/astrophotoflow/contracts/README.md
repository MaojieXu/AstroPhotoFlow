# 公共接口契约

common、assets、imports、datasets、projects、equipment、setups、calibration、trash、previews 保存已有 Pydantic 模型和纯校验器；`software.py` 保存③首包、操作、安装请求及含逐命令评估的官方命令目录契约，`nodes.py` 保存④定义、绑定、差异和写入结果契约，`workflows.py` 当前保存B32软件计划／网页事件组合DTO。模型名、字段、默认值与序列化语义保持。

这里只依赖标准库和 Pydantic。服务端、客户端、CLI、MCP 共用这些定义，旧 backend schema 导入路径已退役，不维护转发文件。

接口事实源是这些定义与实际 HTTP 路由；OpenAPI 是生成快照，前端 Zod 是消费校验模型。未来节点、工作流和运行协议尚未在此实现。

验证：架构边界测试、OpenAPI 和 MCP 契约比对、`uv run --locked --no-sync pytest tests/integration -q`。
