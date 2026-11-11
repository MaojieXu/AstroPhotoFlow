# Agent Note: 复用已核验的前端产物和包缓存

Status: Implemented

## Problem

每个新 Worktree 重建相同网页耗时。

## Decision

普通构建记录指纹。准备入口核对基点、工具、前端输入和产物后复用，并采用主仓库包缓存。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

不符合记录时需重新构建。跨平台与无缓存首装另行验证。

依据见 [提交 d6485185](https://github.com/MaojieXu/AstroPhotoFlow/commit/d648518510f679a7d9195722a8d37cd48edbcff0)、[test-matrix.md L2385](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L2385)。 相关笔记见 [固定 Windows bootstrap 并拆分准备阶段](2026-10-30-windows-bootstrap-workspace-preparation.md)。
