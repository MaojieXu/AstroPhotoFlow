# software 模块

拥有固定软件包、安装与就绪状态、实际调用观察；不拥有节点定义、图、队列或已检查结果。

## 公开入口

`public.py` 显式导出共享能力：包目录与版本、安装/卸载/维护、操作参数校验与调用、调用记录与取消、预览定义、开发构建与 Bundle 观察；跨模块只经 `public.py`，HTTP 适配在 `interfaces/http/software.py`。

## 内部结构

`packages/` 维护包与安装状态，`execution/` 执行具体调用并记录进程与结果，`bundles/` 加载独立 Bundle，`development/` 提供开发构建与内容指纹，`releases.py` 发现发行标签，`environment.py` 构造 Bundle 子进程环境。

## 边界

Siril 等软件来自独立私有 Bundle 仓库，平台持有 SDK、Bundle 加载与发布目录快照；节点定义归 nodes，图、队列、执行历史归 ComfyUI，已检查结果归 data，跨模块装配归 `interfaces/application`。进程退出不等于节点结果就绪，未知结果先查询、不自动重放。

## Bundle 契约

SDK 仅 v2，声明具名图像、序列与文件输入、多输出与分析文件；预览端口由操作的 `preview.input`/`preview.output` 声明，无 `output` 时仅唯一 FITS 图像输出可确定端口；`automatic_result_preview`（缺省 false）允许节点成为自动结果计算目标。

## 不变量

安装状态原子替换在 Windows `WinError 5` 时按上限重试；进度写入失败只记日志并保留上次进度；主进程正常退出后最多观察已知进程树 5 秒，仍活动或无法核实保留 unknown、不重跑。

## 测试

`tests/modules/software/`；Bundle 夹具在 `tests/fixtures/bundles/`；平台单元测试用合成 Bundle，真实 Siril 在 `tests/integration/` 运行。Bundle 行为见[软件子系统](../../../../docs/subsystems/software.md)。
