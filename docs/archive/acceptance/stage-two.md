# AstroPhotoFlow 资产管理第二阶段验收记录

**日期：**2026-10-22（ComfyUI 集成运行日志为 WSL UTC 2026-10-23）
**分支：**`feature/database`
**基线：**第一阶段验收提交 `ce8404e7b2bb177af739fd005df83a98a406d169`
**状态：**第二阶段 S2-AT-01 至 S2-AT-11 验收通过；实现停在第二阶段停止线，未开始第三阶段。

本记录依据[第二阶段技术与接口设计](第二阶段技术与接口设计.md)及[资产格式支持矩阵](资产格式支持矩阵.md)。验收使用临时数据库、临时素材和临时 HOME，不向产品库写入演示数据。

## 实际交付

- 独立服务 Alembic 迁移 `0002_asset_ingestion`，导入根目录读取与边界验证、引用／托管导入、BLAKE3、任务／逐文件结果、资产当前资料编辑、数据集成员版本、项目固定引用及 FITS Header／预览接口。
- AstroPhotoFlow 工作区接入素材浏览、导入表单、任务状态、资产编辑、数据集成员、项目引用、表格汇总和宿主内预览。
- 第二阶段 Python 依赖由 `service/pyproject.toml` 与 `service/uv.lock` 锁定。配置示例、服务说明、OpenAPI 快照、资产格式矩阵及本文已更新。
- `service/openapi.json` 从当前 FastAPI 应用实际生成，包含 36 个路径；代理白名单有 48 个明确的方法／路径，自动契约测试确认全部对应 OpenAPI 操作。

## S2-AT 验收结果

| 验收项 | 结果与证据 |
|---|---|
| S2-AT-01 根目录边界及路径 | 通过。临时根目录测试覆盖路径穿越、越界符号链接、中文及 `#` 特殊字符路径、目录分页与递归。服务和代理均拒绝相对导入根配置。 |
| S2-AT-02 导入形态与存储 | 通过。单文件形成独立资产，多选／目录形成数据集，单成员目录仍形成数据集；同批重复来源仅登记一次。引用与托管复制均有测试，复制源字节保持不变。零成功空目录不发布数据集。 |
| S2-AT-03 身份、散列及按需读取 | 通过。同文件跨批次产生不同资产 ID；导入 BLAKE3 与样本字节相符。删除引用源后，资产列表和项目固定引用仍可读取，不扫描原件或重算散列。 |
| S2-AT-04 人工资料优先 | 通过。Header 原始卡片和解析值独立保留；人工 Gain、零曝光和负温度胜出。文件 `IMAGETYP=Light Frame` 与用户提交的 Master Dark 分类不同，任务仍完成，原始分类提示单独保留。`CCD-TEMP` 保存在设定温度解析字段，不填入实测温度。未知值仍为空。 |
| S2-AT-05 当前资料与成员版本 | 通过。分类、参数及多行备注直接编辑，派生 role／校准级别同步更新且不新增 AssetVersion。项目引用读取固定版本与资产最新资料。数据集保留旧成员顺序，新成员追加；归档不删除固定项目引用。 |
| S2-AT-06 任务及两项恢复策略 | 通过。解析失败内容仍可入库并单独告警；重试保留关联任务及已登记资产。服务中断恢复沿用原 task ID。枚举期间取消只保留已登记项、不虚构剩余项；队列零枚举取消不发布数据集。Dataset revision 冲突保留资产与原错误报告，现有成员编辑可手动追加，且恢复项保留源相对路径。 |
| S2-AT-07 FITS | 通过。测试覆盖 Mono、明确 RGB、Header CFA 与人工 CFA 的 Bayer、BSCALE／BZERO 缩放、无效像素、首个支持 HDU 固定选择及失败不回退；缩略／详情生成不修改原件。 |
| S2-AT-08 预览与表格 | 通过。测试断言 100／1024 px 上限、不放大小图、固定 `auto-stretch-1` 预设。ComfyUI 实际界面显示缩略图、1024 px 浮层、数据集参数“混合”和“部分缺失”。 |
| S2-AT-09 升级及备份 | 通过。由 `0001_foundation` 升级到 `0002_asset_ingestion`，既有项目、设备、资产、版本与项目引用保留；迁移前备份仍是 `0001_foundation` 一致快照。未知 revision 失败测试保留数据库与备份。 |
| S2-AT-10 API、代理及停止范围 | 通过。运行时 OpenAPI 快照与服务一致；48 个代理操作均存在于契约。没有 Asset 内容版本写入、文件下载任意路径、扫描、处理或阶段三 API。 |
| S2-AT-11 ComfyUI 自动启动与服务健康 | 通过。确认资产队列为空后，重启现有 ComfyUI 8188 宿主；宿主从 `feature/database` 扩展路径加载，`uv` 不在 ComfyUI 的 `PATH` 中但扩展从 `~/.local/bin/uv` 启动锁定服务。启动日志记录服务健康检查 HTTP 200。同源代理的 `/capabilities` 和 `/library/assets` 均返回 HTTP 200；空产品库返回 0 条素材。数据库启动前由 `0001_foundation` 经显式升级到 `0002_asset_ingestion`，一致备份保存在 `/home/maojiexu/.local/share/astrophotoflow/backups/`。服务管理器定向测试 6 项通过，覆盖 PATH 与用户 uv 路径、健康服务复用、受管进程停止、一次重启、重启后退出及连续健康检查失败。 |

主要后端行为测试在 `service/tests/test_service.py`、`service/tests/test_ingestion.py`、`service/tests/test_fits_preview.py` 与 `service/tests/test_proxy.py`；前端测试位于 `frontend/src/workspace/`。

## ComfyUI 集成验证

在现有 ComfyUI extension 链接指向的 `feature/database` worktree 中构建并验证。ComfyUI 版本为 0.42.0，前端包 1.57.1，Python 3.12.13。现有 8188 端口宿主与其用户配置／资产库保持未修改；端到端验证另启临时 HOME 下的 ComfyUI 8191、资产服务 8190、数据库和素材目录，测试后关闭并移除临时目录。

实际界面验证了：

- AstroPhotoFlow Section 从 ComfyUI 侧栏打开，空库、素材根目录浏览和导入表单正常。
- 导入一个 FITS 后任务显示 `completed`，内容、元数据、预览均为 `available`；资产表显示 FITS Header 解析的 Gain／曝光，并允许人工输入零 Gain、零曝光、负温度。
- 点击缩略图在宿主内打开 FITS 预览浮层；关闭后回到资产表。
- 直接编辑为 Master Dark 后，role 派生为校准素材，`calibration_level=master`，revision 增加且内容版本 ID 保持不变。
- 导入含一个 FITS 的目录生成固定成员数据集；成员增补后数据集表显示混合分类、Gain／曝光和部分缺失温度。
- 创建临时项目并选用明确的资产版本；项目资产页显示“固定版本 v1”并展示最新资产资料。
- 在画布内点击可见资产名称不会选择或修改底层工作流节点。

集成运行过程中发现并修复了资产行与数据集行判别、详情预览路径、项目引用 UI 和画布事件隔离问题；本记录反映修复后的最终验证结果。

## 最终验证命令

```bash
cd /mnt/c/Users/Administrator/.codex/worktrees/database-foundation/ComfyUI-AstroPhotoFlow
uv run --locked --project service --extra test pytest service/tests -q
cd frontend
pnpm typecheck
pnpm test
pnpm build
```

最终结果：后端 **28 passed**；前端 **10 passed**；TypeScript 检查与 Vite 生产构建通过；`git diff --check` 通过。OpenAPI 快照契约测试通过。

测试日志有两条非阻断警告：Starlette 提示未来可用 `httpx2` 替换测试传输；Alembic 的 `compare_metadata` 提示 Asset／AssetVersion 与 Dataset／DatasetVersion 的循环外键排序。迁移元数据比较结果为空，测试通过；这两条警告未被隐藏。

## 停止线与 Git 状态

第二阶段 S2-AT-01 至 S2-AT-11 范围及验收完成。第三阶段拖入画布、非 FITS 解析／预览、视频逐帧、NumPy 切片、目录监听／重扫、校准匹配、软件 Node、MCP、AI Panel 和 Agent 均未实现。

改动保留在 `feature/database` worktree，当前未创建提交、未推送、未建 PR，也未合并 `dev`。只有按计划报告前两阶段及必要集成回归合并就绪；实际合并等待用户明确指令。

## 2026-10-23 补充 UI 与导入回归

对当前 `feature/database` 工作区做第二轮逐项核对后，补齐了几处原验收未覆盖的缺陷：

- 双击编辑的下拉框改用原始字段值匹配选项，混合数据集 Bin 也能正确显示“混合”并批量修改；导入对话框每次打开都会清空上一次资料草稿。
- 筛选浮窗需在标题栏静止按住 350ms 才能开始拖动；拖动前移动会取消本次拖动。
- 根目录导入允许省略分类；相机 CFA 参数使用同一登记枚举；用户明确选择的 CFA 优先于冲突的 FITS Header。
- 视频首帧预览在素材库与项目引用两种读取路径中都使用 HDU 0，避免已生成封面仍返回 404。SER 集成测试覆盖双档 JPEG、原件不变、坏帧保留入库内容及回填继续处理。

本轮未增加 v1／v2 旧资料兼容层。定向验证结果：前端 **37 passed**、后端 **48 passed**；TypeScript 检查、Vite 构建、OpenAPI 快照一致性及 `git diff --check` 通过。未重跑完整历史验收套件。

## 2026-10-23 前端 P2 回归修复

- 原位保存期间分页、筛选或排序触发的列表读取会排队；最后一个保存成功后读取最新查询条件。保存失败保留草稿与错误，并在用户重试成功或清除失败状态后处理待查询。
- 预览请求以请求序号校验有效性。关闭或卸载后返回的请求不再打开浮层或写入错误状态；过期对象 URL 会释放。
- 本轮定向前端测试 **27 passed**（`Workspace.regression.test.ts`、`Workspace.test.ts`）；`pnpm typecheck`、`pnpm build` 及 `git diff --check` 通过。未重跑后端测试或完整历史验收。
- Windows 桌面人工验收仍待完成。旧技术文档所述“数据集发布 revision 冲突后手动补入”与新行内进度的需求对齐仍待确认。

## 2026-10-23 合并前最终检查

用户在本聊天明确确认手动测试通过，并授权修复剩余搜索问题后，按 `feature/database → dev → main` 的两个 PR 顺序合并。

本轮修复保存已失败时再搜索的恢复路径：查询保持待处理，失败期间不卸载编辑草稿、不持续显示加载；取消编辑或重试保存成功后读取最新搜索条件。新增两个回归用例，先复现失败，再验证两种恢复操作。

最终本地结果：前端 **74 passed / 12 files**；后端 **92 passed**；TypeScript 检查、Vite 生产构建及 `git diff --check` 通过。后端仍有上文记录的两条非阻断警告。仓库现有 CI 工作流已注释，本记录不代表 GitHub CI 通过。

实际执行命令（Windows Node 运行在 C 盘 worktree，后端使用 WSL uv）：

```bash
uv run --locked --no-sync --project service --extra test pytest service/tests -q
cd frontend
# task_node=/mnt/c/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe
"$task_node" node_modules/vitest/vitest.mjs run
"$task_node" node_modules/vue-tsc/bin/vue-tsc.js --noEmit
"$task_node" node_modules/vite/bin/vite.js build
```

本次交付包含资产导入、资料编辑、数据集、筛选、FITS／视频预览及迁移 0002–0005。上面的初次验收、旧测试数量和“等待手动验收／合并授权”描述是历史记录，以本节当前状态为准。旧 S2-AT-06 对“revision 冲突后手动补入”的 UI 结论不作为当前界面验收：新行内进度尚未提供完整错误报告与手动补入恢复流程，需求对齐继续待定。

数据库迁移有持久化副作用；如需回滚，必须先停止写入并使用迁移前一致备份恢复数据库，不能仅回退代码。当前用于人工测试的是隔离预览库，原 Siril 数据库未降级、未覆盖。本次合并不新增生产部署或数据库迁移操作。
