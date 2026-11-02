# 现代化重构：本地官方文档

本包配合[重构计划](../../development/modernization-plan.md)使用，按阶段读取所需章节，不一次性加载全部正文。

抓取完成时间：`2026-10-31T08:49:40.878419Z`。共28组资料、254份官方正文／引用片段／许可证／发布元数据，合计5,760,389字节（5.49 MiB）；下载失败0项。

本轮只准备文档。新增依赖已选定但未安装联调，未运行依赖解析或应用验收，重构G0—G7尚未开始。实际安装依赖仍以项目锁文件为准。

## 来源与离线阅读

- [manifest.json](manifest.json)记录采用版本、固定tag／commit、原文和下载URL、时间、文件大小、SHA-256、许可证位置及必要引用关系。
- 上游文件按原始字节保存，不翻译或替换正文；各库INDEX是本项目编写的阅读导航。
- 发布tag可用时固定到其提交。Vue、TypeScript、pnpm使用滚动文档仓库的固定提交，不宣称逐补丁匹配；Siril、SQLite官网资料是日期快照。
- TanStack的Vue覆盖页和公共正文一起收录；FastAPI示例片段已补齐；watchfiles的API生成指令配有同版本源码签名和docstring。
- 必要include／ref的本地对应关系见各库INDEX。普通延伸阅读可能未收录，用INDEX中的官方来源访问；不宣称这是整站镜像或可离线构建的上游文档网站。
- 保留各项目LICENSE／NOTICE及SQLite版权说明；文档中的命令和示例只用于阅读，不随下载执行。

## 按阶段阅读

| 阶段 | 本地官方资料 | 阅读重点 |
|---|---|---|
| G0 固定版本／生成验证 | [fastmcp](<fastmcp/4.1.4/INDEX.md>)、[cyclopts](<cyclopts/5.3.2/INDEX.md>)、[@hey-api/openapi-ts](<hey-api/0.99.0/INDEX.md>)、[zod](<zod/4.6.5/INDEX.md>)、[@tanstack/vue-query](<vue-query/5.105.0/INDEX.md>)、[pydantic](<pydantic/2.14.1/INDEX.md>)、[uv](<uv/0.13.5/INDEX.md>)、[node](<node/26.8.2/INDEX.md>)、[pnpm](<pnpm/11.13.1/INDEX.md>) | 先读安装、依赖声明、生成插件配置、schema和CLI；只采用计划固定版本。 |
| G1 数据模型／服务 | [pydantic](<pydantic/2.14.1/INDEX.md>)、[sqlalchemy](<sqlalchemy/2.1.6/INDEX.md>)、[sqlite](<sqlite/3.53.1/INDEX.md>)、[alembic](<alembic/1.20.1/INDEX.md>)、[python](<python/3.12.15/INDEX.md>) | 类型／序列化、关系、约束、事务、新数据库基线；保留省略、null和0的区别。 |
| G2 SQL查询／分页 | [sqlalchemy](<sqlalchemy/2.1.6/INDEX.md>)、[sqlite](<sqlite/3.53.1/INDEX.md>) | SELECT、EXISTS、聚合、连接、索引和查询计划。 |
| G3 契约／SDK | [fastapi](<fastapi/0.161.1/INDEX.md>)、[pydantic](<pydantic/2.14.1/INDEX.md>)、[@hey-api/openapi-ts](<hey-api/0.99.0/INDEX.md>)、[zod](<zod/4.6.5/INDEX.md>)、[typescript](<typescript/6.0.3/INDEX.md>)、[vue-tsc](<vue-tsc/3.3.11/INDEX.md>) | 请求／响应、查询模型、错误、媒体类型、Fetch SDK、Zod与类型检查。 |
| G4 MCP／CLI | [fastmcp](<fastmcp/4.1.4/INDEX.md>)、[cyclopts](<cyclopts/5.3.2/INDEX.md>)、[httpx](<httpx/0.28.1/INDEX.md>)、[pytest-asyncio](<pytest-asyncio/1.4.1/INDEX.md>) | 工具schema、mount、BM25、错误、完整目录CLI生成、重载和真实客户端测试。 |
| G5 前端请求状态 | [@tanstack/vue-query](<vue-query/5.105.0/INDEX.md>)、[vue](<vue/3.5.42/INDEX.md>)、[pinia](<pinia/4.0.2/INDEX.md>)、[@hey-api/openapi-ts](<hey-api/0.99.0/INDEX.md>)、[vitest](<vitest/5.0.2/INDEX.md>) | 查询键、失效、取消、轮询、networkMode及表单草稿；Vue覆盖页与公共正文一起读。 |
| G6 Siril／开发基础 | [siril](<siril/1.4.4/INDEX.md>)、[python](<python/3.12.15/INDEX.md>)、[watchfiles](<watchfiles/1.3.0/INDEX.md>)、[httpx](<httpx/0.28.1/INDEX.md>)、[fastapi](<fastapi/0.161.1/INDEX.md>)、[uvicorn](<uvicorn/0.54.0/INDEX.md>)、[vite](<vite/8.2.2/INDEX.md>)、[uv](<uv/0.13.5/INDEX.md>)、[ruff](<ruff/0.17.3/INDEX.md>) | Siril命令／序列、模块加载、监听API、连接生命周期、工具配置；保持原生执行机制。 |
| G7 验证／交接 | [pytest](<pytest/8.4.2/INDEX.md>)、[pytest-asyncio](<pytest-asyncio/1.4.1/INDEX.md>)、[vitest](<vitest/5.0.2/INDEX.md>)、[@playwright/test](<playwright/1.63.0/INDEX.md>)、[ruff](<ruff/0.17.3/INDEX.md>)、[siril](<siril/1.4.4/INDEX.md>) | 隔离fixture、请求替身、trace、失败诊断及真实科学处理；区分验证层级。 |

## 各库目录

| 库／工具 | 采用版本 | 状态 | 文档来源 |
|---|---|---|---|
| [fastmcp](<fastmcp/4.1.4/INDEX.md>) | `4.1.4` | 新增：已选定，未安装联调 | 发布tag对应的固定提交原文 |
| [cyclopts](<cyclopts/5.3.2/INDEX.md>) | `5.3.2` | 新增：已选定，未安装联调 | 发布tag对应的固定提交原文 |
| [@hey-api/openapi-ts](<hey-api/0.99.0/INDEX.md>) | `0.99.0` | 新增：已选定，未安装联调 | 发布tag对应的固定提交原文 |
| [@tanstack/vue-query](<vue-query/5.105.0/INDEX.md>) | `5.105.0` | 新增：已选定，未安装联调 | 发布tag对应的固定提交原文 |
| [watchfiles](<watchfiles/1.3.0/INDEX.md>) | `1.3.0` | 新增：已选定，未安装联调 | 发布tag对应的固定提交原文 |
| [ruff](<ruff/0.17.3/INDEX.md>) | `0.17.3` | 新增：已选定，未安装联调 | 发布tag对应的固定提交原文 |
| [pytest-asyncio](<pytest-asyncio/1.4.1/INDEX.md>) | `1.4.1` | 新增：已选定，未安装联调 | 发布tag对应的固定提交原文 |
| [fastapi](<fastapi/0.161.1/INDEX.md>) | `0.161.1` | 沿用现有锁文件 | 发布tag对应的固定提交原文 |
| [pydantic](<pydantic/2.14.1/INDEX.md>) | `2.14.1` | 沿用现有锁文件 | 发布tag对应的固定提交原文 |
| [sqlalchemy](<sqlalchemy/2.1.6/INDEX.md>) | `2.1.6` | 沿用现有锁文件 | 发布tag对应的固定提交原文 |
| [alembic](<alembic/1.20.1/INDEX.md>) | `1.20.1` | 沿用现有锁文件 | 发布tag对应的固定提交原文 |
| [httpx](<httpx/0.28.1/INDEX.md>) | `0.28.1` | 沿用现有锁文件 | 发布tag对应的固定提交原文 |
| [uvicorn](<uvicorn/0.54.0/INDEX.md>) | `0.54.0` | 沿用现有锁文件 | 发布tag对应的固定提交原文 |
| [vue](<vue/3.5.42/INDEX.md>) | `3.5.42` | 沿用现有锁文件 | 滚动文档源码的固定提交快照 |
| [pinia](<pinia/4.0.2/INDEX.md>) | `4.0.2` | 沿用现有锁文件 | 发布tag对应的固定提交原文 |
| [zod](<zod/4.6.5/INDEX.md>) | `4.6.5` | 沿用现有锁文件 | 发布tag对应的固定提交原文 |
| [typescript](<typescript/6.0.3/INDEX.md>) | `6.0.3` | 沿用现有锁文件 | 滚动文档源码的固定提交快照 |
| [vue-tsc](<vue-tsc/3.3.11/INDEX.md>) | `3.3.11` | 沿用现有锁文件 | 发布tag对应的固定提交原文 |
| [vite](<vite/8.2.2/INDEX.md>) | `8.2.2` | 沿用现有锁文件 | 发布tag对应的固定提交原文 |
| [pytest](<pytest/8.4.2/INDEX.md>) | `8.4.2` | 沿用现有锁文件 | 发布tag对应的固定提交原文 |
| [vitest](<vitest/5.0.2/INDEX.md>) | `5.0.2` | 沿用现有锁文件 | 发布tag对应的固定提交原文 |
| [@playwright/test](<playwright/1.63.0/INDEX.md>) | `1.63.0` | 沿用现有锁文件 | 发布tag对应的固定提交原文 |
| [uv](<uv/0.13.5/INDEX.md>) | `0.13.5` | 沿用现有工具链 | 发布tag对应的固定提交原文 |
| [node](<node/26.8.2/INDEX.md>) | `26.8.2` | 沿用现有工具链 | 发布tag对应的固定提交原文 |
| [pnpm](<pnpm/11.13.1/INDEX.md>) | `11.13.1` | 沿用现有工具链 | 滚动文档源码的固定提交快照 |
| [python](<python/3.12.15/INDEX.md>) | `3.12.15` | 现有产品runtime | 发布tag对应的固定提交原文 |
| [sqlite](<sqlite/3.53.1/INDEX.md>) | `3.53.1` | 现有产品runtime | 滚动官网日期快照 |
| [siril](<siril/1.4.4/INDEX.md>) | `1.4.4` | 现有固定软件 | 官方文档网站日期快照 |

## 已知边界

- 本地关键正文及必要引用可以断网读取；普通延伸阅读、示例中依赖的外部服务和上游站点渲染组件不属于离线包。
- 本机开发Python为3.12.4，产品runtime为3.12.15；标准库文档选用v3.12.15。SQLite实际版本分别为3.45.3和3.53.1，不是独立pip依赖。
- FastMCP的HTTPX2／底层MCP依赖与平台HTTPX客户端分开核对；Hey API插件名不等于额外安装包。
- 资料完整性、版本声明核查不代表解析器、生成器或业务运行已经验证通过。
- 更新资料时同步记录实际固定来源和新散列，保留原文及许可证，不直接改写快照中的API以适配实现。
