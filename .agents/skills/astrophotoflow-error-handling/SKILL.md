---
name: astrophotoflow-error-handling
description: 设计或审查失败路径、重试、后台任务与用户可见错误报告时使用：按所属子系统契约定义失败类型、处理与报告归属，保证失败后状态可见且可安全继续。
---

# 失败与重试

## 触发

新增或修改可能失败的操作、取消、后台任务、错误回执、跨进程调用或导入任务时；审查“未知结果”处理与重试逻辑时。

## 失败先定型

- 可预期失败用声明类型与稳定 `code` 表达：`src/astrophotoflow/contracts/common.py` 的 `ErrorDetail`/`ErrorEnvelope`，服务端用 `src/astrophotoflow/core/errors.py` 的 `ApiError`。
- `code` 是机器身份，显示文本单列；不按消息文本路由，不吞异常改写成成功。
- 保留 cause 与处理所需字段；未预期缺陷可以清晰失败，不得被 containment 变成成功。
- 失败契约写在所属子系统的 `docs/subsystems/` 页，本技能不复述具体错误码。

## 归属与安全继续

- 写清每个失败的处理者、报告者、containment，以及失败后的不变量属于缺失、部分、已提交还是未知。
- 只有状态所有者能决定继续；否则停止依赖该状态的工作，丢弃失效实例或交给用户。
- 日志不是恢复；捕获限制传播，不撤销已经发生的修改。

## 未知结果

- 软件调用、画布操作、导入与导出的未知结果先按 `operation_id` 或原生 execution UUID 查询，不盲目重放。
- 取消受理、观察到停止与未知结果是不同事实；查询不到时保留 unknown 并保持可见。
- 写操作需要幂等键或收据；收据记录实际采用的目标与参数。

## 报告

- 用户可见错误经 `src/astrophotoflow/core/localization.py` 的 `localized_error`/`error_message` 按 workspace locale 渲染。
- 报告含可读摘要、受影响操作与安全下一步，不泄露内部细节。
- 未知或不可信状态必须可见且持久；报告失败时要有独立回退路径。

## 重试

- 重试只在可安全重复、可取消且有 owner 时使用。
- 有限操作有预算与上限；持续监督有生命周期与可观察降级。
- 不用重试掩盖未定位的等待或竞态，测试侧规则见 `astrophotoflow-test-reliability`。

## 验证

- 断言最终状态与用户可见结果，不只验证“异常被捕获”。
- 回执记录实际执行的命令与结果，格式见 `docs/testing.md`。

## 入口

- 数据与状态归属：`docs/architecture.md`
- 软件失败方式：`docs/subsystems/software.md`
- 导入报告与失败：`docs/subsystems/import-pipeline.md`
- 启动与控制：`docs/subsystems/workbench.md`
- 回执与验证边界：`docs/testing.md`
