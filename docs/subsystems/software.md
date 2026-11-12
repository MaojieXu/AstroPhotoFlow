# 外部软件

[English](software.en.md) | 中文

固定软件包、安装与就绪、实际调用与停止观察归 software 模块；独立 Bundle 的源码与适配器由私有仓库维护。模块职责见[架构](../architecture.md)，产品规则见[软件产品需求](../product/software.md)。

## 职责

- 维护发布目录快照中的软件包、操作与显示资料，并从官方 Git 仓库发现版本。
- 执行用户确认后的安装、切换与卸载计划，记录程序版本、调用与观察。
- 为节点目录与自动结果提供能力与依赖信息。

## Bundle 契约

- 只支持 Bundle SDK v2；输入、输出、命令与评估资料声明在 Bundle，平台不生成空节点。
- 宿主负责固定素材输入、实际进程、取消与输出范围检查；分析 schema 与科学输出交 data 公开能力检查。
- 进程退出不等于节点结果就绪；主进程退出后最多观察已知进程树 5 秒，仍活动或无法核实保留 unknown，不重跑。
- 显式样本接口由操作的 `preview.input` 与 `preview.output` 声明。节点结果使用已检查的运行产物，并按声明的媒体类别、角色和结构化分析选择组件。
- 空间参数绑定所声明的输入端口、成员及原尺寸坐标。节点、结果 HTTP 与 MCP 使用同一组公开契约。
- `automatic_result_preview` 默认 false；启用后该操作可成为自动结果目标与依赖，整条依赖链都须允许自动执行。

## 版本与安装

- 选择令牌绑定官方来源、tag、commit 与 manifest；安装计划与实际 checkout 都核对固定目标，语言与 latest 标记不参与令牌。
- 版本查询失败独立报告并保留上次成功列表；历史实验 tag 与未发布 tag 不进入官方安装列表。
- 安装状态原子替换；最终状态写入失败必须报告为安装结果未保存、需要核对。
- Bundle Python 按独立包命名空间加载，内容指纹变化使自有模块树失效，并从源码编译。

## 输入与输出

- 输入：软件包与操作标识、参数、素材或数据集引用、开发绑定目录。
- 输出：调用记录、过程观察、输出成员与实际文件；取消受理、已观察停止与未知结果是不同状态。
- 平台从开发或安装后的 Bundle 以及发布目录快照读取声明，平台单元测试使用合成 Bundle。
- 操作定义记录校准状态语义。Siril 1.4.4 的 Auto Stretch 明确保留状态，calibrate／calibrate_single 依据实际输入及 bias 模式记录已用 Master。成功回执与完整输出检查后登记状态，处理语义缺失时采用 Unknown，结果事实经 data 公开入口保存。

## 失败方式

- 程序或环境缺失时报告未就绪原因，不猜测可用。
- 观察不到进程停止时保留 unknown 并要求查询，不自动重放。
- 无头 Siril 由 Bundle 禁用 D-Bus 自动会话，避免通信辅助进程延续调用生命周期。原生页面区分运行失败、状态未知与软件占用阻止，后两者要求先核查原调用。
- 读取图像主输入时，若 Windows 路径超过 Siril 的限制，Bundle 在本次调用目录准备短文件名副本；原输入与来源记录保留。
- 预览样本可见不等于完整结果可用，正式运行继续使用完整科学输入。

## 对外契约

- HTTP 路由在 `src/astrophotoflow/interfaces/http/software.py`、`software_calls.py` 与 `software_previews.py`。
- 契约在 `src/astrophotoflow/contracts/software.py` 与 `bundles.py`，字段以 [OpenAPI 快照](../api/openapi.json) 为准。
- 公开入口是 `src/astrophotoflow/modules/software/public.py`；跨模块装配在 `src/astrophotoflow/interfaces/application/`。

## 测试与边界

- 测试在 `tests/modules/software/`。
- 节点定义归 nodes；图、队列与执行历史归 ComfyUI；已检查结果归 data。
