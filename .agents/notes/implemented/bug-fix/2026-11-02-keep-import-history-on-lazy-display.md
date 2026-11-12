# Agent Note: 按需显示不重写历史导入状态

Status: Implemented

## Problem

后来生成预览时可能改写旧任务原有的 not_requested 或失败事实。

## Decision

让显示生成只更新 Preview，独立保留旧导入记录。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

当前可查看与历史上是否请求过预览可以同时准确表达。

依据见 [提交 ae43fe41](https://github.com/MaojieXu/AstroPhotoFlow/commit/ae43fe41e80cbed621c4fbc51c9418f64b2746f0)、[test-matrix.md L42](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L42)。 相关笔记见 [导入与派生预览解耦](../simplification/2026-11-02-lightweight-import-and-lazy-display.md)。
