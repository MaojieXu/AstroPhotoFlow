# 模块与数据流

所有产品实现位于 `src/astrophotoflow/`。仓库根 `__init__.py` 仅承担 ComfyUI 的扩展发现与接线。

| 模块 | 职责 |
|---|---|
| `backend` | FastAPI、SQLAlchemy/SQLite、配置、导入、资产／数据集、回收站和 Alembic 迁移 |
| `frontend` | Vue 3、TypeScript、Pinia、Zod；素材库与设置页面，共享现有工作区状态和保存流程 |
| `comfyui` | 同源代理、checkout 服务管理、CPU 工作台的插件入口 |
| `cli` / `client` / `mcp_server` | 工作台命令及现有资产 HTTP API 的 CLI、stdio MCP 包装 |
| `workbench` / `vendor` | 固定 ComfyUI 来源、CPU 环境和工作台进程生命周期 |

浏览器通过 ComfyUI 同源代理访问资产服务；代理在服务端添加令牌，令牌不交给前端。CLI 和 MCP 通过同一领域 API 访问数据，不直接修改 SQLite。

后端按已有业务职责拆分路由，公共认证、会话和序列化仅承载实际共享逻辑。`comfyui` 包普通导入无插件注册副作用，注册只发生在扩展入口。

checkout 的静态资源由根入口从 `build/frontend/` 加载；wheel 中的 CPU 插件携带自己的 `assets/`。工作台复制的是插件目录，不能将 checkout 的相对路径用于已安装插件。

Python 项目、依赖锁和 Node 项目配置均统一在仓库根。前端构建先于 Python 发行构建；sdist 携带已编译资源，从 sdist 生成 wheel 不需要 Node。
