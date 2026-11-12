# Agent Note: 隔离切图和 workspace 切换时的预览

Status: Implemented

## Problem

旧图请求或邻帧预取在切换后可能完成。

## Decision

将媒体结果绑定当前图及 workspace，取消过期邻帧预取。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

上一视图的迟到结果不会替换当前预览。

依据见 [提交 dcfe6939](https://github.com/MaojieXu/AstroPhotoFlow/commit/dcfe693974185a02609ddd345246b64afbe01f5a)、[test-matrix.md L2446](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L2446)。 相关笔记见 [异步保存、预览和筛选保留视图归属](2026-10-25-preserve-async-view-owner.md)。
