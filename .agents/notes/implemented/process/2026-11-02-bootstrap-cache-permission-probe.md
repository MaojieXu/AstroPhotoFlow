# Agent Note: 准备前核对缓存写入权限

Status: Implemented

## Problem

共享工具和日志目录的权限错误可能在安装中途才暴露。

## Decision

在工具准备前探测缓存与 npm 日志路径的可写性，固定 pnpm 安装优先复用缓存并保留严格离线选项。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

失败直接指出路径，不修改全局权限或改用未知缓存。

依据见 [提交 a3857c74](https://github.com/MaojieXu/AstroPhotoFlow/commit/a3857c745b63d830800dfe49362a39480fe69788)、[test-matrix.md L2378](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L2378)。 相关笔记见 [固定 Windows bootstrap 并拆分准备阶段](2026-10-30-windows-bootstrap-workspace-preparation.md)。
