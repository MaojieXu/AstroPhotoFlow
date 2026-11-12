# Agent Note: 精简设备表单和组合

Status: Implemented

## Problem

设备录入字段及组合选择一度过重。

## Decision

精简表单，组合保留单相机、单望远镜及多个滤镜，并收敛预设选择。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

设备身份和已导入素材的快照继续独立。后续再删除独立拍摄预设。

依据见 [提交 679be0cf](https://github.com/MaojieXu/AstroPhotoFlow/commit/679be0cf93b5dabbd25e59ca6375777f5277b111)、[test-matrix.md L2231](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L2231)。 相关笔记见 [设备组合与所属拍摄预设](../feature/2026-10-25-owned-equipment-setups-and-presets.md)。
