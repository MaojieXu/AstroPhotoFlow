# AstroPhotoFlow 原生应用桥接

NativeShell 保留原生 GraphView；LibrarySidebarTab 挂载私有 UI 包并提供侧栏关闭保护；useLibrarySidebarTab 注册现有素材库标签。WorkbenchSettingsPanel 经UI包公开导出挂载工作台配置，作为原生设置窗口中的独立“工作台”页面；FormItem／Button／Input由宿主传入，保留整组保存与显式重启。settingsPresentation集中控制APF本地设置的分类、搜索及面板定位可见性，不修改底层设置值；原生云版／桌面版保持原有呈现。

本区域可以依赖原生应用的 Store 和组件，但只通过 @astrophotoflow/ui 包公开入口使用业务界面。业务实现不得反向依赖这里。

保持节点库 → 素材库 → 工作流顺序；工作台配置统一从底部设置入口进入，旧工作台侧栏已移除。保留原生分栏、设备按钮位置及草稿保护。未来画布同步协议需要单独实现，不能由现有挂载代码推断已支持 Agent 编辑。

验证：原生 GraphView、侧栏状态测试和隔离浏览器验收。
