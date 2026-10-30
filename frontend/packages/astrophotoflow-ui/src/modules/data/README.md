# 数据界面

`api`保存实际HTTP客户端和Zod消费模型；`workspace`保存素材／固定组、设备组合、预设及校准界面。`Workspace`从包公开导出，`App.vue`是独立组件测试入口，不是另一套产品应用。

- 本机选择器返回文件／当前层文件夹清单，ImportDialog确认后托管导入；无需配置授权根。原件进度与后台预览分开，任务通知复用宿主Toast，不在表格累计历史横幅。
- 素材简约列表只显示预览和名称；名称点击后选原生落点，整行可拖入，缩略图点击查看。组导航、名称编辑、批量管理、细节资料及就绪限制保留。
- 固定CanvasDataRequest交给宿主`canvasSource`，实际原生节点／撤销由桥接处理。节点图片、成员切换及参数不因拖放调整而删除。
- 查看通过`LibraryControls.mediaViewer`注入宿主，UI包只维护公开消费类型；不导入原生组件／OpenSeadragon或画布Store，查看状态不变成科学输入。
- 表单草稿、分页、筛选和勾选属于UI；revision、固定成员、来源和删除影响由服务返回。设备组合／我的设备与素材库对齐，删除保留历史快照。

完整用户规则见 [需求](../../../../../../docs/requirements/README.md)，数据权威见 [data入口](../../../../../../src/astrophotoflow/modules/data/README.md)，实现／验收见 [当前上下文](../../../../../../docs/development/current-context.md)。不在此累计逐轮候选或复制接口字段。
