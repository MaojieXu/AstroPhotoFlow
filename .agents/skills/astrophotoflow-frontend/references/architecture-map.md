# 前端架构导航

路径以本参考文件所在目录为基准。按任务选入口，再沿当前 imports 核对实际调用链。职责与不变量由 [架构](../../../../docs/architecture.md)和 [前端子系统](../../../../docs/subsystems/frontend.md)维护。

## 启动与导航

| 要找的内容 | 源码入口与下一跳 |
| --- | --- |
| 应用创建、插件和全局样式 | [main.ts](../../../../frontend/src/main.ts)装配 Router、Pinia、Vue Query 与 i18n，挂载 [App.vue](../../../../frontend/src/App.vue) |
| URL 与页面路由 | [router.ts](../../../../frontend/src/router.ts)使用 hash history，根路径与未知路径转到 `/workflows`，该页面使用 NativeShell；进入前初始化用户 Store |
| 本地工作台主界面 | [NativeShell.vue](../../../../frontend/src/platform/astrophotoflow/sidebar/NativeShell.vue)挂载 [GraphView.vue](../../../../frontend/src/views/GraphView.vue)，接入素材显示、结果显示、画布会话和自动结果；`apf_panel=software` 查询参数选择软件侧栏 |
| 侧栏入口、顺序与切换 | [registerCoreSidebarTabs.ts](../../../../frontend/src/composables/sidebarTabs/registerCoreSidebarTabs.ts)注册入口，[sidebarTabStore.ts](../../../../frontend/src/stores/workspace/sidebarTabStore.ts)持有侧栏状态；APF 入口在 [sidebar](../../../../frontend/src/platform/astrophotoflow/sidebar) |
| 素材页面与控件装配 | [LibrarySidebarTab.vue](../../../../frontend/src/platform/astrophotoflow/sidebar/LibrarySidebarTab.vue)构造 controls、连接回执与关闭保护，经公开导出挂载 [Workspace.vue](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/workspace/Workspace.vue)，由 [WorkspacePage.vue](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/workspace/WorkspacePage.vue)组织业务区域 |
| 工作台设置 | [WorkbenchSettingsPanel.vue](../../../../frontend/src/platform/astrophotoflow/settings/WorkbenchSettingsPanel.vue)提供客户端、翻译与原生控件，消费 [WorkbenchSettings.vue](../../../../frontend/packages/astrophotoflow-ui/src/core/WorkbenchSettings.vue)；原生设置从 [settings](../../../../frontend/src/platform/settings)进入 |

侧栏与 Workspace 内部区域的导航从对应注册与状态入口追踪。新增界面先核对这些现有装配点，再判断是否需要修改 Vue Router。

## 责任层与状态

| 任务 | 入口与复用关系 |
| --- | --- |
| 自研包公开能力 | [UI 包 index.ts](../../../../frontend/packages/astrophotoflow-ui/src/index.ts)与 [package.json](../../../../frontend/packages/astrophotoflow-ui/package.json)；宿主消费 `@astrophotoflow/ui` |
| 素材、数据集、设备、校准、导入、结果与回收站 | [data](../../../../frontend/packages/astrophotoflow-ui/src/modules/data)按领域分目录；从 [data README](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/README.md)和 WorkspacePage 的 imports 找具体界面 |
| 节点目录与软件包业务 | [nodes](../../../../frontend/packages/astrophotoflow-ui/src/modules/nodes)、[software](../../../../frontend/packages/astrophotoflow-ui/src/modules/software)；宿主节点控件装配在 APF 的 canvas、results 中 |
| HTTP、错误、workspace 查询身份与配置 | [core README](../../../../frontend/packages/astrophotoflow-ui/src/core/README.md)、[查询客户端](../../../../frontend/packages/astrophotoflow-ui/src/core/query/client.ts)、[身份](../../../../frontend/packages/astrophotoflow-ui/src/core/query/identity.ts)；服务数据沿用 Vue Query，页面草稿沿用对应组件或 Store |
| UI 页面选择状态 | [workspace/store.ts](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/workspace/store.ts)；编辑草稿沿具体业务 composable 追踪 |
| 图、画布与可视节点 | [GraphView.vue](../../../../frontend/src/views/GraphView.vue)、[canvasStore.ts](../../../../frontend/src/renderer/core/canvas/canvasStore.ts)、[renderer](../../../../frontend/src/renderer)、[LiteGraph](../../../../frontend/src/lib/litegraph/src/litegraph.ts)、[appInstance.ts](../../../../frontend/src/scripts/appInstance.ts)；原生生命周期与显示控件在这些入口装配 |
| 工作流文件、标签页和当前图管理 | [workflowStore.ts](../../../../frontend/src/platform/workflow/management/stores/workflowStore.ts)、[workflow](../../../../frontend/src/platform/workflow)；按当前调用者复用保存、草稿、撤销与转换 |
| 队列、执行进度与输出 | [queueStore.ts](../../../../frontend/src/stores/queueStore.ts)、[executionStore.ts](../../../../frontend/src/stores/executionStore.ts)、[nodeOutputStore.ts](../../../../frontend/src/stores/nodeOutputStore.ts)、[api.ts](../../../../frontend/src/scripts/api.ts) |
| APF 图命令、数据引用与拖入 | [canvas/session.ts](../../../../frontend/src/platform/astrophotoflow/canvas/session.ts)、[canvas](../../../../frontend/src/platform/astrophotoflow/canvas)；从 session 的 dataBridge、nodeBridge imports 进入写入实现 |
| APF 运行与结果展示 | [results](../../../../frontend/src/platform/astrophotoflow/results)中的 automatic、bundleDisplay 与 DataRunWidget；业务查询和保存沿 UI 包公开客户端进入 |
| 大图、视频、概览与瓦片查看 | [宿主 media](../../../../frontend/src/platform/astrophotoflow/media)负责交互视口，[业务 media](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/media)提供查询与查看逻辑 |

包边界约束见 [业务 UI 约定](../../../../frontend/packages/astrophotoflow-ui/AGENTS.md)和 [宿主约定](../../../../frontend/src/platform/astrophotoflow/AGENTS.md)。上游附带模块从 [platform](../../../../frontend/src/platform)、[components](../../../../frontend/src/components)与 [composables](../../../../frontend/src/composables)定位，是否接入本地产品由当前 Router、注册代码和调用者确认。

## 技术与共享基础

| 需求 | 权威入口 |
| --- | --- |
| Vue、TypeScript、Pinia、Router、VueUse、Reka UI、PrimeVue、Vite、Vitest、Playwright 依赖 | [前端 package.json](../../../../frontend/package.json)、[workspace catalog](../../../../frontend/pnpm-workspace.yaml)；UI 包另使用 TanStack Vue Query、Zod 和生成客户端 |
| 别名、类型与模块解析 | [tsconfig.json](../../../../frontend/tsconfig.json)、[UI 包 tsconfig](../../../../frontend/packages/astrophotoflow-ui/tsconfig.json)；宿主 `@/` 指向原生 src，包内测试 `@ui` 指向包 src |
| 语义样式、图标与组件变体 | [design-system 导出](../../../../frontend/packages/design-system/package.json)，具体视觉入口见 [组件路由](component-router.md#视觉入口) |
| class 合并与共享纯工具 | [tailwind-utils](../../../../frontend/packages/tailwind-utils)、[shared-frontend-utils](../../../../frontend/packages/shared-frontend-utils)；按包公开导出选择 |
| 国际化 | [宿主 i18n.ts](../../../../frontend/src/i18n.ts)合并并注入 [业务 i18n.ts](../../../../frontend/packages/astrophotoflow-ui/src/core/i18n.ts)；语言与覆盖规则见前端子系统 |
| 前端 API 类型与校验 | [generated/api](../../../../frontend/packages/astrophotoflow-ui/src/generated/api)、[openapi-ts.config.ts](../../../../frontend/packages/astrophotoflow-ui/openapi-ts.config.ts)；从根 `pnpm generate:sdk` 生成 |

## 工具与验证

命令在仓库根执行。脚本定义以 [根 package.json](../../../../package.json)为准，前端依赖与锁文件归 frontend。构建产物位置见 [根约定](../../../../AGENTS.md)，环境与真实运行见 [开发文档](../../../../docs/development.md)。

| 改动范围 | 验证入口 |
| --- | --- |
| 业务 UI 组件和查询 | `pnpm test <测试路径片段>`、`pnpm typecheck`；用例在 [UI tests](../../../../frontend/packages/astrophotoflow-ui/tests)，挂载环境见 tests/setup.ts |
| 原生组件和宿主桥接 | `pnpm --dir frontend exec vitest run --config vite.config.mts <测试路径>`；配置含原生 src 用例，检查当前 [Vite test projects](../../../../frontend/vite.config.mts)；根 typecheck 只覆盖 UI 包，宿主类型检查使用 `pnpm --dir frontend typecheck` |
| 导出、跨层依赖 | `pnpm check:boundaries`；规则在 [.dependency-cruiser.json](../../../../frontend/.dependency-cruiser.json) |
| 打包与样式扫描 | `pnpm build`；入口 [build_frontend.py](../../../../scripts/build_frontend.py)与 [vite.config.mts](../../../../frontend/vite.config.mts) |
| 布局、键盘、Portal、缩放和拖拽 | 选相关 [产品浏览器测试](../../../../tests/browser)或原生组件 Storybook，用 `pnpm test:browser` 对授权的测试 workspace 验证；环境与回执要求见 [测试文档](../../../../docs/testing.md) |
| 导航资料与 skill | `pnpm check:docs`，同时核对当前源码与代表调用者 |

按实际影响选择检查。根 `pnpm test` 的过滤范围以 UI 包 Vitest 配置为准，宿主测试需显式使用前端配置。既有模块说明中的命令提示也需与这些当前配置核对。
