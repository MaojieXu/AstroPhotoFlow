# 导入流水线

[English](import-pipeline.en.md) | 中文

把本机文件或上传内容登记为素材、托管原件并生成预览。实现归 data 模块的导入流水线（`src/astrophotoflow/modules/data/imports/`），模块职责与数据归属见[架构](../architecture.md)。

## 职责

- 受理一次导入，固定文件清单与来源观察，创建素材与逻辑数据集。
- 托管原件：对 managed 来源复制并散列，对上传文件散列后原子归位。
- 写入文件头元数据、分类、设备与校准快照，并在原件可用后生成预览。
- 以任务报告各阶段进度，支持取消、恢复、重试与只补发布。

## 输入

- 网页提交的绝对文件清单；文件夹只取当前层支持格式，不提交递归目录。
- 带 `root_id` 的相对路径清单，以及上传接口的暂存文件。
- 可选的分类、参数、目标数据集与组级校准输入。数据集发布只纳入子帧素材，回执列出已入库但未入组的文件。

## 阶段与状态

登记只读取 FITS/XISF 头并建立身份，不散列、复制或解码图像。待处理素材 `availability=unknown`、`content_status=pending`，原件完整散列并归位后才可用；登记、内容、元数据与预览分别记录状态，任务在所有阶段结束后才进入终态。

- managed 来源在一次读取中散列并复制到暂存文件，再原子归位到已分配的可读素材目录，路径规则见[素材库](library.md)。
- 上传文件已暂存，后台散列后原子移入同一托管目录体系。
- 外部来源保留登记时的 size 与 mtime；读取前后变化返回 `SOURCE_CHANGED` 并发布为 changed，不发布部分副本。
- 取消清除未发布的部分复制；恢复与重试复用原素材身份，不重新登记。

## 报告与失败

任务报告分 `report.registration`、`report.content` 与 `report.preview` 三段；`bytes_copied` 只表示已复制字节，不等于已校验可用字节，登记 100% 也不表示整批结束。

- 元数据失败计入 `metadata_failed`，不影响已发布原件的可用性。
- 导入任务共享服务级文件线程池与优先级预览执行器，退出时排空；任务等自己的内容与预览结束才进入终态。
- 预览失败不影响科学原件；同一 Object 的兼容 subframe 按固定顺序共享参考帧配方，masterframe 独立计算。

- 导入方式明确选择独立素材、新建子帧数据集或追加已有数据集。文件数量和文件夹选择只决定输入范围。
- 可选项目身份及 revision 在受理时固定，原件与数据集发布后单独结算项目关联。项目冲突保留入库结果，并在任务中报告失败。
- 发布或关联失败可从原任务的成功素材重新建组、追加或重关联项目。修复使用当前 revision 与幂等回执，结果未知先查询，原件保留。

## 分类与快照

分类只按明确文件头，不按文件名猜测。参数优先级为人工非空值、文件观察、受理时冻结的预设、未知，0 是有效值。受理时冻结组合、预设与设备资料，重试与恢复沿用原快照；后台不重写人工资料。

## 对外契约

- HTTP 路由在 `src/astrophotoflow/interfaces/http/data/imports.py`、`inspection.py` 与 `previews.py`。
- 任务、报告与错误码在 `src/astrophotoflow/contracts/imports.py`，字段以 [OpenAPI 快照](../api/openapi.json) 为准。
- 网页、CLI 与 MCP 使用同一批路由；CLI 与 MCP 的调用约定见[参考](../references.md)。

## 测试

`tests/modules/data/test_import_pipeline.py`、`test_ingestion.py`、`test_equipment_snapshots.py`。
