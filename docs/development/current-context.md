# 当前开发上下文

更新时间：2026-10-26。开发分支为 **dev**。原生网页和七模块源码迁移基线为 `16025dd89f2c3c2b25bae58bcc241e5202863c87`，已从原 dev `b6759ab` 快进合入；main 不属于本轮交付范围。

仓库为 [MaojieXu/AstroPhotoFlow](https://github.com/MaojieXu/AstroPhotoFlow)，origin 已使用新地址。本地目录已改为 `C:/Users/Administrator/Desktop/WorkSpace/AstroPhotoFlow`。目录改名和快进合并均已销项，不再执行旧目录切换脚本。

## 当前实现

- 固定 ComfyUI 0.42.0 和前端 1.57.1 的原生网页平台。画布始终挂载，节点库下依次为素材库、工作流；启动打开素材库，设备管理位于导入旁。
- Python 已按 core、contracts、modules/data、interfaces 归位；自研 UI 与原生桥接分开。其他五个业务模块只有文档占位，不表示已实现。
- 已有资产与集合版本、项目固定引用、导入、设备快照、校准关联、预览和回收站。schema 为 `0009_remove_legacy_capture_profiles`，数据 MCP 为 58 个工具。
- 单图自动拉伸从原件计算 RGB 背景白平衡和 MTF 配方，同步大图与缩略图；不修改原件、科学参数、版本身份和其他成员。

当前边界见[架构概览](../architecture/overview.md)、[模块导航](../architecture/module-map.md)和[素材行为](../architecture/assets.md)。

## 当前运行基线

- 开发 Python：`.artifacts/venvs/dev`，使用根 `uv.lock`；Node 26.8.2、pnpm 11.13.1，前端锁文件为 `frontend/pnpm-lock.yaml`。
- 正常 dev workspace：`.artifacts/workspaces/dev`，网页 31388、领域服务 31390；根 `.env` 与默认指针仍选择同一 workspace。
- 固定 CPU runtime：真实用户 LocalAppData 下的 `AstroPhotoFlow/runtime/native-web-0.1.0`，与旧 0.1.0 runtime 分离。
- 产品输出：`.artifacts/build/frontend`、`.artifacts/build/python`、`.artifacts/dist`。完整网页由 workspace/web 提供，不依赖 custom node 或扩展加载业务界面。
- 本轮隔离验收：`.artifacts/workspaces/docs-update`，网页 32588、领域服务 32590，不激活为默认 workspace。

目录改名后已按锁文件重新安装 dev，修复 editable 安装和命令入口；AstroPhotoFlow MCP、默认指针、编辑器和项目工具脚本中的有效旧路径已修正，其他 MCP 配置保持。本机固定工具入口为 `.artifacts/redesign/bin` 与其 Node 26 目录，不使用系统中版本不同的 Node/pnpm。

受限执行环境会将 LOCALAPPDATA 重定向到沙箱目录；本机维护使用正常用户环境访问已有 runtime，不修改产品路径解析，不新建另一套 CPU runtime。

本轮已验证 dev 网页、HTTP、CLI 和真实 MCP 访问同一库，112 条存量资产在重启前后保持；这里的数量是本轮观察值，不是后续固定验收条件。正常 dev 保持运行，隔离实例已停止，32588／32590 已释放。启动回执已修正为 `#/workflows`。

原件、令牌、配置与锁文件保持；SQLite 主文件字节在启停后变化，但 17 张逻辑表与改名前快照的行级摘要一致，外键检查通过。运行与发行证据统一记录于[验证矩阵](test-matrix.md)。

wheel 源码目录外安装、无 Node 的 sdist 重建与重装已通过。本轮仍只验证 Windows／CPU；首次引导体验与 Linux 验收没有因此标为完成。

## 已取消的旧任务

2026-10-26 用户确认：不重建历史 restructure 验收环境，不恢复 redesign 实例常驻运行，不恢复或继续保留 `branch/redesign`。已有环境、workspace 和证据保留。旧页面、固定照片数量和旧分支合入清单退出待办；有效业务场景进入验证矩阵。

## 后续有效待办

- 按[开发路线](platform-roadmap.md)细化数据引用、节点定义、工作流版本和运行回执，再验证首个真实外部软件操作。
- 补齐节点输入输出交接、软件适配、节点制作发布、项目工作流版本、托管运行、结果来源、画布同步和用户接管。
- 热发布需要原型验证；结果比较和项目记忆仍未实现。普通 CPU 图执行不能作为这些能力的完成证据。
- Linux 尚无本轮证据。FFmpeg 视频验证结果单独记录；XISF 全帧解码和拉伸开销属于已知限制，未承诺本轮优化。

真实 dev 不用于导入、删除或工作流写入验收；合成素材只写入隔离 workspace。不清库、不重新导入原件、不新增数据库备份。
