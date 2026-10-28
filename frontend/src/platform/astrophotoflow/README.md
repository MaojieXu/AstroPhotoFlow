# AstroPhotoFlow 原生应用桥接

NativeShell 保留原生 GraphView；LibrarySidebarTab 挂载私有 UI 包并提供侧栏关闭保护；useLibrarySidebarTab 注册现有素材库标签。WorkbenchSidebarTab 用同一原生侧栏模板挂载工作台配置，useWorkbenchSidebarTab 注册标签。应用只通过 index.ts 使用这些集成入口。

本区域可以依赖原生应用的 Store 和组件，但只通过 @astrophotoflow/ui 包公开入口使用业务界面。业务实现不得反向依赖这里。

保持节点库 → 素材库 → 工作流 → 工作台配置顺序、原生分栏、设备按钮位置及草稿保护。未来画布同步协议需要单独实现，不能由现有挂载代码推断已支持 Agent 编辑。

验证：原生 GraphView、侧栏状态测试和隔离浏览器验收。
