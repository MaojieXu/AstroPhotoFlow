# Agent Note: 按任务维护最少文档

Status: Implemented

## Problem

旧规则默认要求通读大量文档，需求、现状和未来设计混在一起。

## Decision

10 月 29 日决定按任务读短上下文与计划，旧 22 Batch 和草案移为历史参考，接口快照沿用生成链。10 月 30 日提交该调整。

## Alternatives considered

旧固定的概要、数据草案和全量接口前置流程被替代。

## Consequences

未完成目标继续保留。后续文档重构进一步移除了旧树，历史可由 Git 查回。

依据见 [提交 2a6053eb](https://github.com/MaojieXu/AstroPhotoFlow/commit/2a6053eb3e8351156d7fb2b4b1ed208e6e628bc0)、[0001-minimal-documentation.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/decisions/0001-minimal-documentation.md)、[2026-11-06-docs-rebuild](2026-11-06-docs-rebuild.md)。 相关笔记见 [采用可执行批次与共享 HTTP 客户端设计](2026-10-27-executable-batches-shared-client.md)。
