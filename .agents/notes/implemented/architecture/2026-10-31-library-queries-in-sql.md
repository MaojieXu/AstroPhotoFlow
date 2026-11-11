# Agent Note: 把素材列表过滤和分页推入 SQL

Status: Implemented

## Problem

先读取全集再由应用筛选不适合持续增长的图库。

## Decision

将有边界的筛选、分页及相关汇总移入数据库查询。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

读接口保留稳定语义，分页页内结果与全组事实分别计算。

依据见 [提交 679be0cf](https://github.com/MaojieXu/AstroPhotoFlow/commit/679be0cf93b5dabbd25e59ca6375777f5277b111)、[test-matrix.md L1066](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L1066)。
