# Agent Note: 统一导入预检和实际登记的参数优先级

Status: Implemented

## Problem

显式 null 和人工 CFA 在预检与实际登记之间可能解释不同。

## Decision

共用参数、分类和 CFA 派生规则。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

预检结论对应同一实际登记语义，测试覆盖前检、导入及检查读回。

依据见 [提交 ae43fe41](https://github.com/MaojieXu/AstroPhotoFlow/commit/ae43fe41e80cbed621c4fbc51c9418f64b2746f0)、[test-matrix.md L32](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L32)。 相关笔记见 [登记前只读检查扫描素材的校准条件](../feature/2026-11-02-read-only-calibration-import-preflight.md)。
