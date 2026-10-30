# 重要决定与原因（ADR）

ADR只回答“为什么选这个方案，以及付出什么代价”。一个重要决定一篇短文：日期／状态、问题、选择、后果；无需给普通修复、字段或每个任务建ADR。建议一页内能读完。

| 决定 | 状态 |
|---|---|
| [0001 文档按任务读取、接口由代码生成](0001-minimal-documentation.md) | 已采用，2026-10-29 |

新平台ADR在本目录继续编号。已接受的旧平台ADR保留原位置，不重新抄写；按任务选择，若后续需求覆盖其部分内容，以现行需求和新ADR为准。Accepted表示选择被接受，不代表代码交付。

| 主题 | 既有记录 |
|---|---|
| 工作台基础与实际启动地址 | [0054](../../frontend/docs/adr/WORKBENCH-FOUNDATION-0054-automatic-startup-endpoints.md) |
| 工作台配置与维护控制 | [0062](../../frontend/docs/adr/WORKBENCH-FOUNDATION-0062-configuration-and-lifecycle.md)、[0064](../../frontend/docs/adr/WORKBENCH-FOUNDATION-0064-web-restart-and-native-controls.md) |
| 固定存储与原生连接 | [0060](../../frontend/docs/adr/WORKBENCH-CONTRACTS-0060-minimal-storage-and-native-bridge.md) |
| 首个Siril原生操作 | [0065](../../frontend/docs/adr/WORKBENCH-SOFTWARE-0065-first-siril-native-operation.md) |
| 软件包及配套节点 | [0056](../../frontend/docs/adr/WORKBENCH-SOFTWARE-0056-bundled-software-nodes.md) |
| 共享可编辑节点与确认更新 | [0057](../../frontend/docs/adr/WORKBENCH-NODES-0057-shared-editable-node-definitions.md) |
| 原生工作流／运行／Agent职责 | [0058](../../frontend/docs/adr/WORKBENCH-WORKFLOWS-0058-native-workflow-execution-and-agent-interaction.md) |
| 局部编辑、先保存后运行、明确目标 | [0059](../../frontend/docs/adr/WORKBENCH-WORKFLOWS-0059-native-editing-save-and-agent-target.md) |

撤销决定时保留旧记录并标明被哪篇替代；当前有效规则更新 [需求](../requirements/README.md) 或 [架构](../architecture/overview.md)，避免让Agent遍历历史才能知道怎么做。
