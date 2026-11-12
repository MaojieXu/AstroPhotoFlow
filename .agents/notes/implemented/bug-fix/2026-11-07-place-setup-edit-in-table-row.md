# Agent Note: 把设备组合编辑移入所选行

Status: Implemented

## Problem

设备组合表把编辑按钮放在列表下方。选中一行后，按钮紧贴表格边缘，容易被看成独立的列表内容。

## Decision

普通浏览时在表格右侧预留操作列，选中行显示带名称和悬浮提示的铅笔按钮。按钮打开当前选中组合的编辑器，点击操作与行选择分别处理。批量管理使用复选列，普通浏览的操作列随模式切换收起。 [设备组合表](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/equipment/EquipmentSetupTable.vue)

## Alternatives considered

把按钮放进顶部工具栏可以保留数据列宽度，但会占用搜索与新建组合的空间。给表格下方的按钮加留白可以缓和边界拥挤，按钮仍与所选行分离。

## Consequences

操作列在普通浏览时固定占宽，选择不同组合时列宽稳定。窄侧栏沿用表格横向滚动。编辑仍受保存和草稿状态约束。在独立浏览器预览中使用已登记的组合核对了行内按钮和编辑弹窗。 [组合表回归用例](../../../../frontend/packages/astrophotoflow-ui/tests/modules/data/workspace/EquipmentSetupTable.test.ts)
