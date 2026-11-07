# data 模块

拥有素材与集合的固定版本、项目资料、设备与预设快照、校准、原件、预览、导入与回收站，是这些事实的唯一权威。

## 公开入口

`public.py` 显式导出跨模块能力：素材与版本查询、集合发布、导入任务、预览与缩略图、画布数据、结果检查与登记、校准、设备、项目与回收站；跨模块只经 `public.py`，HTTP 路由由 `interfaces/http/data/` 装配。

## 职责边界

- 已检查结果与素材内容归 data；图、队列、执行历史归 ComfyUI；具体软件调用归 software；跨模块装配归 interfaces。
- 来源格式的登记、原件可读、解析与预览分开，预览与查看状态不进入科学输入。
- `formats/` 只处理文件格式，不依赖导入流水线、ORM 或 HTTP；`science/conversion.py` 消费原始像素，像素源不反向依赖科学转换。
- 稳定身份、固定成员顺序与资料 revision 是持久不变量；新运行使用纠正后的资料，旧运行不被改写；FITS 与 SER 保留实际帧数与精度。

## 关键协作

坏点表、ICC、比较星 CSV、WCS 与脚本以稳定文件版本经 `APF_FILE_REFERENCE` 交接；运行输出复用同一查看器与缓存，按所选成员或 HDU 准备；颜色布局由软件契约声明，读取只改内存解释，不覆盖原件。

## 测试

`tests/modules/data/`；样本数据在 `tests/data/`。导入与预览行为见[素材库](../../../../docs/subsystems/library.md)与[导入流水线](../../../../docs/subsystems/import-pipeline.md)。
