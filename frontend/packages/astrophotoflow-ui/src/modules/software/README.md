# ③ 外部软件接入与环境：前端分工

[③概要](../../../../../../src/astrophotoflow/modules/software/README.md)是行为入口。2026-10-29 SoftwarePanel 候选只常驻软件名、红绿就绪点及安装／卸载；原因通过状态点查看，具体版本、来源、安装位置和保留说明在原生 Dialog 确认。宿主注入原生 Button／Dialog，UI 包不导入原生源码；同一 WebSocket 回调确认，轮询展示实际结果。命令目录保留在 API，不再占据软件页。测试文件已补齐但不运行，类型／构建通过，真实安装及卸载由用户验收。

- 展示项目维护的软件列表、安装版本、可用状态和安装／更新／卸载入口。用户也可让 Agent 通过平台 MCP 操作。
- 安装后展示配套节点；未登录或许可缺失时仍展示节点及原因，引导用户在软件或平台界面自行输入敏感信息。
- 更新前展示受影响工作流及参数变化并请求确认；处理运行中不允许更新。缺失或卸载的节点保留在画布并提示。
- ④提供节点定义，⑤统一管理当前图、实际运行及Agent发现和交互；UI不自行推断任务已完成或保存另一份业务权威。

通过[私有UI包公开入口](../../index.ts)与[宿主桥接](../../../../../src/platform/astrophotoflow)接入原生应用；软件确认从当前ComfyUI WebSocket发送，不另建连接。测试位于`tests/modules/software/SoftwarePanel.test.ts`。软件包规则见[软件包ADR](../../../../../docs/adr/WORKBENCH-SOFTWARE-0056-bundled-software-nodes.md)。
