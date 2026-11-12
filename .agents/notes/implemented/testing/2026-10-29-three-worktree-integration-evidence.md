# Agent Note: 记录三工作树集成与验证边界

Status: Implemented

## Problem

各工作树独立证据容易被误当作合并后的完整验收。

## Decision

合入三条工作线后核对 Git 一致性，并逐项注明已有验证和未重跑项目。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

能追溯来源及合并情况，不能由该记录推定合并后的产品运行已全验。

依据见 [提交 51046067](https://github.com/MaojieXu/AstroPhotoFlow/commit/5104606740427d463f03d367ef13b0a85b81c935)、[test-matrix.md L1333](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L1333)。
