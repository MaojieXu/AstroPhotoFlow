# 后端联调与验证

路径以本文件为基准，命令在仓库根执行。环境版本和工作台操作以[开发文档](../../../../docs/development.md)为准。

## 契约与生成物

| 改动 | 核对与生成入口 |
| --- | --- |
| HTTP 路由、模型或原生消息 schema | `pnpm docs:api` 导出 OpenAPI 与代理路由清单；原生消息定义从 [http/schema.py](../../../../src/astrophotoflow/interfaces/http/schema.py)进入 |
| MCP 工具名称、参数或返回类型 | 修改工具定义与组合后运行 `uv run --locked --no-sync python scripts/generate_cli.py`，同步 MCP 工具快照与生成业务 CLI |
| 前端消费的 HTTP 契约 | `pnpm generate:sdk` 重新导出 OpenAPI 并生成 TypeScript／Zod 客户端；同时核对实际前端调用者 |
| ORM 与数据库初始化基线 | 按[数据库开发入口](backend-map.md#数据库开发)更新并验证 |

生成物位置与查询方式见[接口参考](../../../../docs/references.md)。按实际消费链选择生成任务。生成 CLI 使用未连接 workspace 的完整工具目录，实际 Agent 工具视图还经过搜索变换，可从 [mcp/server.py](../../../../src/astrophotoflow/interfaces/mcp/server.py)的 build_tool_catalog 与 create_server 核对。

字段变更追踪服务端模型、Python 客户端、MCP 工具、生成 CLI 与前端消费方。检查参数传递时保留原有省略、`null`、`0` 与 revision 语义，重点核对客户端 JSON 序列化和生成器的参数过滤。生成完成后审查 diff，并验证受影响的普通调用入口。

## workspace 与运行目标

1. 使用显式选择的测试 workspace，核对 config.toml、实际进程与目标服务。CLI／外部 MCP 用 `ASTROPHOTOFLOW_CONFIG` 指向该文件，受管领域服务与原生桥接用 `APF_WORKSPACE` 指定 workspace 目录。配置入口见[接入层约定](../../../../src/astrophotoflow/interfaces/AGENTS.md)。
2. 用 `uv run --locked --no-sync apf status --workspace <workspace>` 核对运行状态与返回地址。实际端口、页面地址和配置关系见[开发调试说明](../../../../docs/development.md#调试)，沿现有客户端与 core 地址解析访问对应服务。
3. 运行浏览器或 MCP 验证前准备仓库内隔离测试 workspace。MCP 热加载使用 `pnpm dev:mcp --workspace .artifacts/workspaces/<test> --port 8765`，脚本检查隔离目标，并输出 HTTP MCP 地址。使用输出地址连接开发客户端。脚本入口见 [dev_mcp.py](../../../../scripts/dev_mcp.py)。
4. 根据被修改的进程验证加载结果。MCP 热加载后重新连接并查询工具，领域服务 Python 变化需显式重启目标服务，原生宿主变化按其加载生命周期重新加载。启停与重启通过 core 的公开控制入口，遵循[基础设施约定](../../../../src/astrophotoflow/core/AGENTS.md)。

测试 workspace 的数据替换依据[数据库开发约定](../../../../docs/development.md#目录)。共享 runtime、默认 workspace、全局 MCP 与外部原件的操作边界见[根约定](../../../../AGENTS.md#运行与素材保护)。

## 验证与回执

| 影响范围 | 优先验证入口 |
| --- | --- |
| contracts 与业务规则 | `uv run --locked --no-sync pytest -q <相关测试路径> --basetemp=.artifacts/pytest-<task>`；业务测试从 [tests/modules](../../../../tests/modules)选择，跨边界模型行为从 [tests/integration](../../../../tests/integration)选择 |
| 配置、工作台、数据库与分发 | [tests/core](../../../../tests/core)与 [tests/packaging](../../../../tests/packaging)；基线修改核对 test_image_management_migration.py |
| HTTP、客户端、原生协议与本机 CLI | [tests/interfaces](../../../../tests/interfaces)，沿对应实现的调用方选测试；接口快照与代理白名单一致性入口见[接口参考](../../../../docs/references.md#一致性) |
| MCP 工具与开发重载 | [tests/interfaces/mcp](../../../../tests/interfaces/mcp)中的 test_fastmcp_catalog.py 和 test_fastmcp_reload.py，分别核对目录和跨进程重载行为 |
| Python 模块依赖方向 | `uv run --locked --no-sync pytest tests/architecture -q --basetemp=.artifacts/pytest-<task>`；涉及前端依赖时使用根 `pnpm check:boundaries` |
| 文档、导航与技能 | `pnpm check:docs` |

真实联调沿本次改动的普通入口观察结果。例如从生成 CLI 或 MCP 创建测试数据集，沿共享客户端与 HTTP 验证有序成员及 revision；原生软件调用验证实际调用回执与已检查结果。对未知写入结果先查询原回执，再根据所属子系统契约决定继续方式。

回执记录实际 workspace、命令、结果与日志位置，并分别说明实现、自动验证、真实运行和用户验收。格式与浏览器测试配置见[测试文档](../../../../docs/testing.md)。索引提供验证入口，具体检查范围由当前改动决定。
