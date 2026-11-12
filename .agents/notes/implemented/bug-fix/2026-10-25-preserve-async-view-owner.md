# Agent Note: 异步保存、预览和筛选保留视图归属

Status: Implemented

## Problem

切换视图后，先前请求的结果可能影响当前页面。

## Decision

保存、预览与筛选完成时核对原来的视图归属。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

切换后的视图不会被上一视图的迟到结果覆盖。

依据见 [提交 b99a53d2](https://github.com/MaojieXu/AstroPhotoFlow/commit/b99a53d29cf881373d1bad27ce06005485f217a0)。
