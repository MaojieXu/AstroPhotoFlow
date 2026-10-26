# 七模块文件架构验收

实施分支：`branch/redesign`；基线提交：`c11745a7b6499baa508d9062d1658edde9f0c925`。本轮不提交、不推送，不改变 dev／main 引用。

布局、迁移与入口分别见[文件架构](../architecture/repository-layout.md)、[七模块导航](../architecture/module-map.md)。本记录描述源码重构验收，不代表软件接入、节点制作、托管运行或完整 Agent 已实现。

## 实际环境

- Windows、Python 3.12、固定 ComfyUI 0.42.0 CPU runtime，Node 26.8.2、pnpm 11.13.1。
- 验收 Python 环境：`.artifacts/venvs/restructure`，使用相同 uv.lock 创建；没有移动原开发环境。
- 隔离 workspace：`.artifacts/workspaces/restructure`，端口 32488／32490；未激活默认 workspace，验收后服务已停止。
- 当前机器实际验证不替代 Linux 或其他平台验证，CI 配置继续保留平台矩阵。

## 结果与证据

| 检查 | 结果 | 本地证据 |
|---|---|---|
| Python 全部回归及导入边界 | 286 passed，1 skipped；既有 SQLAlchemy 外键环排序警告保留 | `.artifacts/restructure/python-isolated.xml`、同名 log |
| 引擎构建资源发布回归 | 1 passed；相同资源不覆写，变化资源经暂存发布 | `.artifacts/restructure/engine-build-test.log` |
| 私有 UI 组件 | 19 个文件、144 passed，既有业务断言保留 | `.artifacts/restructure/test-current.log` |
| 原生侧栏与画布 | 4 个文件、21 passed | `.artifacts/restructure/native-tests.log` |
| 类型与生产构建 | UI、原生应用类型检查及完整构建通过 | `.artifacts/restructure/release-build-final.log` |
| Python／前端依赖边界 | 无错误；保留 9 条组件循环依赖警告，本轮不拆解组件 | `.artifacts/restructure/boundaries.log` |
| ADR | 新 ADR 命名验证通过 | `.artifacts/restructure/adr-check.log` |
| 浏览器 | 5 组通过，无 page error 或外部请求 | `.artifacts/restructure/browser-final.log`、`.artifacts/reports/native-web` |
| 安装与发行 | 仓库外 wheel 安装、无 Node 的 sdist 重建及再安装通过；最终摘要以报告为准 | `.artifacts/reports/packaging.json` |

浏览器验证覆盖：原生素材侧栏、顺序与收起、设备和项目管理、未保存修改保护、图和视口保留、保存加载、LoadImage → SaveImage CPU 执行、浏览器上传、缩略图与自动拉伸预览、回收站恢复和刷新。

新空用户配置的上游首次模板弹窗会遮挡侧栏；现有测试原先使用已完成引导的配置。本轮在隔离浏览器测试中显式设置 `Comfy.TutorialCompleted`，保留产品首次引导实现，没有用强制点击跳过遮挡，也没有宣称首次引导已重新设计。

## 数据、契约和来源核对

- 迁移前后 OpenAPI 与全部 58 个 MCP 工具结构比对一致；快照位于 `.artifacts/restructure/openapi-before.json`、`mcp-before.json`。
- 218 个数据类／函数除导入外的行为 AST 一致；未重新设计数据模型、导入或预览算法。
- 固定引擎、冻结需求和九份历史迁移字节保持；原生引擎网关入口及 runtime 未因路径改名而重建。
- 隔离实例重启后，合成资产的 ID、版本、内容摘要及默认 workspace 指针一致；未操作用户原件和既有数据库。
- 服务端令牌未出现在全部 1149 个已服务网页资源中。源码包只纳入 `.artifacts/build/frontend` 文件，不包含 workspace、令牌、依赖目录、缓存或 .env。
- 旧根 build／dist 原样保存在 `.artifacts/archive/pre-restructure`，没有覆盖或删除其内容；frontend/build 上游辅助源码保持。
- 历史基准脚本验证了当前源码与重构前 Git 提交的模块加载；这不代表重新执行了整套性能基准。

## 开发环境说明

原 `.artifacts/venvs/dev` 更新项目安装时遇到 Windows 对 `apf.exe` 的文件占用，未强制覆盖。正式命令与协议验收使用新安装的隔离环境，不能将旧启动器的失败日志当作最终回归结果。

后续若原环境仍被占用，释放占用后正常执行 uv sync，或显式设置 `UV_PROJECT_ENVIRONMENT` 为已验证的隔离环境。此限制属于当前机器的安装状态；发行物及独立安装的 apf／apf-service 已验证。没有修改全局 MCP 注册或默认指针。
