# Agent Note: 取消独立拍摄预设

Status: Implemented

## Problem

独立预设使器材、组合和拍摄值同时需要维护。

## Decision

移除预设运行合同及旧表，保留直接设备或可选组合、明确滤镜选择和素材固定快照。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

历史迁移可追溯。设备关联不覆盖已记录拍摄参数。

依据见 [提交 ae43fe41](https://github.com/MaojieXu/AstroPhotoFlow/commit/ae43fe41e80cbed621c4fbc51c9418f64b2746f0)、[test-matrix.md L32](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L32)。 相关笔记见 [设备组合与所属拍摄预设](../feature/2026-10-25-owned-equipment-setups-and-presets.md)、[精简设备表单和组合](2026-11-01-simplify-equipment-fields-and-setups.md)。
