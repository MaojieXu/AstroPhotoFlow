# Agent 开发约定

## 开始任务

1. 核对分支与工作区，保留用户未提交内容。集成分支是 `dev`；提交、推送、合并按用户授权。
2. 先读[文档入口](docs/README.md)，按任务进入对应层；跨模块再读[架构](docs/architecture.md)。
3. 用架构文档的模块表定位源码，再读改动范围附近的 `AGENTS.md`、代码与测试；无需通读全部文档。
4. 未定的产品选择询问用户；常规实现自行完成。用户后续明确要求优先于初始需求，不从历史文档恢复已取消任务。

## 最小正确改动

- 广泛了解现状，狭窄修改；不顺带重构、改名、格式化或新增依赖。
- 新增分支、默认值、重试、回退、兼容层或抽象，必须对应具体需求、观察到的故障、已有测试或仓库不变量；没有依据就让失败清晰可见。
- 不创建空服务、假接口、预注册能力或第二套原生机制；只在真实复用需求出现时提取公共能力。
- 不擅自启停共享 runtime、更新正常 dev、修改默认 workspace、全局 MCP、令牌或真实素材。

## 集成与发布

- 从 `dev` 开分支，通过适用检查后可在本地合入 `dev`，无需 PR 或独立审批。合并及推送 `dev` 按用户授权，详见[贡献指南](CONTRIBUTING.md)。
- 发布只做 `X.Y.Z-dev.N`。`dev` → `main` 走发布 PR，主分支合并与 tag 需另行授权。

## 必须保持的边界

- 基于 ComfyUI 的本地网页工作台，两个常驻服务。外部 Agent 经平台 MCP 操作；不内置聊天、推理、模型会话或生成式模型凭据管理。
- 复用原生 Vue／Pinia、画布、JSON、自动保存、本地草稿、撤销、转换、队列、进度及取消。
- 工作流归属以[产品需求](docs/product/workflow.md)为准。自研 projects/workflows 已在当前候选中拆除，不从旧文档恢复已取消的项目图管理或完整运行库；具体调用／结果能力分别归 software／data，跨模块装配归 interfaces。
- `contracts` 只依赖标准库与 Pydantic；`core` 不依赖业务，显式迁移元数据装配除外。
- 业务通过模块公开入口合作，不读其他模块私有 ORM。HTTP／CLI／MCP 共用服务能力，不直接写 SQLite；本机启停使用 core 控制入口。
- 自研 UI 在 `frontend/packages/astrophotoflow-ui`；原生通过包导出消费。原生 Store、画布及事件协调在 `frontend/src/platform/astrophotoflow`，UI 包不能反向导入原生单例。
- 保留稳定素材身份、固定版本／成员、设备快照、校准及原件保护。省略、null、0 不混用，预览不当科学输入，未知结果先查询、不盲目重跑。
- Siril 为独立私有 Bundle，平台保留 SDK 与目录快照。
- 构建产物放 `.artifacts/build`、`.artifacts/dist`；`frontend/build` 是源码。根 `package.json` 是任务入口，前端依赖与锁文件在 `frontend`。

## 文档与验证

- 文档规则见 [docs/AGENTS.md](docs/AGENTS.md)：单一出处、预算、双语配对、Agent Notes、Skills 与门禁。
- 文档只写当前状态；决定、修复与简化的取舍写 Agent Note，讨论留在 PR。
- 按[测试文档](docs/testing.md)记录验证回执与日志，分别说明实现、自动验证、真实运行与用户验收。
