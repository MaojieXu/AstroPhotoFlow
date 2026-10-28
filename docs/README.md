# 文档索引

当前说明、目标路线和验证证据分别维护。目录存在、接口返回成功或历史测试通过，不代表完整产品目标已交付。

| 用途 | 入口 |
|---|---|
| 开始任务 | [Agent 开发约定](../AGENTS.md)、[当前开发上下文](development/current-context.md) |
| 总体架构与源码归属 | [总体架构与模块边界](architecture/overview.md)、[五模块源码与验证导航](architecture/module-map.md)、[文件架构](architecture/repository-layout.md) |
| 模块概要设计 | [①公共](../src/astrophotoflow/core/README.md)、[②数据](../src/astrophotoflow/modules/data/README.md)、[③软件](../src/astrophotoflow/modules/software/README.md)、[④节点](../src/astrophotoflow/modules/nodes/README.md)、[⑤工作流／执行／Agent交互](../src/astrophotoflow/modules/workflows/README.md)；概要不等于实现 |
| 数据设计 | [共同入口](architecture/data-models/README.md)及五份模块文档；固定素材、软件包、可编辑节点、唯一原生图／运行／多次预览和当前控制；未定schema或接口 |
| 使用场景 | [现行需求详细场景](requirements/README.md#scenario-import)：双入口导入、选材／拖入画布、深空／原始行星视频／叠加后期、软件操作／Python／复合节点创作；安静接续须真实客户端验证，Python仍S6，均不代表新增实现完成 |
| 产品目标与开发顺序 | [现行产品需求与范围](requirements/README.md)、[五模块开发路线](development/platform-roadmap.md) |
| 近期实施与分支验收 | [第⑤阶段近期实施计划](development/implementation-plan.md)：M1～M6、22个Batch／建议分支，六份任务卡落实文件／函数／顺序／测试与人工操作，区分技术集成和用户批准；计划本身不代表实现，M1已有候选，状态见[验证矩阵](development/test-matrix.md#m1-foundation) |
| 开发、运行与发行 | [开发流程](development/README.md)、[工作台使用](development/workbench.md) |
| 数据行为 | [素材与存储](architecture/assets.md)、[导入流水线](development/import-pipeline.md)、[预览](development/library-preview.md) |
| 项目、设备与校准 | [使用组合与预设](development/settings-organization.md)、[设置与回收站](development/settings-management.md)、[校准关联](development/calibration-library.md) |
| HTTP、CLI 与 MCP | [现有接口说明](api/README.md)、[OpenAPI 快照](api/openapi.json)、[Agent 操作参考](development/library-agent-tools.md)；[五模块接口与文件级详细设计](api/platform-contracts.md)维护未来操作、精确签名、文件／调用责任、测试与原型门槛 |
| 软件包与按需工具发现目标 | [③软件概要](../src/astrophotoflow/modules/software/README.md)、[统一检索需求](requirements/README.md#tool-discovery)；固定版本、双入口目录及最多10候选均待实现／验证，不是现有安装或接口说明 |
| 节点制作与更新目标 | [④节点概要](../src/astrophotoflow/modules/nodes/README.md)、[④数据设计](architecture/data-models/04-nodes.md)、[前端分工](../frontend/packages/astrophotoflow-ui/src/modules/nodes/README.md)；workspace统一节点库、可选测试、确认更新及变化端口处理均待实现，Python／复合S6，导出另行规划 |
| 工作流、执行与Agent目标 | [⑤概要](../src/astrophotoflow/modules/workflows/README.md)、[数据设计](architecture/data-models/05-workflows.md)、[前端分工](../frontend/packages/astrophotoflow-ui/src/modules/workflows/README.md)；复用原生，重要方案另存，各执行图像节点自动预览，在线画布控制与必要记录待实现 |
| 覆盖与实际证据 | [需求、实现与验证矩阵](development/test-matrix.md) |
| 历史附件 | [归档索引](archive/README.md) |

现行需求统一维护产品目标、范围与验收条件，总架构是权威状态、调用边界与关键链路的唯一入口，路线维护开发阶段、依赖和联调出口。模块概要维护所属能力、流程、交接及验收，模块导航定位源码及验证，文件架构维护目录和导入规则。运行实现和模型是接口事实源；OpenAPI 是生成快照，前端 Zod 随相关契约维护。数据结构初稿维护对象与关系，素材说明保留当前行为；未来接口契约集中维护必要输入输出及失败规则，不复制进现有快照。功能说明保存当前行为，当前上下文保存有效待办，测试矩阵保存有候选和范围的验收结论。旧计划和重复过程记录不重新作为执行指令。
