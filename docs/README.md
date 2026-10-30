# 从这里找文档

日常只需看“产品要做什么、现在到哪、下一步做什么”。代码细节在需要修改时再读。

| 你想知道什么 | 入口 |
|---|---|
| 产品目标、不能破坏的用户规则 | [产品需求](requirements/README.md) |
| 已实现什么、还有哪些缺口 | [当前上下文](development/current-context.md) |
| 下一项工作及如何验收 | [当前计划](development/implementation-plan.md) |
| 模块怎么分工、数据存哪 | [架构](architecture/overview.md) |
| 某个功能的代码在哪 | [源码导航](architecture/module-map.md) |
| 重要方案为什么这样选 | [ADR](decisions/README.md) |
| 如何安装、启动或开发 | [使用说明](development/workbench.md)、[开发命令](development/README.md) |
| 接口、命令和工具怎么查 | [API入口](api/README.md) |
| 某项检查真的做过吗 | [验证记录](development/test-matrix.md)，只按具体条目查 |

## 只有相关任务才读

- 数据行为：[素材与存储](architecture/assets.md)、[导入](development/import-pipeline.md)、[查看与预览](development/library-preview.md)。
- 设备和校准：[设备及预设](development/settings-organization.md)、[管理与删除](development/settings-management.md)、[校准关联](development/calibration-library.md)。
- 模块 README 只提供本模块代码入口与约束；局部 AGENTS.md 补充修改规则。
- [历史资料](archive/README.md) 包含旧22 Batch及设计草案；不作为当前执行计划。

需求由人决定，接口由代码生成，验证记录说明证据。ADR不替代产品目标、任务或运行说明。维护方法及参考来源见 [ADR-0001](decisions/0001-minimal-documentation.md)。
