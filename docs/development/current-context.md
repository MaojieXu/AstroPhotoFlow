# 当前开发上下文

更新时间：2026-10-25。本轮开发分支 feature/remake，按用户指令交付至 dev；工程标准化基线为 `4cc317d`，本轮完成最终 bug 修复、设备资料解耦及旧 CaptureProfile 移除。

## 唯一开发入口

- 项目 Python：`.artifacts/venvs/dev`，依赖沿用根 uv.lock。
- 本机变量：根 `.env`，模板 `.env.example`；由 uv 显式加载。
- 当前 workspace：`.artifacts/workspaces/dev`，本轮按用户授权清空测试数据并重建为空库；配置为该目录的 config.toml。
- 前端／服务：`http://127.0.0.1:31388/` 和 `127.0.0.1:31390`。
- CPU runtime：复用正常用户 LocalAppData 下的 AstroPhotoFlow/runtime/0.1.0，不再依赖旧 test/ 中的解释器或 ComfyUI 源码。
- MCP：开发环境 uv 加载项目 `.env` 后运行 `apf mcp`；其他 Codex/MCP 设置保持不变。

`astrophotoflow.config` 是共享配置事实源；后端、代理、CLI、MCP 和工作台不再各自解析 TOML。显式路径优先，其次环境中的配置位置，再其次当前 workspace 指针及默认位置；无效选定配置明确失败。服务令牌保持 workspace 内文件机制。

旧服务、编辑器格式化器和历史工作台已解除对 service/、test/ 的依赖。本机 VS Code 默认 Python 解释器、Black、Pylint 已配置为统一开发解释器。历史数据库不迁移，原图／ZIP及参考项目保留，独立 RAW/HEIF 样本和出处移入 tests/data/reference-samples。

## 产品边界

开发及31388展示实例的schema现为 `0009_remove_legacy_capture_profiles`。任务接受时冻结全部引用设备资料，重试和恢复沿用原快照；素材当前资料及固定版本分别保存独立设备快照，设备库变化不会改写历史显示。旧 CaptureProfile 接口、项目字段和表已移除。项目、设备、组合和预设使用共通回收站流程。MCP为58工具，保留原五工具；已用原全局注册命令验证新会话，全局注册未改，既有客户端连接可能需重连刷新工具清单。素材行为见[架构说明](../architecture/assets.md)，CLI/MCP 见[接口说明](../api/README.md)。新功能按[五分支约定](module-improvements.md)推进；完整 Agent、软件适配、工作流和结果比较仍未实现。

设置增删改查和设备快照语义见[设置记录管理](settings-management.md)。

原工程重构验收见[历史记录](remake-acceptance.md)，本轮配置和运行收尾的实际证据见[配置管理验收](config-management-acceptance.md)。按用户指令合入并推送 dev；main 不变，不进行前端自动点击。

最新预览修复：PixInsight 无 CTYPE3 的三平面 FITS 识别已补齐，已有库无需重导入即可回填预览；资产、版本、分组和人工参数保持。验证见 [PixInsight 预览修复](pixinsight-preview-fix.md)。

## 当前 Goal 开发进度

五分支共同基础为 `3f72b71`，均包含a5c6381。五分支功能已本地合入feature/remake：分阶段导入、实测FITS优化、
组合/预设、独立校准库及固定版本关系、按需大图、结构化CLI/MCP和项目Skill。代码复查三轮收敛；
随后运行验收纠正了历史任务标记阻挡可用缓存及创建校准组的迟到导航。最终运行实现为11a267f，
后续交付文档不改变运行代码。验收、跳过项和实际散列见[矩阵](module-improvements-acceptance.md)，
手动入口见[检查清单](module-improvements-manual-check.md)。

31388/31390已使用同一 dev workspace 重启，数据库为新建 0009 空库；原测试记录、托管副本、预览、暂存及旧备份已清理，原始素材、ZIP、配置、服务令牌和 CPU runtime 保留。
插件 JS/CSS 的实际 HTTP 内容与本次 build/frontend 完全一致；既有全局 MCP 注册命令仍能发现58工具，CLI、MCP及前端代理均查询同一空库。

本轮实际验收：Windows Python 3.12，270 passed / 1 skipped（FFmpeg unavailable），已有 ORM 循环外键排序警告1条；前端138 passed，类型检查和构建通过。
wheel源码目录外安装及无Node的sdist重建通过；Linux本轮未执行，不视为已通过。未重导入真实数据集、未自动点击前端、开发验收阶段未提交或推送，随后按用户指令交付至 dev。
详细证据见[最终修复验收](final-bugfix-acceptance.md)。
