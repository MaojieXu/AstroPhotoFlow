# Agent Note: 开发和正式发布使用独立通道

Status: Implemented

## Problem

试验标签容易被误认为正式可用版本。

## Decision

10 月 29 日确认使用 X.Y.Z-dev.N 开发版本，正式标签与稳定通道另行批准。

## Alternatives considered

早期实验标签作为历史保留，正式发布不沿用或移动开发标签。

## Consequences

Bundle 目录与 schema 核对通道和标签，记录明确区分开发包、实验标签和正式发行。

依据见 [提交 e56a4ee5](https://github.com/MaojieXu/AstroPhotoFlow/commit/e56a4ee520fb90ceca57197543b7968972ef2afe)、[test-matrix.md L1434](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L1434)。
