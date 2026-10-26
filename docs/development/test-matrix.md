# 需求、实现与验证矩阵

自动化回归、真实运行和完整产品验收分别记录。子功能通过不表示对应 FR 或全部 AT 已完成；历史结果不替代当前候选验证。

## 当前行为与验证入口

| 需求范围 | 已有行为及边界 | 验证入口 |
|---|---|---|
| FR-01 项目 | 资料、回收站、资产与集合固定引用；项目托管工作流未实现 | `tests/modules/data/test_service.py`；UI Workspace／Settings |
| FR-02/09 画布 | 画布与视口保留、保存加载、CPU 队列；天文适配和项目工作流权威未实现 | `tests/browser/native-web.mjs`；原生 GraphView／侧栏测试 |
| FR-04 导入 | 登记与托管分离、并发、Header 分类、预设快照、编辑与排序 | `tests/modules/data/test_import_pipeline.py`、`test_ingestion.py`、`test_library_sort.py`、`tests/integration/test_import_presets.py`；UI 导入／任务测试 |
| FR-04/11 删除 | 确认范围、部分清理、固定身份、共享路径与外部原件保护 | `tests/modules/data/test_service.py`、`test_calibration.py`；UI LibraryTrashDialog |
| FR-05 预览 | 100 px 缩略图、1080 px 大图、单图自动拉伸与 RGB 白平衡；完整比较未实现 | `tests/modules/data/test_auto_stretch.py`、`test_fits_preview.py`、`test_display_previews.py`、`test_video_preview.py`；UI PhotoPreviewDialog |
| 设备与预设 | 接受时冻结快照、删除后恢复／重试、历史名称和草稿保护 | `tests/modules/data/test_equipment_snapshots.py`、`test_setups.py`；UI SettingsOrganization／Workspace |
| 校准引用 | 默认、继承／null／覆盖、跨组隔离、历史清理保护；不执行校准 | `tests/modules/data/test_calibration.py`、`test_domain_foundation.py`；UI CalibrationLibrary |
| FR-07 数据 MCP | 58 工具与 CLI 共用服务；图编辑和软件运行工具未实现 | `tests/integration/test_client_operations.py`、`test_cli_mcp_protocol.py` |
| FR-08 并发 | revision 与过期请求拒绝；完整接管／撤销未实现 | 数据服务、导入及 CLI/MCP 回归 |
| FR-13/15 交付 | 固定引擎、进程生命周期、完整网页、源码外安装和无 Node 重建 | `tests/core`、`tests/packaging`、`scripts/verify_distribution.py` |
| FR-14 服务边界 | 认证、代理来源／路径、原件和共享文件保护 | `tests/interfaces/comfyui/test_proxy.py`；数据服务／导入回归 |
| FR-15 契约 | OpenAPI、Pydantic、前端 Zod 与 MCP 结构 | OpenAPI 快照、UI 契约和真实 stdio 测试 |

前端 API JSON fixture 是模拟数据，不是整批真实照片的端到端验收。浏览器写入验收使用隔离服务和合成 PNG，覆盖原生侧栏、未保存保护、画布／视口、保存加载、真实 CPU 执行、上传、自动预览、回收站恢复及刷新。

## 保留的历史证据

| 日期与候选 | 当时验证结果 | 本机证据与范围 |
|---|---|---|
| 2026-10-25，原生侧栏 `c11745a` | UI 144、原生侧栏／画布 21、浏览器 5 组；类型及构建通过 | `.artifacts/redesign/sidebar-frontend.xml`、`sidebar-native-tests.log`、`sidebar-browser.log`；Windows／CPU、合成素材 |
| 2026-10-25，七模块迁移阶段 `c11745a` 至 `16025dd` | Python 286 passed／1 skipped，另 1 项引擎构建回归通过；UI 144、原生 21、浏览器 5 组；OpenAPI 与 58 工具结构一致，发行验证通过 | `.artifacts/restructure/python-isolated.xml`、`engine-build-test.log`、`boundaries.log`、`browser-final.log`；218 个数据实现行为 AST 核对保持 |
| 2026-10-26，切换前 `16025dd` 加 URL 调整 | Python 287 passed／1 skipped，UI 144、侧栏 8；构建及发行通过 | `.artifacts/rename/*-before-move.log`、`python-before-move.xml`；仅证明切换前候选 |

旧阶段过程可从 Git 历史查询；本机日志与环境不随源码分发。历史独立复查和运行验收不表述为本轮新做的代码审查。

## 本轮改名收尾验收

日期：2026-10-26。基线 `16025dd`，候选包含文档清理和仓库 URL 调整。Windows／Python 3.12／CPU、Node 26.8.2、pnpm 11.13.1，依赖锁文件保持。

| 检查 | 本轮结果 | 证据 |
|---|---|---|
| dev 环境与路径 | 锁定重装、包定位、apf／apf-service 和固定工具版本通过；只更新 AstroPhotoFlow 的 MCP 注册内容，其他配置保持 | `.artifacts/docs-update/uv-sync.log`、`path-repair.json` |
| Python 全量 | 288 passed，无 skipped；FFmpeg 首帧用例实际执行通过。保留 1 条 SQLAlchemy 外键环警告 | `.artifacts/docs-update/python.xml` |
| 启动回执修复 | 实际启动仍打印旧 `#/library`；新增回归断言先复现，再将回执修正为 `#/workflows`。修复后工作台 5 项通过 | `start-url-before-fix.log`、`workbench.xml`，均位于 `.artifacts/docs-update` |
| 自研 UI | 19 个文件、144 passed | `.artifacts/docs-update/ui.log` |
| 原生侧栏与画布 | 5 个文件、25 passed；旧上游侧栏预期对齐已确认的节点库／素材库／工作流顺序，保留任务历史开关与菜单断言；定向格式和 ESLint 通过 | `.artifacts/docs-update/native.log`、`test-format.log`、`test-eslint.log` |
| 依赖边界 | Python 5 项通过；前端 0 errors、保留 9 条组件循环依赖警告 | `.artifacts/docs-update/boundaries.log` |
| 类型与生产构建 | 私有 UI 和原生应用类型检查、完整网页构建通过 | `.artifacts/docs-update/build.log` |
| 隔离浏览器 | 32588／32590、合成 PNG、5 组通过，含真实 CPU 执行、保存加载、上传与自动预览、回收站恢复 | `.artifacts/docs-update/browser.log`、`.artifacts/reports/native-web/results.json` |
| 网页／CLI／HTTP／MCP | 同库查询一致，真实注册命令启动 stdio 后发现 58 工具；1149 个网页文件与构建一致且不含领域令牌 | `.artifacts/docs-update/dev-before-restart.json`、`dev-after-restart.json` |
| 停止与重启 | 两套实例端口释放、重启后身份保持；dev 最终 running、隔离实例 stopped，默认 workspace 不变 | `.artifacts/docs-update/lifecycle.json` |
| 数据保持 | 118 个非数据库文件的大小／mtime／SHA-256 保持；SQLite 主文件字节变化，但 17 张表的行级摘要与改名前一致，外键有效；无新增数据库备份 | `.artifacts/docs-update/data-preservation.json` |
| 文档与冻结需求 | 54 份 Markdown 收敛至 28 份；本地链接、锚点与删除引用检查通过，冻结包含散列清单共 10 个文件原字节保持 | `.artifacts/docs-update/docs-check.json` |
| 发行与安装 | wheel 源码目录外安装、无 Node 的 sdist 重建及再安装通过；完整网页、迁移、入口和源码包范围检查通过 | `.artifacts/docs-update/distribution.log`、`.artifacts/reports/packaging.json` |

上述全量 Python 在启动回执修复前运行；该修复之后运行了对应工作台回归与真实启动／重启。

受限进程首次运行 UI 时出现跨进程临时目录 ENOENT；正常用户环境重跑后全部通过，未为该环境故障修改产品逻辑。早期失败和最终日志均保留在本轮目录。

浏览器脚本在隔离用户配置中显式设置 `Comfy.TutorialCompleted`，沿用上游首次引导；这 5 组检查不代表首次引导已重新设计或单独验收。运行核对使用 HTTP／CLI／MCP；数据库容器变化的诊断沿用维护脚本的只读 SQLite 快照比对，不构成新的业务访问路径。

## 仍需后续验收

- FR-02/03/06/09/10/12 及其他 FR 的未完成部分，按[当前路线](platform-roadmap.md)推进。AT-01 至 AT-28 原文保留在[冻结验收清单](../requirements/v1.0/07_实施路线与验收清单.md)。
- Linux 尚无本轮运行证据。视频用例在 FFmpeg 不可用的平台仍需单列为 skipped，不能计作通过。
- 用户最终业务体验验收与自动化回归分开。设置、设备快照和校准引用等有效场景见功能文档；旧页面、旧照片数量和退役入口不再作为条件。
