# 文档索引

当前说明、目标路线和验证证据分别维护。目录存在、接口返回成功或历史测试通过，不代表完整产品目标已交付。

| 用途 | 入口 |
|---|---|
| 开始任务 | [Agent 开发约定](../AGENTS.md)、[当前开发上下文](development/current-context.md) |
| 当前架构与源码归属 | [模块与数据流](architecture/overview.md)、[七模块导航](architecture/module-map.md)、[文件架构](architecture/repository-layout.md) |
| 产品目标与开发顺序 | [七模块开发路线](development/platform-roadmap.md)、[冻结需求基线](requirements/README.md) |
| 开发、运行与发行 | [开发流程](development/README.md)、[工作台使用](development/workbench.md) |
| 数据行为 | [素材与存储](architecture/assets.md)、[导入流水线](development/import-pipeline.md)、[预览](development/library-preview.md) |
| 项目、设备与校准 | [使用组合与预设](development/settings-organization.md)、[设置与回收站](development/settings-management.md)、[校准关联](development/calibration-library.md) |
| HTTP、CLI 与 MCP | [接口说明](api/README.md)、[OpenAPI 快照](api/openapi.json)、[Agent 操作参考](development/library-agent-tools.md) |
| 覆盖与实际证据 | [需求、实现与验证矩阵](development/test-matrix.md) |
| 历史附件 | [归档索引](archive/README.md) |

运行实现和模型是接口事实源；OpenAPI 是生成快照，前端 Zod 随相关契约维护。功能说明保存当前行为，当前上下文保存有效待办，测试矩阵保存有候选和范围的验收结论。旧计划和重复过程记录通过 Git 历史查询，不重新作为执行指令。
