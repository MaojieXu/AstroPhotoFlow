# 组件路由

按需求进入下表。源码入口所在目录通常还包含同名 `.stories.ts`、`.test.ts` 与配套类型，按需读取。表中链接用于快速定位，完整 props、事件、模型与插槽以当前实现为准。

## 原生组件

| 需求 | 复用入口 | 调用、示例与核对点 |
| --- | --- | --- |
| 操作按钮、图标按钮、加载态 | [Button](../../../../frontend/src/components/ui/button/Button.vue)、[buttonVariants](../../../../frontend/packages/design-system/src/button.variants.ts) | [Button stories](../../../../frontend/src/components/ui/button/Button.stories.ts)；现成 variant、size、loading、tooltip，图标按钮保留可访问名称 |
| 文本、多行文本、搜索 | [Input](../../../../frontend/src/components/ui/input/Input.vue)、[Textarea](../../../../frontend/src/components/ui/textarea/Textarea.vue)、[search-input](../../../../frontend/src/components/ui/search-input) | 宿主注入实例见 LibrarySidebarTab；搜索从 SearchInput、AsyncSearchInput、SearchAutocomplete 中按数据来源选择 |
| 单选、搜索选择、多选 | [SingleSelect](../../../../frontend/src/components/ui/single-select/SingleSelect.vue)、[MultiSelect](../../../../frontend/src/components/ui/multi-select/MultiSelect.vue) | [单选 stories](../../../../frontend/src/components/ui/single-select/SingleSelect.stories.ts)、[多选 stories](../../../../frontend/src/components/ui/multi-select/MultiSelect.stories.ts)；核对选项类型、v-model、open、modal 与弹层宽度 |
| 复选、开关、互斥选择 | [Checkbox](../../../../frontend/src/components/ui/checkbox/Checkbox.vue)、[Switch](../../../../frontend/src/components/ui/switch/Switch.vue)、[radio-group](../../../../frontend/src/components/ui/radio-group) | 各目录 stories 与 tests；核对受控模型和混合状态支持 |
| 数值、步进、范围与颜色 | [FormNumberField](../../../../frontend/src/components/common/FormNumberField.vue)、[number-field](../../../../frontend/src/components/ui/number-field)、[Slider](../../../../frontend/src/components/ui/slider/Slider.vue)、[ColorPicker](../../../../frontend/src/components/ui/color-picker/ColorPicker.vue) | FormNumberField 的宿主使用见 WorkbenchSettingsPanel；画布中同时核对坐标缩放与输入事件 |
| 设置字段、标签与错误提示 | [FormItem](../../../../frontend/src/components/common/FormItem.vue)、[field](../../../../frontend/src/components/ui/field) | [FormItem test](../../../../frontend/src/components/common/FormItem.test.ts)；FormItem 根据设置 item 渲染控件并关联标签，使用前核对 item 契约与 formValue 模型 |
| 弹窗与确认表单 | [dialog](../../../../frontend/src/components/ui/dialog)、[LibraryFormDialog](../../../../frontend/src/platform/astrophotoflow/sidebar/LibraryFormDialog.vue) | [LibraryFormDialog test](../../../../frontend/src/platform/astrophotoflow/sidebar/LibraryFormDialog.test.ts)；项目适配已组合 Portal、标题、关闭按钮与 busy 保护 |
| 下拉菜单、右键菜单、单选菜单 | [Menu](../../../../frontend/src/components/ui/menu/Menu.vue)、[ContextMenu](../../../../frontend/src/components/ui/menu/ContextMenu.vue) | [menu types](../../../../frontend/src/components/ui/menu/types.ts)、同目录 stories；核对 trigger 插槽、items、open 和 Portal 目标 |
| 气泡与悬停说明 | [popover](../../../../frontend/src/components/ui/popover)、[TextTooltip](../../../../frontend/src/components/ui/tooltip/TextTooltip.vue)、[hover-card](../../../../frontend/src/components/ui/hover-card) | 各目录 stories；Button 已支持 tooltip，现有 `ui/Popover.vue` 的调用者按实际接口核对 |
| 表格、排序表头与分页 | [table](../../../../frontend/src/components/ui/table)、[Pagination](../../../../frontend/src/components/ui/pagination/Pagination.vue) | [Pagination stories](../../../../frontend/src/components/ui/pagination/Pagination.stories.ts)；Table 提供展示结构，业务排序和服务分页沿页面已有查询实现 |
| 标签页、树、分栏 | [tabs](../../../../frontend/src/components/ui/tabs)、[Tree](../../../../frontend/src/components/ui/tree/Tree.vue)、[splitter](../../../../frontend/src/components/ui/splitter) | 各目录 stories；标签页核对模型与插槽，分栏核对最小尺寸与侧栏滚动 |
| 通知、内联状态、徽标 | [toastStore](../../../../frontend/src/components/ui/toast/toastStore.ts)、[Message](../../../../frontend/src/components/ui/message/Message.vue)、[Badge](../../../../frontend/src/components/ui/badge/Badge.vue) | LibrarySidebarTab 演示成功、失败与带 action 的通知；核对通知清理、持续时间与操作归属 |
| 加载与空状态 | [Spinner](../../../../frontend/src/components/ui/spinner/Spinner.vue)、[Skeleton](../../../../frontend/src/components/ui/skeleton/Skeleton.vue)、[NoResultsPlaceholder](../../../../frontend/src/components/common/NoResultsPlaceholder.vue) | 各组件当前调用者；按页面已有查询状态显示 loading、empty 和 error |
| 拖拽、图像和虚拟列表 | [DraggableList](../../../../frontend/src/components/common/DraggableList.vue)、[ComfyImage](../../../../frontend/src/components/common/ComfyImage.vue)、[composables](../../../../frontend/src/composables) | 拖入画布走下表 LibraryCanvasSource；大型列表先找对应调用者对 `@tanstack/vue-virtual` 的使用 |

## 业务适配与组合

| 当前任务 | 首选入口与调用实例 |
| --- | --- |
| 在素材、设备、导入界面新增表单 | [data/components](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/components)已有 LibraryButton、LibraryTextField、LibraryInput、LibraryTextarea、LibrarySelect、LibraryMultiSelect、LibraryCheckbox、LibraryMenu、LibraryTabs、LibraryDialog 与 InlineField；实际组合见 [EquipmentSetupManager](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/equipment/EquipmentSetupManager.vue)和 [ImportDialog](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/imports/ImportDialog.vue) |
| 查控件从哪里注入、如何接入宿主 | [LibraryControls](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/workspace/libraryControls.ts)定义类型与注入 key，[LibrarySidebarTab](../../../../frontend/src/platform/astrophotoflow/sidebar/LibrarySidebarTab.vue)构造原生 controls，经 Workspace 传入 WorkspacePage，再由 WorkspacePage provide；读取具体 Library 包装以确认转发与模型转换 |
| 修改设备字段、设备组合或编辑草稿 | [EquipmentFields](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/equipment/EquipmentFields.vue)、[EquipmentSetupTable](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/equipment/EquipmentSetupTable.vue)、[useSetupEditor](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/equipment/useSetupEditor.ts)；领域提交沿同目录 mutations 和生成模型 |
| 复用侧栏外壳和设置控件 | [SidebarTabTemplate](../../../../frontend/src/components/sidebar/tabs/SidebarTabTemplate.vue)、LibrarySidebarTab、[WorkbenchSettingsPanel](../../../../frontend/src/platform/astrophotoflow/settings/WorkbenchSettingsPanel.vue)；沿用标题、body 插槽、关闭保护和 controls 装配 |
| 素材拖入或点击放置节点 | [LibraryCanvasSource](../../../../frontend/src/platform/astrophotoflow/canvas/LibraryCanvasSource.vue)、[CanvasDataWidget](../../../../frontend/src/platform/astrophotoflow/canvas/CanvasDataWidget.vue)；数据写入从架构导航的 session 与 dataBridge 进入 |
| 图像、视频、概览或结果预览 | [MediaViewer](../../../../frontend/src/platform/astrophotoflow/media/MediaViewer.vue)、[MediaImagePreview](../../../../frontend/src/platform/astrophotoflow/media/MediaImagePreview.vue)；WorkspacePage 优先挂载 controls.mediaViewer，无注入分支使用 [PhotoPreviewDialog](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/media/PhotoPreviewDialog.vue)；查看状态遵守前端子系统契约 |
| 保存、导出或显示节点结果 | [DataExportDialog](../../../../frontend/src/platform/astrophotoflow/results/DataExportDialog.vue)、[BundleResultWidget](../../../../frontend/src/platform/astrophotoflow/results/BundleResultWidget.vue)、[AnalysisView](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/results/AnalysisView.vue)；对应目录 tests 验证实际回执与结果语义 |

业务适配的现有无宿主分支服务当前挂载方式，复用时保留已有调用行为。宿主消费业务组件从 [包公开导出](../../../../frontend/packages/astrophotoflow-ui/src/index.ts)进入。需要跨业务复用时先核对公开入口与当前调用需求。

## 视觉入口

| 修改内容 | 先查 |
| --- | --- |
| 语义颜色、尺寸、主题与字体 | [design-system style.css](../../../../frontend/packages/design-system/src/css/style.css)、[palette](../../../../frontend/packages/design-system/src/css/_palette.css)、[fonts](../../../../frontend/packages/design-system/src/css/fonts.css)、[colorPaletteService](../../../../frontend/src/services/colorPaletteService.ts)；沿用所在组件的语义 class 与 token |
| 按钮、选择器、标签变体与 class 合并 | [design-system 导出](../../../../frontend/packages/design-system/package.json)、[tailwind-utils](../../../../frontend/packages/tailwind-utils)的 `cn`；原生 Button 展示变体组合方式 |
| 图标与设计参考 | 现有 `icon-[lucide--…]`、`icon-[comfy--…]` 用法和 [图标源](../../../../frontend/packages/design-system/src/icons)；设计参考入口见 [design-standards](../../../../frontend/docs/guidance/design-standards.md) |
| 样式扫描与业务布局 | [宿主 style.css](../../../../frontend/src/assets/css/style.css)扫描 UI 包源码；[data/styles.css](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/styles.css)、[equipmentCompact.css](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/workspace/equipmentCompact.css)及当前组件样式；修改前检查选择器影响范围 |

新实现遵循 [前端约定](../../../../frontend/AGENTS.md)与该目录 guidance，新增 PrimeVue 使用先核对现有限制。已有局部 CSS、适配与组件变体各有调用者，修改时核对实际用途。验证命令见 [架构导航](architecture-map.md#工具与验证)。
