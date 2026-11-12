# Agent Note: 隔离复核 M1 配置与控制候选

Status: Implemented

## Problem

单独测试配置读写无法确认双服务采用的地址和控制状态。

## Decision

准备隔离候选及回执，分别核对配置、实际运行和待用户确认项。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

记录是当时候选复核，后续修正另有证据。

依据见 [提交 00ddbd88](https://github.com/MaojieXu/AstroPhotoFlow/commit/00ddbd88f23c0f312eb0bab74797ae202908eb69)、[test-matrix.md L1846](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L1846)。
