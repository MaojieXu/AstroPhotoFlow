# Agent Note: 核对滤镜保存与现代化回归

Status: Implemented

## Problem

新通道字段和旧夹具在集成后需要对齐。

## Decision

验证滤镜 Channel 的实际保存，修正不符合现行契约的回归夹具。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

避免把旧测试期待当成已通过的行为。

依据见 [提交 1bd7ffc2](https://github.com/MaojieXu/AstroPhotoFlow/commit/1bd7ffc2f0c4501c52bb138315cc547c4b5ebdea)、[提交 25acb66f](https://github.com/MaojieXu/AstroPhotoFlow/commit/25acb66ff4a84b3df1c8486cb24f3790c833aaf0)、[test-matrix.md L2297](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L2297)。 相关笔记见 [滤镜 Channel 采用自由文本](../feature/2026-11-01-free-text-filter-channel.md)。
