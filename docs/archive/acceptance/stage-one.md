# AstroPhotoFlow 第一阶段交付与验收记录

**日期：2026-10-22；分支：`feature/database`；结果：第一阶段验收通过。**

本记录只覆盖 T01 第一阶段。资产管理第二、第三阶段尚未实施；本阶段成果留在 `feature/database`，未合并到 `dev`。本次没有导入文件、生成演示资产或添加资产写入 API。

详细设计仍以[第一阶段技术与接口设计](第一阶段技术与接口设计.md)为准，阶段出口及合并条件见[三阶段实施计划](资产管理三阶段实施计划.md)。

## 交付内容

- `service/`：独立 FastAPI 服务、SQLAlchemy 模型、Alembic 初始迁移、CLI、配置示例和 `uv.lock`。
- `src/astrophotoflow/proxy.py`：ComfyUI 同源代理，只登记第一阶段的 18 个方法／路径组合。
- `frontend/src/assets/`、`frontend/src/workspace/`：Zod API 契约、Pinia 状态、AstroFlow 侧栏内资产工作区和配置表单。
- `service/openapi.json`：从当前 FastAPI 应用生成的 OpenAPI 快照。
- [服务启动和迁移说明](../service/README.md)及根目录 README 更新。

## 自动化验证

| 验证 | 结果 |
|---|---|
| `UV_PROJECT_ENVIRONMENT=/home/maojiexu/.cache/astrophotoflow/feature-database-service-venv uv run --locked --project service --extra test pytest -q -p no:cacheprovider service/tests` | 12 项通过；新增项目／设备／拍摄配置的默认、active、archived、all 状态筛选回归，项目拍摄配置关联的替换、清空、revision 递增与失败原子性回归，以及普通文本／PATCH／科学快照的时间字符串保真回归；代理查询参数与重复键由 test_proxy_whitelist_origin_headers_and_upstream_status 验证 |
| Alembic 与 SQLAlchemy 模型对照 | 新库应用 `0001_foundation` 后，`compare_metadata` 无差异 |
| `./node_modules/.bin/vitest run --config vitest.config.ts`（在 `frontend/`） | 10 项通过；新增完整加载 201 条拍摄配置、查询失败清除旧记录、搜索／筛选重置分页及旧响应不覆盖新查询回归 |
| `./node_modules/.bin/vue-tsc --noEmit`（在 `frontend/`） | 通过 |
| `./node_modules/.bin/vue-tsc --noEmit && ./node_modules/.bin/vite build`（在 `frontend/`） | 类型检查与 Vite 构建通过，生成扩展 JS/CSS |
| `pnpm --dir frontend install --frozen-lockfile` | 依赖锁文件安装通过 |
| OpenAPI 路由检查 | 12 个路径模板、18 个方法／路径组合；资产及项目资产引用均只有 GET |

Python 测试输出了两类非失败警告：Starlette 对当前测试客户端的弃用提示；Alembic autogenerate 对 Asset 与 AssetVersion 循环外键的排序提示。初始迁移可正常应用，自动对照无 schema 差异。该循环关系按设计保留，后续迁移继续沿用显式迁移脚本。

宿主人工复验本轮未执行。修复未改扩展注册、侧栏挂载或宿主布局；新增页面行为由 Vue 组件回归覆盖，代理参数由隔离 aiohttp 服务回归覆盖，旧的 ComfyUI 实机结果作为此前集成证据保留。

本轮六项复验已完成：三个配置列表的状态筛选生效；项目表单加载所有关联配置页；仅按 datetime 字段生成 UTC Z，不改写普通文本或已保存快照；代理保持搜索值和重复查询参数；失败请求清除旧类别记录；搜索与筛选回到第一页，并由请求代次阻止过期响应覆盖当前结果。

第一条测试命令曾误从仓库根目录收集到 Cookiecutter 模板测试，因该独立测试环境没有安装模板所需的 yaml 模块而在收集阶段停止。随后将运行范围限定到 service/tests，目标服务测试 12 项全部通过；模板测试本轮未运行，也未添加其依赖。

## ComfyUI 集成验证

使用现有 ComfyUI 0.42.0、前端 1.57.1 宿主；每次重启前队列均为空。集成验收结束后，ComfyUI 规范扩展链接指向 `feature/database` worktree，原 `main` 链接保存在 `custom_nodes` 之外；宿主已用阶段一扩展启动。

- 领域服务在本机 8190 端口启动；新数据库由 Alembic 创建，健康与能力接口通过代理返回成功。
- 浏览器工作区呈现在 AstroPhotoFlow 侧栏内，包含素材库、节点仓库、可安装软件、Agent 聊天、设置五个区域入口；素材库与配置管理连接真实服务，其他三个区域明确显示未接入状态。
- 在隔离的临时数据库中，通过界面创建项目、相机和暗平场配置，并关联到项目；三类记录均从服务重新读取并展示。
- 模拟第二个客户端以旧 revision 保存；界面显示 409 冲突、请求 ID 和处理提示，同时保留未保存的表单草稿。
- 项目资产页面对已存在项目返回真实空列表；未创建资产数据。
- 实际 ComfyUI 页面验证点击一级入口和管理页分段导航都只更新当前侧栏内容，没有跳转或打开另一个界面；校准素材作为资产用途筛选提供。单元测试验证未保存表单切换时可取消并保留草稿。
- 浏览器控制台未见错误。

临时 UI 测试数据库及记录已清理；默认产品数据库保留初始化后的空库。原侧栏静态展示验收作为历史结果沿用，本次没有重复执行。

## 停止范围与后续

第一阶段达到停止线。资产导入、BLAKE3 计算、解析、预览、任务队列、引用写入、发布、软件 Node、MCP 和 Agent 均未实施。

按计划在这里停止，等待第二阶段指令。第一、第二阶段成果都继续留在 `feature/database`；仅三个阶段全部完成、各阶段验收及必要的三阶段集成回归通过且没有阻断问题后，才具备合并到 `dev` 的条件；实际合并仍按用户指令执行。
