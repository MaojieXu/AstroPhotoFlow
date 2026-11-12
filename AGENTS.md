# AGENTS.md

AstroPhotoFlow 是基于 ComfyUI 的本地网页工作台，每个 workspace 运行两个常驻服务。外部 Agent 经平台 MCP 操作。先读[文档入口](docs/README.md)，跨模块改动先读[架构](docs/architecture.md)，文档遵循 [docs/AGENTS.md](docs/AGENTS.md)。

## 数据与工作流

保留稳定素材身份、数据集当前成员顺序、设备快照、校准及原件保护。调用开始后固定实际输入与参数。省略、null、0 不混用，预览不当科学输入，未知结果先查询、不盲目重跑。

工作流归属以[产品需求](docs/product/workflow.md)为准。具体调用／结果能力分别归 software／data，跨模块装配归 interfaces。不从历史文档恢复已取消的自研 projects/workflows、项目图管理或完整运行库。

## 仓库布局

用[架构模块表](docs/architecture.md#模块与职责)定位源码，再读改动范围附近的 `AGENTS.md`、代码与测试。

前端修改、界面构建、样式与组件开发先加载 [astrophotoflow-frontend](.agents/skills/astrophotoflow-frontend/SKILL.md)，按任务索引定位架构、已有组件与调用实例。

平台后端开发、HTTP、MCP／CLI、原生桥接与联调先加载 [astrophotoflow-backend](.agents/skills/astrophotoflow-backend/SKILL.md)，按任务路由定位责任层、调用链与验证入口。

```text
src/astrophotoflow/                      Python 领域能力与接口
frontend/packages/astrophotoflow-ui/     自研 UI
frontend/src/platform/astrophotoflow/    原生 Store、画布与事件协调
engine/ComfyUI/                         固定版本的原生引擎
.agents/                               Agent Notes 与 Skills
docs/                                  产品、架构、子系统与操作文档
scripts/                               门禁与生成脚本
```

构建产物放 `.artifacts/build`、`.artifacts/dist`；`frontend/build` 是源码。根 `package.json` 是任务入口，前端依赖与锁文件在 `frontend`。

## 常用命令

环境与启动步骤见[开发文档](docs/development.md)。在仓库根目录运行。

```powershell
uv run --locked --no-sync pytest -q --basetemp=.artifacts/pytest-<task>
pnpm test                  # 前端单元测试
pnpm typecheck             # 自研 UI 类型检查
pnpm check:boundaries      # 架构边界检查
pnpm check:docs            # 文档门禁
pnpm docs:api              # 接口生成物
pnpm build                 # 前端构建
```

### 本地验证

按改动范围运行检查。按[测试文档](docs/testing.md)记录验证回执与日志，分别说明实现、自动验证、真实运行与用户验收。

## 开发约定

- **开始任务**。核对分支与工作区，保留用户未提交内容。集成分支是 `dev`，提交、推送、合并按用户授权。
- **需求选择**。未定的产品选择询问用户，常规实现自行完成。用户后续明确要求优先于初始需求，不从历史文档恢复已取消任务。
- **最小正确改动**。广泛了解现状，狭窄修改，不顺带重构、改名、格式化或新增依赖。
- **新增机制有依据**。新增分支、默认值、重试、回退、兼容层或抽象，必须对应具体需求、观察到的故障、已有测试或仓库不变量。没有依据就让失败清晰可见。
- **按真实需求复用**。不创建空服务、假接口、预注册能力或第二套原生机制，只在真实复用需求出现时提取公共能力。
- **原生能力**。复用 Vue／Pinia、画布、JSON、自动保存、本地草稿、撤销、转换、队列、进度及取消。
- **平台范围**。不内置聊天、推理、模型会话或生成式模型凭据管理。
- **模块依赖**。`contracts` 只依赖标准库与 Pydantic。`core` 不依赖业务，显式迁移元数据装配除外。
- **公开入口**。业务通过模块公开入口合作，不读其他模块私有 ORM。HTTP／CLI／MCP 共用服务能力，不直接写 SQLite。本机启停使用 core 控制入口。
- **UI 依赖**。原生通过自研 UI 包导出消费组件，UI 包不能反向导入原生单例。
- **集成**。从 `dev` 开分支，通过适用检查后可在本地合入 `dev`，无需 PR 或独立审批。合并及推送 `dev` 按用户授权，详见[贡献指南](CONTRIBUTING.md)。
- **发布**。只做 `X.Y.Z-dev.N`。`dev` → `main` 走发布 PR，主分支合并与 tag 需另行授权。

## 运行与素材保护

不擅自启停共享 runtime、更新正常 dev、修改默认 workspace、全局 MCP、令牌或真实素材。

## 文档与验证记录

文档只写当前状态，遵循 [docs/AGENTS.md](docs/AGENTS.md) 的单一出处、预算、双语配对、Agent Notes、Skills 与门禁规则。决定、修复与简化的取舍写 Agent Note，讨论留在 PR。

## 编辑这些约定

各层 `AGENTS.md` 只写本目录特有的约束与入口提示，遵循[分层规则](docs/AGENTS.md#agentsmd-分层)。修改后运行 `pnpm check:docs`。

## 外部集成

Siril 为独立私有 Bundle，平台保留 SDK 与目录快照。外部集成与引擎分发规则见[架构](docs/architecture.md#外部集成)。
