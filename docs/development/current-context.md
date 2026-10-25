# 当前开发上下文

更新时间：2026-10-25。当前分支 feature/remake，工程标准化基线为 `4cc317d`，本轮完成运行配置统一和历史目录收尾。

## 唯一开发入口

- 项目 Python：`.artifacts/venvs/dev`，依赖沿用根 uv.lock。
- 本机变量：根 `.env`，模板 `.env.example`；由 uv 显式加载。
- 当前 workspace：`.artifacts/workspaces/dev`，创建时使用新数据库，现保留用户手动导入的数据；配置为该目录的 config.toml。
- 前端／服务：`http://127.0.0.1:31388/` 和 `127.0.0.1:31390`。
- CPU runtime：复用正常用户 LocalAppData 下的 AstroPhotoFlow/runtime/0.1.0，不再依赖旧 test/ 中的解释器或 ComfyUI 源码。
- MCP：开发环境 uv 加载项目 `.env` 后运行 `apf mcp`；其他 Codex/MCP 设置保持不变。

`astrophotoflow.config` 是共享配置事实源；后端、代理、CLI、MCP 和工作台不再各自解析 TOML。显式路径优先，其次环境中的配置位置，再其次当前 workspace 指针及默认位置；无效选定配置明确失败。服务令牌保持 workspace 内文件机制。

旧服务、编辑器格式化器和历史工作台已解除对 service/、test/ 的依赖。本机 VS Code 默认 Python 解释器、Black、Pylint 已配置为统一开发解释器。历史数据库不迁移，原图／ZIP及参考项目保留，独立 RAW/HEIF 样本和出处移入 tests/data/reference-samples。

## 产品边界

开发代码 schema 已进入 `0007_setups_and_calibration`，运行中的旧展示实例尚未统一更新；MCP 当前仍为五工具。素材行为见[架构说明](../architecture/assets.md)，CLI/MCP 见[接口说明](../api/README.md)。新功能按[五分支约定](module-improvements.md)推进；完整 Agent、软件适配、工作流和结果比较仍未实现。

原工程重构验收见[历史记录](remake-acceptance.md)，本轮配置和运行收尾的实际证据见[配置管理验收](config-management-acceptance.md)。不自动合并 dev/main 或推送远端，不进行前端自动点击。

最新预览修复：PixInsight 无 CTYPE3 的三平面 FITS 识别已补齐，已有库无需重导入即可回填预览；资产、版本、分组和人工参数保持。验证见 [PixInsight 预览修复](pixinsight-preview-fix.md)。

## 当前 Goal 开发进度

五分支共同基础为 `3f72b71`。设置组织和异步导入首版已经本地合入 feature/remake，
两分支集成候选为 `9a0706e`（集成后 Python 30、前端 119 项通过）。校准库继续在独立
worktree 开发；导入分支正在补充分阶段性能和 XISF 元数据观察。1080 px 预览及工具/Skill
分支尚未交付，不能宣称整个 Goal 完成。实际证据和剩余验收见[矩阵](module-improvements-acceptance.md)。

原 31388 展示进程尚未替换为本轮候选。工作区插件隔离已通过两套真实 CPU 实例验证，
测试实例已退出，无受管子进程残留，四个端口均释放。全局 MCP 注册与默认 workspace 指针未改变。
