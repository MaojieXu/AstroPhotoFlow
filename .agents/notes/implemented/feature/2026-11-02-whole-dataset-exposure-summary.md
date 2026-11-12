# Agent Note: 累计曝光按完整固定组汇总

Status: Implemented

## Problem

以当前页求和会受筛选和分页影响。

## Decision

数据库对整个指定组累计 subframe 曝光，区分未知和零，不把 Master 或 integration_seconds 纳入。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

明确历史版本按冻结事实显示，当前资料修正可刷新当前组。

依据见 [提交 ae43fe41](https://github.com/MaojieXu/AstroPhotoFlow/commit/ae43fe41e80cbed621c4fbc51c9418f64b2746f0)、[test-matrix.md L16](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L16)。 相关笔记见 [把素材列表过滤和分页推入 SQL](../architecture/2026-10-31-library-queries-in-sql.md)。
