# Agent Note: 把 Feature 交接收敛为三步

Status: Implemented

## Problem

多角色交接的重复提示提高操作成本。

## Decision

简化成准备、交付和集成的三步入口，保留用户授权与独立审查。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

该历史流程后来被 PR 约定替代，再改为功能分支本地集成。

依据见 [提交 f8c61363](https://github.com/MaojieXu/AstroPhotoFlow/commit/f8c613633148e365839bcc0c1c627a7c42e266ca)、[test-matrix.md L2324](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L2324)、[2026-11-06-pr-workflow](2026-11-06-pr-workflow.md)、[2026-11-06-local-dev-integration](2026-11-06-local-dev-integration.md)。 相关笔记见 [统一 Feature 集成、推送和清理交接](2026-10-30-unified-feature-integration-handoff.md)。
