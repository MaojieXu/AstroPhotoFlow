# Agent Note: 对齐导入确认的分类复选框

Status: Implemented

## Problem

导入确认里「手动指定整批分类」使用裸复选框。通用表单标签的纵向布局把文字排到控件下方，复选框在弹窗里显得过大。

## Decision

分类入口改用工作台的 `LibraryCheckbox`，以弹窗局部样式把勾选框固定为 16 px。可点击标签和帮助图标与勾选框横向对齐，自动识别说明随可用宽度换行。单文件和批量导入共用该表单。 [导入确认组件](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/imports/ImportDialog.vue)

## Alternatives considered

继续使用原生输入并单独覆盖尺寸和样式也能修复这一处，但会额外维护一套复选框表现。现有适配器已承载原生界面控件与 HTML 回退。

## Consequences

分类开关仍控制同一组手动字段和提交值。用户要求自行验收，最新版前端已打开到导入入口。 [前序导入确认改动](../feature/2026-11-07-camera-owned-import-defaults.md)
