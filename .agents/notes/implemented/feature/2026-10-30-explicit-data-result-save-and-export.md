# Agent Note: 显式保存或导出 Data 完整结果

Status: Implemented

## Problem

完成预览不能承担长期保存科学输出的职责。

## Decision

让 Data 接收用户明确选中的完整结果，保存到库或导出实际科学文件。

## Alternatives considered

旧 ADR 曾考虑按项目自动登记和显式共享。后续选择按用户实际选中的完整结果保存。

## Consequences

保留固定成员及科学来源。部分预览和完整结果仍独立。

依据见 [提交 55484461](https://github.com/MaojieXu/AstroPhotoFlow/commit/55484461b2f9cbccfe404a3b9f9f58d903f3ce71)、[WORKBENCH-DATA-0047-project-results-and-shared-library.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/frontend/docs/adr/WORKBENCH-DATA-0047-project-results-and-shared-library.md)、[WORKBENCH-DATA-0055-selected-results-and-previews.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/frontend/docs/adr/WORKBENCH-DATA-0055-selected-results-and-previews.md)、[提交 974347a3](https://github.com/MaojieXu/AstroPhotoFlow/commit/974347a3d14379c25ab06e16b54fb8423b22629b)。 相关笔记见 [区分科学数据与显示预览](../architecture/2026-10-22-separate-science-and-display.md)。
