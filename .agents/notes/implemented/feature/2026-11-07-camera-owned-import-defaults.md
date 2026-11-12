# Agent Note: 相机默认参数与紧凑导入确认

Status: Implemented

## Problem

导入确认表单要求重复选择像素排列和 ISO 或 Gain／Offset 模式。单文件与批量共用同一套宽弹窗，但设备控件、单列参数和多段说明占用了过多空间。望远镜附件区也一直显示空列表说明和倍率示例。

## Decision

相机规格沿用 `cfa_pattern`，并新增可选的 `default_parameter_mode`。导入受理时冻结实际应用的相机规格，覆盖直接设备选择、设备组合和内联相机。登记使用冻结规格补齐模式，且仅对阵列信息缺失、可确认的二维 FITS 原始子帧补齐 CFA。文件事实及显式提供的值保持原有优先级，设备推导值用 `equipment` 标记。校准预检、登记和元数据重读沿用同一规则与冻结资料。 [相机规格](../../../../src/astrophotoflow/contracts/equipment.py) · [导入参数解析](../../../../src/astrophotoflow/modules/data/imports/metadata.py)

导入确认复用设备编辑器的中号弹窗和紧凑控件，把文件数、体积与托管说明放在一行。单文件和批量使用同一个常显表单，按实际选择显示组名、分类和可用的手填数值。望远镜附件的原焦说明和倍率示例移入标题旁的 `LibraryInfo`，输入无效时仍由对应字段提示。 [导入确认组件](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/imports/ImportDialog.vue) · [附件编辑器](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/equipment/OpticalAccessoriesEditor.vue)

## Alternatives considered

继续让导入表单整批手填阵列和模式，会让相机规格和导入输入承担同一职责。由后台读取实时设备库，则会让受理后的设备编辑影响正在登记或重试的任务。用折叠收纳表单可以压低默认高度，但用户查看和填写资料时仍要展开。

## Consequences

现有设备规格 JSON 承载新增可选字段，旧相机缺省时仍可导入。曝光、ISO、Gain、Offset 和实测温度依文件观察或用户明确填写，数值 `0` 继续保留。已有版本读取自己的冻结资料，组名及备注仍随单文件或批量场景处理。本次实现已完成前端构建并在独立浏览器预览打开。相关前序记录见[工作台与素材侧栏精简](../simplification/2026-11-07-deduplicate-workbench-panels.md)和[Windows 文件选择器](../bug-fix/2026-11-07-native-picker-without-compilation.md)。
