# Agent Note: 清理私有 Feature runtime 时取消留副本

Status: Implemented

## Problem

已结束的 Feature 留存重复 runtime 占用空间。

## Decision

经授权清理对应私有 Feature 的运行数据，取消默认保留副本。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

清理范围是明确授权的私有空间。共享实例和真实素材仍独立保护。

依据见 [提交 a53b3213](https://github.com/MaojieXu/AstroPhotoFlow/commit/a53b32131862435cf19a3ad190560ca846563295)。 相关笔记见 [统一 Feature 集成、推送和清理交接](2026-10-30-unified-feature-integration-handoff.md)。
