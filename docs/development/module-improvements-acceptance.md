# 五分支开发验收记录

本记录区分已验证事实和待交付内容，不以计划或分支存在代替功能完成。

## 公共基础

- 功能基线：`a5c638133852c4a50d75579912868e165a203870`。
- 公共基础提交：`3f72b71ca2b4e3a13aad7bc0ef4893008906a325`。
- 源码 schema：`0007_setups_and_calibration`；未升级原展示实例数据库。
- 原始素材、原有展示 workspace、全局 MCP 配置保持原位。

| 检查 | 实际结果 | 本机证据 |
|---|---|---|
| workbench/comfyui 回归 | 19 passed | `.artifacts/reports/foundation-tests.xml` |
| 初始化复用、插件隔离和不切换默认指针 | 3 passed | `.artifacts/reports/runtime-isolation-tests.xml` |
| 公共模型、迁移、包资源及 OpenAPI | 9 passed，48 deselected | `.artifacts/reports/domain-foundation-tests.xml` |
| 前端回归 | 14 个文件、111 passed | 2026-10-25 `corepack pnpm test --reporter=dot` 输出 |
| 前端类型检查 | 通过 | `corepack pnpm typecheck` 输出 |
| 两个真实 CPU 实例隔离 | 通过，两个实例均已停止 | `.artifacts/reports/module-isolation-smoke.json` |
| diff 空白检查 | 通过 | 公共基础提交前 `git diff --check` |

双实例使用 37388/37390 和 38388/38390。分别导入不同的合成 PNG，查询结果及资产 ID 分离；
两份静态 JS 添加各自测试注释，实际 HTTP 返回值分别匹配对应文件，散列不同；
主页、服务健康、同源代理均通过，均报告 schema 0007。测试结束后两套进程状态均为 stopped，
默认 workspace 指针和全局 MCP 配置散列未变化。没有自动点击 UI。

环境说明：首次受限环境中的代理测试停在 loopback 通信，核对 PID/创建时间/命令后停止了该次运行；
使用允许 loopback 的环境重跑。首次正式结果为 16 passed/3 failed，失败来自旧测试遗漏 `proxy` 导入；
修正该实际测试错误后得到上述 19 passed。迁移元数据检查仍有既有循环外键排序 warning。

## 功能验收矩阵

| 编号 | 必须交付的行为 | 当前状态／应取得的证据 |
|---|---|---|
| IMP-01 | 登记与托管分离、立即可查询、前端只显示登记进度 | 4448b37 的登记屏障/实际组件回归通过，合并后前端119通过 |
| IMP-02 | 文件并发 2、预览并发 1，可配置且服务级有界 | 服务级峰值2/1、并行任务共享及退出排空测试通过 |
| IMP-03 | 上传无第二次整文件写入；外部托管后台复制 | c84f1a3 的24次分阶段对照及复制/归位/恢复回归通过；来源变化一致性补充21项通过 |
| IMP-04 | 自动分类、整批覆盖、未知不猜、预设优先级 | FITS/XISF、不可变快照及公共HTTP优先级通过；834f08b 保持省略字段读取观察值、显式null覆盖 |
| IMP-05 | 拉伸基准按固定成员顺序、同条件子组、重试恢复一致 | 竞速完成、首图失败和重试回归通过；精确像素保持与性能数据见导入记录 |
| PRE-01 | 点击 1080 px 按需预览、缓存、不放大 | 最终完整测试通过；真实RAW100×67/1080×720，现有PI照片960×540验证 |
| PRE-02 | 移除重复管理成员入口，组内浏览编辑和删除保留 | 前端135通过、类型检查和生产构建通过；固定成员分页与预览通过 |
| SET-01 | 目标项目与单图/组的固定版本引用 | API/组件固定引用回归通过；固定版本成员浏览及私有引用预览通过 |
| SET-02 | 五类设备、使用组合、内联设备不入设备库 | 99cb13c API/组件与快照测试通过 |
| SET-03 | 组合内预设与导入选用、不可追改历史快照 | 设置验收通过，集成新增HTTP优先级/快照测试通过 |
| CAL-01 | 校准库独立、Master Light 不归入校准库 | 1e43fba 独立All/Light/校准视图与组件测试通过 |
| CAL-02 | 固定校准版本、组默认、成员继承/null/覆盖、跨组隔离 | 版本/项目固定引用及覆盖回归通过，已合入bda6047 |
| CAL-03 | 校准关系参与永久删除预览与重新检查 | 19项校准回归通过，含两种输入顺序、重叠成员、真实文件失败及共享路径；集成24项通过 |
| TOOL-01 | 结构化客户端与主要业务 CLI/MCP 操作 | 58工具/CLI已实现，保留旧五名称；真实stdio含JPEG、导出/碰撞/MIME通过 |
| TOOL-02 | 与实际工具一致的素材管理 Skill | 项目Skill校验通过，随sdist保存，说明与58工具对应 |
| FINAL-01 | 保留 R4/受损照片/共享路径/外部原图回归 | d656741完整Python248 passed/1 skipped，原保护回归在内 |
| FINAL-02 | 全部前端测试、类型检查、生产构建 | 11a267f完整前端136 passed、类型检查与生产构建通过 |
| FINAL-03 | 仓库外 wheel 安装、sdist 无 Node 重建 | 安装/无Node重建通过；最终散列以packaging.json为准 |
| FINAL-04 | 独立复查、各分支提交与用户手动入口 | 三轮记录见复查链接；31388更新、HTTP/资源/MCP确认通过；不自动点击 |

## 分支状态

五个功能分支均已从公共基础创建。仅创建分支不计作功能完成。

| 分支／集成 | 当前代码与验证 |
|---|---|
| settings-organization | `99cb13cde654a4ab8f91fc3481e40086e6ed0e50`，后端/代理 71 passed、前端 116 passed、构建/类型检查通过；见[设置验收](settings-organization.md) |
| import-pipeline | `215425743387dd8fd56ed7208cbcfa30e3947e60`，含登记、实测优化及CFA重试修正；见[导入验收](import-pipeline.md) |
| 两分支集成 | `9a0706ef4566ff0fbb37b0e704b4c3f0b861200d`，解决上传接线和表单 ref 两处文本冲突，保留自动分类和预设选择；集成 Python 30 passed、前端 119 passed |
| calibration-library | `1e43fba667898122a8e59f533876c473cd8c65cf`，分支后端114/前端125通过；已合入 |
| library-preview | `96790808715be6c51128c297ae15c3c2854b585b`，缓存/格式/清理/重试通过；已合入 |
| library-agent-tools | `54c9eaf568db0a8630949feeadb8bb0713d4146a`，58工具及16项最终协议检查通过；已合入 |

公共上传/预设快照接受时序缺陷修复为 `7a8dd43`，补充 HTTP 接受回归通过。
导入分阶段性能对照及 XISF Header 分类/参数读取已完成，保留最初及后续原始测量，
不以最初登记速度结果代替总处理吞吐改善证据。

后续导入候选 c84f1a3 已合入 d46dc5a；24次等条件独立进程实验显示：托管后台中位数
1.727s→0.276s，上传后台1.732s→0.230s；第二次整文件写入134,254,080→0字节。
该测量对应 c84f1a3，不冒充之后全部代码的重新测量。校准候选1e43fba 已合入bda6047，
分支后端114、前端125通过；根集成校准/预设/OpenAPI24项通过。

## 最终候选与运行验收

后台运行代码为 `d6567414e57031f8694dfb3ed3f8b898deade84b`，最终前端为11a267f（只补创建视图存活守卫）；后续文档提交不改变运行代码。

- 完整Python：248 passed、1 skipped、1条既有SQLAlchemy循环外键排序warning，121.81s；`.artifacts/reports/final-python.xml`。
- 跳过：`test_ffmpeg_extracts_one_video_frame`，原因FFmpeg unavailable；不记为通过，本机未实际验证FFmpeg录制视频路径。
- 完整前端：136 passed、19文件，10.03s；`.artifacts/reports/final-frontend.log`。
- 类型检查/生产构建通过；`.artifacts/reports/final-release.log`。
- wheel仓库外安装、sdist禁用Node后重建安装通过；`.artifacts/reports/packaging.json`、`final-packaging.log`。
- [独立复查记录](module-improvements-review.md)区分三轮代码复查及随后缓存状态验收，不把运行测试冒充额外审查轮次。
- 原workspace显式升级0006→0007并备份；未重新导入素材。38条资产、原字段/版本/成员/参数、38条旧缩略图及原件size/mtime保持，数据表逐列比较通过。
- 38张照片的大图配方均可用，含8条历史unsupported任务；只实际生成一张PI样例960×540，其余保留按需生成。
- 主页/健康/同源代理通过，实际JS/CSS与本次build逐字节一致。
- 用现有全局注册的同一uv命令启动stdio会话：58工具、资产ID集合、原生MCP JPEG与前端缓存一致。
- 默认workspace指针/全局MCP配置散列未变，31388/31390运行；`.artifacts/reports/final-runtime.json`。
- Windows/Python3.12实际执行；Linux CI已配置但未远端运行。无push、PR或dev/main合并。
- 最终wheel的所有Python文件与当前src逐字节一致且没有多余旧Python模块；`.artifacts/reports/final-wheel-source-parity.json`。

手动入口及无需全量重导的检查见[手动验收](module-improvements-manual-check.md)。
