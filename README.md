# AstroPhotoFlow

基于 ComfyUI 的本地天文图像工作台。用户在网页中导入素材、连接节点、调用外部软件并查看结果，也可让外部 Agent 通过平台 MCP 操作同一工作台。

已有素材、固定版本、设备与校准管理，以及 Siril Auto Stretch 的 Bundle 接入和在线画布局部操作。完整的项目工作流关联、跨重启运行记录和结果比较仍需补齐；集成与验证状态见 [当前上下文](docs/development/current-context.md)。Windows 优先，Linux／WSL 尚未验收。

- 想了解要做成什么：读 [产品需求](docs/requirements/README.md)。
- 想开发：读 [Agent 约定](AGENTS.md)、[当前任务](docs/development/implementation-plan.md) 和 [开发命令](docs/development/README.md)。
- 想安装或使用：读 [工作台使用](docs/development/workbench.md)。
- 想找具体资料：从 [文档入口](docs/README.md) 按需进入。

平台不内置 Agent 或聊天；现有数据工具继续保留。当前只有开发构建，正式发布另行批准。
