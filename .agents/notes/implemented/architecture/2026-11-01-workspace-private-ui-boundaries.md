# Agent Note: 按实际能力拆分 UI 与宿主桥接

Status: Implemented

## Problem

候选把过多行为集中进 WorkspacePage，表面完成的文件拆分仍存在职责集中。

## Decision

按素材、配置、媒体及宿主协调能力分拆，重查文件归属和公开入口。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

复核用具体读写路径验证边界，保留 UI 与原生应用的依赖方向。

依据见 [提交 679be0cf](https://github.com/MaojieXu/AstroPhotoFlow/commit/679be0cf93b5dabbd25e59ca6375777f5277b111)、[test-matrix.md L183](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L183)。 相关笔记见 [划分平台模块与原生 UI 边界](2026-10-26-organize-platform-and-native-ui.md)。
