# Agent Note: 修复补发布状态与活动子任务核对

Status: Implemented

## Problem

失败后的补发布和仍在运行的子任务需要区分。

## Decision

集成时修正导入补发布状态和活动子任务检查。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

可核对已完成内容与尚待发布的部分，避免将活动任务误报为就绪。

依据见 [提交 dcfe6939](https://github.com/MaojieXu/AstroPhotoFlow/commit/dcfe693974185a02609ddd345246b64afbe01f5a)、[test-matrix.md L2446](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L2446)。
