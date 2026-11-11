# Agent Note: 恢复缩略图缓存和失败首帧依赖

Status: Implemented

## Problem

固定首帧失败或缓存文件消失时，单项重试可能不能完成。

## Decision

只重试所选失败成员和必要首帧依赖，丢失缓存沿原 Preview 身份重新排队。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

保留固定引用和拉伸。原条目只编写了测试，集成提交另有定向验证。

依据见 [提交 ae43fe41](https://github.com/MaojieXu/AstroPhotoFlow/commit/ae43fe41e80cbed621c4fbc51c9418f64b2746f0)、[test-matrix.md L5](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L5)。 相关笔记见 [固定组版本与首帧驱动缩略图批次](../feature/2026-11-02-fixed-group-thumbnail-batches.md)。
