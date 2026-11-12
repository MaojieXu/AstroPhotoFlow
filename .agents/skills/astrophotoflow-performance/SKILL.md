---
name: astrophotoflow-performance
description: 做性能调查或优化时使用：先用现有基准建立可复现基线与测量卡，再单因素修改、用负对照证明改善并保持行为与资源所有权。
---

# 性能调查

## 触发

用户要求“更快”或定位慢路径时；导入流水线、预览与缩略图、库查询、MCP 工具发现或前端渲染出现可感知延迟时。

## 定范围

- 先确认用户可见端点与完成条件、负载范围、资源约束、可接受的细微差异与停止规则。
- 后端阶段耗时与浏览器端到端分开测量；单测耗时不是产品延迟。
- 没有测量前不加缓存、预算或第二套索引；新增机制按根 `AGENTS.md` 需要依据。

## 基线

- 复用现有基准：`scripts/benchmark_library.py --output <path>`、`scripts/benchmark_mcp_tools.py --output <path>`、`tests/benchmarks/import_pipeline.py --trials/--files/--output`。
- 输出放 `.artifacts`；固定 revision、平台、输入维度与构造参数，记录命令与原始样本。
- 冷热场景分开：冷样本用新子进程与私有临时根，热样本显式保留缓存。

## 测量卡

记录七项：用户操作与完成条件、负载与构造参数、入口路径、时钟起止与排除项、内存口径、判定（原始样本与聚合）、行为证据。缺项不进入修改。

## 定位与改一个因素

- 先证明回归：在未优化实现上跑同一负载并保存结果。
- 一次只改一个因果因素；每轮跑聚焦场景与端到端父场景。
- 常见方向只作假设：重复解析与拷贝、逐项临时对象、无效失效、重复查询、无失效策略的缓存。
- 用 profile、阶段计时、工作计数或分配采样区分假设，不凭代码直觉。

## 行为保持

- 预览与缩略图不是科学输入；未知调用结果不重跑；原子发布、既有校验与所有权不变。
- 不静默截断内容、跳过校验或改变生命周期换数字。
- 运行或补所属行为测试；性能证据不替代功能验证。

## 负对照

- 收紧的断言必须在原实现或受控重引入目标代价时失败。
- 阈值不得低于已验证的噪声；不为通过调低预算或挑选单次结果。

## 记录与回执

- 结论写 Agent Note（`simplification` 或 `testing` 类），记录被拒方案与剩余风险。
- 回执按 `docs/testing.md`，只写实际执行的命令与观察结果。
- 性能参数（worker 数等）保存后不自动重启，下次显式重启生效。

## 入口

- 环境与命令：`docs/development.md`
- 测试与回执：`docs/testing.md`
- 预览缓存：`docs/subsystems/previews.md`
- 导入流水线：`docs/subsystems/import-pipeline.md`
- 基准：`scripts/benchmark_library.py`、`scripts/benchmark_mcp_tools.py`、`tests/benchmarks/`
