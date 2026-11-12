# Agent Note: 核对缩略图原件内容与停止顺序

Status: Implemented

## Problem

缩略图任务可能与固定内容变动、停止和提交竞争。

## Decision

验证固定原件内容，并同步停止与提交。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

旧内容或已停止任务不能被当作新的有效缓存结果。

依据见 [提交 dcfe6939](https://github.com/MaojieXu/AstroPhotoFlow/commit/dcfe693974185a02609ddd345246b64afbe01f5a)、[test-matrix.md L2446](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L2446)。 相关笔记见 [固定组版本与首帧驱动缩略图批次](../feature/2026-11-02-fixed-group-thumbnail-batches.md)。
