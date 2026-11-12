# Agent Note: 固定组版本与首帧驱动缩略图批次

Status: Implemented

## Problem

组成员需要一致的拉伸，又要按需要生成预览。

## Decision

用固定组和首帧版本记录批次与拉伸依赖，批次状态与成员分页分开。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

首帧失败有独立状态，科学素材和派生缩略图保持分离。

依据见 [提交 ae43fe41](https://github.com/MaojieXu/AstroPhotoFlow/commit/ae43fe41e80cbed621c4fbc51c9418f64b2746f0)、[test-matrix.md L5](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L5)。 相关笔记见 [组浏览只用缩略图并共享拉伸](../simplification/2026-10-24-group-thumbnail-shared-stretch.md)。
