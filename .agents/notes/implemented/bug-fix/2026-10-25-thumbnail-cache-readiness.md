# Agent Note: 以当前缩略图缓存判断显示就绪

Status: Implemented

## Problem

任务历史状态可能与当前可读取的缩略图不一致。

## Decision

让可用的缩略图缓存决定当前显示是否就绪。

## Alternatives considered

以历史任务完成状态推断当前缓存。

## Consequences

任务状态继续描述历史执行，显示状态依据当前可读内容。

依据见 [提交 96790808](https://github.com/MaojieXu/AstroPhotoFlow/commit/96790808715be6c51128c297ae15c3c2854b585b)、[提交 e498e262](https://github.com/MaojieXu/AstroPhotoFlow/commit/e498e26243144ce50017bd1d3305eee3a5943c53)。
