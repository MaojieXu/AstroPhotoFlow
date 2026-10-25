# 当前开发上下文

更新时间：2026-10-25。当前分支 feature/remake，工程标准化基线为 `4cc317d`，本轮完成运行配置统一和历史目录收尾。

## 唯一开发入口

- 项目 Python：`.artifacts/venvs/dev`，依赖沿用根 uv.lock。
- 本机变量：根 `.env`，模板 `.env.example`；由 uv 显式加载。
- 当前 workspace：`.artifacts/workspaces/dev`，使用空的新数据库；配置为该目录的 config.toml。
- 前端／服务：`http://127.0.0.1:31388/` 和 `127.0.0.1:31390`。
- CPU runtime：复用正常用户 LocalAppData 下的 AstroPhotoFlow/runtime/0.1.0，不再依赖旧 test/ 中的解释器或 ComfyUI 源码。
- MCP：开发环境 uv 加载项目 `.env` 后运行 `apf mcp`；其他 Codex/MCP 设置保持不变。

`astrophotoflow.config` 是共享配置事实源；后端、代理、CLI、MCP 和工作台不再各自解析 TOML。显式路径优先，其次环境中的配置位置，再其次当前 workspace 指针及默认位置；无效选定配置明确失败。服务令牌保持 workspace 内文件机制。

旧服务、编辑器格式化器和历史工作台已解除对 service/、test/ 的依赖。本机 VS Code 默认 Python 解释器、Black、Pylint 已配置为统一开发解释器。历史数据库不迁移，原图／ZIP及参考项目保留，独立 RAW/HEIF 样本和出处移入 tests/data/reference-samples。

## 产品边界

schema 仍为 `0006_library_trash_cleanup_state`，MCP 严格为五工具。素材行为见[架构说明](../architecture/assets.md)，CLI/MCP 见[接口说明](../api/README.md)。Agent、软件适配、完整工作流、增强数据库和结果比较仍未实现。

原工程重构验收见[历史记录](remake-acceptance.md)，本轮配置和运行收尾的实际证据见[配置管理验收](config-management-acceptance.md)。不自动合并 dev/main 或推送远端，不进行前端自动点击。
