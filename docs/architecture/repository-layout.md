# 七模块文件架构与迁移记录

日期：2026-10-25。实施分支：`branch/redesign`。本次将已有代码迁入七模块的长期位置，保持业务行为和公开协议；验收证据另见[当前上下文](../development/current-context.md)。

## 决策与范围

- 保留 `engine/ComfyUI`、`frontend`、`src/astrophotoflow` 三块主干和完整上游 workspace，暂不裁剪上游应用。
- 公共基础和六个业务模块按职责纵向组织；模块内部按实际需求分层，不把模块变成独立服务或第二套图调度器。
- 一个私有 `@astrophotoflow/ui` 组件包承载自研界面，通过公开入口接入原生应用，共用 Vue、Pinia 和前端锁文件。
- 未实现模块建立 README／AGENTS 文档落点，不创建可导入的空实现、假接口或预注册功能。
- 内部导入路径迁移，不添加旧 backend schema 兼容层。公开客户端、命令、HTTP 和 MCP 行为保持。
- 产品构建输出归 `.artifacts`；原件、数据库、默认 workspace、全局 MCP 注册、虚拟环境、依赖缓存和参考仓库不迁移。

选择保留主干而未采用 apps 式整体搬迁，是为了保持固定上游的来源边界，并将变化集中在实际归属问题。采用私有 UI 包而未直接混入原生 src，是为了提供可独立定位的源码、测试和消费入口。此次没有拆解现有大组件、导入流水线或改变算法。

## 最终位置

| 位置 | 归属与规则 |
|---|---|
| `engine/ComfyUI` | 固定图执行引擎源码，保持原生注册和执行机制 |
| `frontend/src/platform/astrophotoflow` | 原生挂载与桥接，可使用原生组件、Store；对业务 UI 只使用包公开入口 |
| `frontend/packages/astrophotoflow-ui` | 私有源码组件包，包含 core 与六模块目录；不独立启动、不对外发布 |
| `src/astrophotoflow/core` | 配置、进程、认证、错误、数据库连接及迁移基础 |
| `src/astrophotoflow/modules` | data、software、nodes、workflows、runs、collaboration 的业务所有权 |
| `src/astrophotoflow/contracts` | 标准库和 Pydantic 构成的公共模型与纯校验器 |
| `src/astrophotoflow/interfaces` | HTTP 应用装配、服务命令、CLI、客户端领域操作、MCP 协议适配 |
| `src/astrophotoflow/client.py`、`cli.py` | 保留 AssetClient／ServiceApiError 和公开命令模块入口 |
| `src/astrophotoflow/comfyui` | 固定引擎网关入口，不注册或安装 AstroPhotoFlow 扩展 |
| `src/astrophotoflow/vendor` | 随包运行资源与来源清单；引擎归档由构建脚本生成，不手工编辑 |
| `.artifacts/build/frontend`、`.artifacts/build/python` | 完整网页和 Python 构建中间产物 |
| `.artifacts/dist` | wheel／sdist 发行物 |
| `.artifacts/archive/pre-restructure` | 新路径验收后保存根 build／dist 旧产物，不覆盖已有归档 |

根 `package.json` 只提供任务命令。根 `pnpm-workspace.yaml` 的空 packages 列表与 `verifyDepsBeforeRun: false` 用于 pnpm 11 的任务入口，防止它自动重装已退役的根前端依赖；真正的依赖 workspace 和唯一前端锁文件位于 frontend。

`frontend/build` 是上游构建辅助源码，不能作为产物归档或删除。包中 `web/`、`vendor/` 的安装资源位置保持，源码位置迁移不改变用户 workspace 布局。

## 迁移对照

下表左侧均为旧位置，后续任务不得恢复旧树。

| 原位置 | 新位置 |
|---|---|
| `src/astrophotoflow/frontend` | `frontend/packages/astrophotoflow-ui/src/modules/data` |
| 前端 `assets/client.ts`、`contracts.ts`、`host-client.ts` | 数据界面 `api/client.ts`、`api/contracts.ts`、`api/index.ts` |
| 原生 `NativeShell.vue`、`LibrarySidebarTab.vue`、`useLibrarySidebarTab.ts` | 原生产品桥接目录，由其 index.ts 对外导出 |
| `config.py`、`workbench.py` | `core/config.py`、`core/workbench.py` |
| `backend/db.py`、`schema.py`、`alembic.ini`、`alembic/` | `core/database/`，九份历史迁移内容保持 |
| `backend/models.py` 的 Base | `core/database/base.py`；具体数据模型留在 data/models.py |
| `backend/errors.py`、`dependencies.py` | `core/errors.py`、`core/http.py` |
| `backend/api.py`、`cli.py`、`system.py` | `interfaces/http/app.py`、`cli.py`、`system.py` |
| 其余 backend 数据业务文件 | `modules/data/`，保留主要文件名、函数与业务实现 |
| backend 各 schema 文件、预览模型、PhotoImportOptions | `contracts/` 的 common、assets、imports、datasets、projects、equipment、setups、calibration、trash、previews |
| `cli.py` 实现、`cli_commands.py` | `interfaces/cli/main.py`、`commands.py`；根 cli.py 保留入口 |
| `client_domains`、`agent_tools`、`mcp_server.py` | `interfaces/client`、`interfaces/mcp/tools`、`interfaces/mcp/server.py` |
| `tests/frontend` 与其真实 API 样例 | UI 包 `tests/modules/data` 与 `tests/fixtures` |
| `tests/backend`、`tests/workbench`、`tests/comfyui` | `tests/modules/data`、`tests/core`、`tests/interfaces/comfyui` |

服务的公开命令仍为 apf／apf-service，浏览器网关仍为 `/astrophotoflow/api/v1`，领域 API 仍为 `/api/v1`。内部模块路径和打包资源检查随迁移更新，不产生数据库 schema 升级。

## 依赖与装配

1. contracts 不依赖数据库、服务端、配置、客户端或引擎。
2. core 不依赖业务模块和接入层；Alembic env 是明确的元数据装配例外。
3. interfaces/http/app.py 通过 data/public.py 与 data/routes.py 装配现有业务；其他模块通过相应公开入口合作。
4. 客户端、CLI、MCP 使用 HTTP 服务，不直接操作业务 ORM 或 SQLite。
5. UI 包不导入原生应用；原生应用通过包导出消费 UI，画布协调集中在桥接区。
6. 后续模块的依赖与入口随真实实现补齐，不以占位目录宣称功能可用。

`tests/architecture` 检查 Python 导入方向；前端沿用 dependency-cruiser，检查 UI → 原生应用的禁止依赖、原生消费入口和模块公开入口。根命令：`pnpm check:boundaries`，运行前使用项目 Python 环境。

## 构建与发行

- 开发先安装 frontend workspace 依赖并构建网页，再安装或刷新 Python 项目。根不再执行前端依赖安装。
- 源码包排除 `.artifacts` 后，精确纳入 `.artifacts/build/frontend`；不纳入工作区、令牌、缓存、日志、Python 中间构建或旧发行物。
- wheel 继续包含完整 HTML、JS、CSS、静态资源和运行归档。sdist 携带预构建网页，支持没有 Node 的 wheel 重建。
- 构建、仓库外安装、浏览器与启动停止的证据分别记录，目录迁移完成不替代运行验收。

## 后续开发

[七模块导航](module-map.md)是任务入口，[开发路线](../development/platform-roadmap.md)规定先后依赖，局部 README／AGENTS 说明文件所有权。后续新增功能直接进入预定模块；如确需改变模块根布局，先记录架构决策，而不是在功能任务中临时另建源码树。
