# 需求、实现与测试矩阵

这里区分“当前实现的回归覆盖”和“完整 v1.0 产品验收”。某一子功能有测试不表示对应 FR 全部完成。

| 需求范围 | 当前实现 | 自动化证据 |
|---|---|---|
| FR-01 项目基础管理 | 创建、编辑、归档、引用及拍摄配置关联；完整托管工作流未实现 | `tests/backend/test_service.py`、前端 Workspace/Settings 测试 |
| FR-04 素材管理 | 分阶段异步导入、Header 分类、任务、预设快照、数据集、筛选排序与编辑 | backend ingestion/import_pipeline/service/library_sort；frontend Workspace/ImportDialog/ImportTasks；integration import_presets |
| FR-04/11 删除与恢复 | 已接受的组／照片回收站、确认范围、部分清理、R4、身份和固定版本保留 | backend service 的 trash 回归；frontend LibraryTrashDialog |
| FR-05 当前显示子集 | 100 px 缩略图、1080 px按需缓存、固定拉伸和项目固定成员浏览；完整比较未实现 | backend fits_preview/display_previews/video_preview；frontend PhotoPreviewDialog |
| FR-07 资料管理 MCP | 58工具及 CLI 共用领域客户端，覆盖素材／配置／校准；完整软件工作流未实现 | integration cli_mcp_protocol/client_operations |
| 设备组合与校准关系 | 内联设备、所属预设、固定校准版本、组默认／成员覆盖、历史引用保护 | backend setups/calibration/domain_foundation；frontend SettingsOrganization/CalibrationLibrary |
| FR-08 当前并发子集 | 参数 revision、过期请求拒绝；完整接管／撤销未实现 | backend service/ingestion、CLI/MCP 协议回归 |
| FR-13/15 CPU 交付 | 固定 ComfyUI 来源、包资源、生命周期接线 | `tests/workbench/`、`tests/packaging/`、发行验证脚本 |
| FR-14 当前服务边界 | 本地认证、代理来源／路径约束、原图和共享文件保护 | `tests/comfyui/`、backend service/ingestion |
| FR-15 契约与可重复构建 | 根锁文件、OpenAPI 快照、Zod、wheel/sdist | OpenAPI 等式和代理白名单测试、前端契约测试、发行验证 |

现有前端真实 API JSON 是 mock fixture，不能称为真实 31 图端到端验收。真实大素材不进入快速测试；本轮不重导入全量 Astro Dataset，也不自动点击前端。

待补的未来产品验收：FR-02/03/06/09/10/12，以及其他 FR 中未完成部分。AT-01 至 AT-28 保留在[冻结需求](../requirements/v1.0/07_实施路线与验收清单.md)，只有实际实现并取得对应证据后才能标记通过。

新增回归聚焦本轮真实风险：模块入口、插件复制路径、CLI/MCP 进程协议和从源码目录外安装；不为假想业务或未来能力编写测试。FFmpeg 不可用导致的视频用例跳过需在报告中单列，不能当作通过。
