# 模块与数据流

所有产品实现位于 `src/astrophotoflow/`。仓库根 `__init__.py` 仅承担 ComfyUI 的扩展发现与接线。

| 模块 | 职责 |
|---|---|
| `config` | 纯 Python 的配置定位、TOML 解析、类型检查和 workspace 存储路径 |
| `backend` | FastAPI、SQLAlchemy/SQLite、配置、导入、资产／数据集、回收站和 Alembic 迁移 |
| `frontend` | Vue 3、TypeScript、Pinia、Zod；素材库与设置页面，共享现有工作区状态和保存流程 |
| `comfyui` | 同源代理、checkout 服务管理、CPU 工作台的插件入口 |
| `cli` / `cli_commands` | 工作台兼容命令、结构化领域命令及 JSON 请求体 |
| `client` / `client_domains` | 共享 HTTP 传输、错误和按导入／素材／配置组织的类型化操作 |
| `mcp_server` / `agent_tools` | stdio MCP 启动及按领域注册的工具，与 CLI 共用客户端 |
| `workbench` / `vendor` | 固定 ComfyUI 来源、CPU 环境和工作台进程生命周期 |

浏览器通过 ComfyUI 同源代理访问资产服务；代理在服务端添加令牌，令牌不交给前端。CLI 和 MCP 通过同一领域 API 访问数据，不直接修改 SQLite。

后端按已有业务职责拆分路由，公共认证、会话和序列化仅承载实际共享逻辑。`comfyui` 包普通导入无插件注册副作用，注册只发生在扩展入口。

checkout 的静态资源由根入口从 `build/frontend/` 加载；wheel 中的 CPU 插件携带自己的 `assets/`。工作台复制的是插件目录，不能将 checkout 的相对路径用于已安装插件。

CPU 源码和依赖可以共享；插件及其 assets 位于各 workspace/comfyui-data 下，避免 worktree 间覆盖。导入线程池由服务 lifespan 创建并排空；大图生成复用其预览线程池，缓存状态与清理通过同一数据库事务边界协调。

Python 项目、依赖锁和 Node 项目配置均统一在仓库根。前端构建先于 Python 发行构建；sdist 携带已编译资源，从 sdist 生成 wheel 不需要 Node。
