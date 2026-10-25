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

开发及31388展示实例的schema均为 `0007_setups_and_calibration`。MCP为58工具，保留原五工具；已用原全局注册命令验证新会话，全局注册未改，既有客户端连接可能需重连刷新工具清单。素材行为见[架构说明](../architecture/assets.md)，CLI/MCP 见[接口说明](../api/README.md)。新功能按[五分支约定](module-improvements.md)推进；完整 Agent、软件适配、工作流和结果比较仍未实现。

原工程重构验收见[历史记录](remake-acceptance.md)，本轮配置和运行收尾的实际证据见[配置管理验收](config-management-acceptance.md)。不自动合并 dev/main 或推送远端，不进行前端自动点击。

最新预览修复：PixInsight 无 CTYPE3 的三平面 FITS 识别已补齐，已有库无需重导入即可回填预览；资产、版本、分组和人工参数保持。验证见 [PixInsight 预览修复](pixinsight-preview-fix.md)。

## 当前 Goal 开发进度

五分支共同基础为 `3f72b71`，均包含a5c6381。五分支功能已本地合入feature/remake：分阶段导入、实测FITS优化、
组合/预设、独立校准库及固定版本关系、按需大图、结构化CLI/MCP和项目Skill。代码复查三轮收敛；
随后运行验收纠正了历史任务标记阻挡可用缓存及创建校准组的迟到导航。最终运行实现为11a267f，
后续交付文档不改变运行代码。验收、跳过项和实际散列见[矩阵](module-improvements-acceptance.md)，
手动入口见[检查清单](module-improvements-manual-check.md)。

31388/31390使用原workspace并已升级0007，原38张照片/参数/版本/成员/旧缩略图保持；未全量重导入。
插件在workspace/comfyui-data中隔离，JS/CSS提供内容与build一致；原全局MCP命令能发现58工具及相同图片。
默认workspace指针和全局MCP配置未变。双实例隔离测试环境已停止，当前仅保留主展示实例运行。
