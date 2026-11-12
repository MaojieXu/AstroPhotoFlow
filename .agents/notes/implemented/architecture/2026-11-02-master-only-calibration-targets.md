# Agent Note: 校准只绑定固定 Master 版本

Status: Implemented

## Problem

原始校准组、用途不相符的素材与可应用 Master 容易混淆。

## Decision

只接受适用槽位的固定 Master 素材版本，保留消费者和 Master 来源的历史固定组。

## Alternatives considered

旧组目标列被移除。存在旧 raw 绑定的库显式拒绝迁移。

## Consequences

既有科学关系不会被迁移静默丢弃。新库中的未配置、明确不用、不适用及继承分别显示。

依据见 [提交 ae43fe41](https://github.com/MaojieXu/AstroPhotoFlow/commit/ae43fe41e80cbed621c4fbc51c9418f64b2746f0)、[test-matrix.md L16](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L16)。 相关笔记见 [校准组与固定版本绑定](../feature/2026-10-25-versioned-calibration-bindings.md)。
