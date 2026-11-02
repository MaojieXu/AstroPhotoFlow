# Agent 开发约定

## 开始任务

1. 核对分支与工作区，保留用户未提交内容。集成分支是 `dev`；不修改或合并到 `main`，提交、推送按用户授权。
2. 纯空间／环境准备只读 [开发流程](docs/development/README.md) 并执行固定入口；开发任务先读 [当前上下文](docs/development/current-context.md) 和 [当前计划](docs/development/implementation-plan.md)，产品任务再读 [需求](docs/requirements/README.md)，跨模块再读 [架构](docs/architecture/overview.md)。
3. 用 [源码导航](docs/architecture/module-map.md) 定位，再读修改范围内适用的 AGENTS.md、代码和相关测试。无需通读所有模块、历史设计或验收日志。
4. 未定的产品选择询问用户；常规实现选择自行完成。用户后续明确要求优先于初始需求，不要从历史文档恢复已取消任务。

## 最小正确改动

- 广泛了解相关现状，狭窄修改；不顺带重构、改名、格式化或加依赖。
- 新增分支、默认值、重试、回退、兼容层或抽象，必须对应具体需求、观察到的故障、已有测试或仓库不变量；没有依据就让失败清晰可见。
- 不创建空服务、假接口、预注册能力或第二套原生机制。只在真实复用需求出现时提取公共能力。
- Feature 可实现、编写必要测试、构建和类型编译并提供独立预览，默认不执行测试套件或综合验收；用户确认可以集成后，由 Git Manager 组织审查和必要验证。文档链接检查与接口快照生成可随对应文档任务执行；已通过的检查不无故重复。
- 不擅自启停共享 runtime、更新正常 dev、修改默认 workspace、全局 MCP、令牌或真实素材。
- 环境准备读取阶段回执；成功路径不临时重写准备脚本、反复读取日志或重复已通过的检查，失败才定向排错。

## 并行开发与集成

- 一个 Git Manager 负责空间准备、清理、独立审查、测试、修复和串行合并 `dev`；Feature 只在自己的分支、Worktree、runtime 与 workspace 工作，不自行合并或默认推送。
- Feature 按[开发流程](docs/development/README.md)冻结并回传待审 Brief，暂停修改；用户确认可集成后才由 Manager 组织审查。Reviewer 使用独立上下文，只根据最终需求、必要约束和代码变更找问题，不修改代码。
- `demo` 只表示验收环境，不设长期分支；集成、推送、空间清理与 Feature Chat 归档可由用户一次明确授权，推进 `main`、发布 tag 和正式发布仍须另行授权。操作步骤、角色 Prompt 和 Brief 格式统一在 [开发流程](docs/development/README.md)。

## 必须保持的边界

- 基于 ComfyUI 的本地网页工作台，两个常驻服务。外部 Agent 经平台 MCP 操作；不内置聊天、推理、模型会话或生成式模型凭据管理。
- 复用原生 Vue／Pinia、画布、JSON、自动保存、本地草稿、撤销、转换、队列、进度及取消。
- 工作流归属以[有效需求](docs/requirements/README.md#native-workflow-ownership)为准。自研workflows已在本候选中拆除，不从旧文档恢复已取消的项目图管理或完整运行库；具体调用／结果能力分别归software／data，跨模块装配归interfaces。
- `contracts` 只依赖标准库与 Pydantic；`core` 不依赖业务，显式迁移元数据装配除外。
- 业务通过模块公开入口合作，不读其他模块私有 ORM。HTTP／CLI／MCP 共用服务能力，不直接写 SQLite；本机启停使用 core 控制入口。
- 自研 UI 在 `frontend/packages/astrophotoflow-ui`；原生通过包导出消费。原生 Store、画布及事件协调在 `frontend/src/platform/astrophotoflow`，UI 包不能反向导入原生单例。
- 保留稳定素材身份、固定版本／成员、设备快照、校准及原件保护。省略、null、0 不混用，预览不当科学输入，未知结果先查询、不盲目重跑。
- Siril 为独立私有 Bundle，平台保留 SDK 与目录快照。当前只做 `dev`／`X.Y.Z-dev.N`；stable 和无后缀正式发布须用户另行明确批准。
- 构建产物放 `.artifacts/build`、`.artifacts/dist`；`frontend/build` 是源码。根 package.json 是任务入口，前端依赖与锁文件在 `frontend`。

## 文档怎么维护

- [需求](docs/requirements/README.md) 写用户要什么；[架构](docs/architecture/overview.md) 写职责与数据归属；[ADR](docs/decisions/README.md) 只记录重要取舍及原因。
- [当前上下文](docs/development/current-context.md) 只放有效状态与缺口；[当前计划](docs/development/implementation-plan.md) 只细化下一项实际任务。旧22 Batch已降为参考，不能照旧批次自动开工。
- 接口字段、签名和 schema 以代码为准；[API入口](docs/api/README.md) 说明如何生成与查询，不手抄接口表。
- 结果放 [验证记录](docs/development/test-matrix.md)，完整日志进 `.artifacts`。实现、自动验证、真实运行和用户验收分别说明，不能互相代替。
- 同一规则只维护一处，其他文档用链接；Feature Brief 默认放聊天最终消息，集成时只更新受影响文档，不逐次同步全局状态。不再要求先写完五模块概要、数据草案、全量接口详设才能编码；仅在当前任务需要时补输入输出示例、约束与验收。
