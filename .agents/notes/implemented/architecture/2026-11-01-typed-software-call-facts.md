# Agent Note: 具体软件调用使用类型化事实

Status: Implemented

## Problem

随着流程模块退出，实际进程、输出及停止观察需要稳定归属。

## Decision

把调用和观察交给 software，使用明确的运行事实和类型化配方，保留未知与已结束的区别。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

查询同一执行核对未知结果，跨模块只经公开入口读写。

依据见 [提交 679be0cf](https://github.com/MaojieXu/AstroPhotoFlow/commit/679be0cf93b5dabbd25e59ca6375777f5277b111)、[test-matrix.md L330](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L330)。
