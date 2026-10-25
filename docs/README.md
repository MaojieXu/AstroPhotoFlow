# 文档索引

当前说明描述 AstroPhotoFlow 已实现的行为；冻结需求和历史验收不代表本次已完成全部产品目标。

| 分类 | 入口 | 用途 |
|---|---|---|
| 需求 | [需求基线](requirements/README.md) | v1.0 愿景、FR/AT 编号与后续范围 |
| 架构 | [模块与数据流](architecture/overview.md)、[素材行为](architecture/assets.md) | 当前模块职责、存储和用户可见规则 |
| 接口 | [接口说明](api/README.md)、[OpenAPI](api/openapi.json) | HTTP、CLI、五个 MCP 工具及契约维护 |
| 开发 | [开发流程](development/README.md)、[工作台使用](development/workbench.md) | 构建、测试、安装与诊断 |
| 上下文 | [当前状态](development/current-context.md) | 当前工作基线、明确未实现内容和交接边界 |
| 并行开发 | [五分支计划与约定](development/module-improvements.md) | 新功能的共享语义、分工、运行隔离和执行证据 |
| 测试 | [需求与测试矩阵](development/test-matrix.md) | 已有覆盖、已实现能力的缺口、未来验收 |
| 运行收尾 | [配置管理验收](development/config-management-acceptance.md) | 统一环境、配置与旧目录清理证据 |
| 预览修复 | [PixInsight FITS 预览](development/pixinsight-preview-fix.md) | 三平面识别与实际素材回填证据 |
| 历史 | [归档索引](archive/README.md) | 原阶段计划、执行 Prompt、快照与验收证据 |

维护规则：运行实现和模型是接口事实源，OpenAPI 是生成快照，前端 Zod 手工维护并随相关接口测试更新。当前说明使用稳定路径和可执行命令；个人机器路径、旧分支指令和当时的测试结论留在归档中。
