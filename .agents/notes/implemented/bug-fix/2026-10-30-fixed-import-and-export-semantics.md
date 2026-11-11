# Agent Note: 修正固定导入和完整结果导出语义

Status: Implemented

## Problem

导入及保存链路需要在实际处理时仍使用确认过的固定范围。

## Decision

补齐固定素材输入、完整成员和导出行为的校验。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

运行及回执继续引用已确认内容，导出不以预览或部分成员代替。

依据见 [提交 1925d394](https://github.com/MaojieXu/AstroPhotoFlow/commit/1925d394301a7bfe6e77776c8ae43460e82b0632)。 相关笔记见 [显式保存或导出 Data 完整结果](../feature/2026-10-30-explicit-data-result-save-and-export.md)。
