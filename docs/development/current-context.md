# 当前开发上下文

更新时间：2026-10-25。当前工作为 `feature/remake` 工程标准化，继承 `material-setting-improvement` 的 `d40d6c496cbc16e29bd0d54f3cc1afaeabc5d3ef`。

基线已通过用户手动检查并推送；R4、父子恢复、过期清理请求、分页响应和回收站布局修复已经包含在内，不重新打开其产品设计。

当前行为见[素材说明](../architecture/assets.md)，外部接口见[接口说明](../api/README.md)。schema 保持 `0006_library_trash_cleanup_state`，MCP 保持五工具。完整工作流／Agent／软件适配、增强数据库及结果比较未实现，不属于本次标准化。

迁移前产品测试清单见 [refactor-baseline.json](refactor-baseline.json)。已有证据：垃圾桶及相关后端 32 项通过、外部 reference 原图保护定向补验通过；最后一次 UI 增量的回收站组件 7 项通过、类型检查与构建通过。旧的 110 项前端记录属于此前候选，不替代重构后的完整验收。

原图、ZIP、旧虚拟环境与已有展示 workspace 不搬动；新运行产物统一 `.artifacts/`。当前展示地址沿用 `http://127.0.0.1:31388/`，通过 HTTP 和实际资源核对后交给用户手动点击，不运行 computer use。

本次重构已完成本机自动验收和独立只读复审：Python 129 通过／1 跳过，前端 111 通过，wheel／sdist 安装验证通过；实际结果见[验收记录](remake-acceptance.md)。31388 已提供重构后的资源，交互由用户手动检查。本分支不自动合并到 dev/main，不更改全局 MCP 注册或默认 workspace。
