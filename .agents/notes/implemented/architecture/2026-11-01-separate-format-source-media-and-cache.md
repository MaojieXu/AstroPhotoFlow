# Agent Note: 分开科学格式、媒体、缓存与清理职责

Status: Implemented

## Problem

图像读取、瓦片租约、缓存和原件生命周期混在一起时难以保护科学文件。

## Decision

划分格式层、源文件读取、派生媒体、瓦片／租约和清理阶段。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

派生文件可以重建，清理不改变固定科学输入。

依据见 [提交 679be0cf](https://github.com/MaojieXu/AstroPhotoFlow/commit/679be0cf93b5dabbd25e59ca6375777f5277b111)、[test-matrix.md L245](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L245)、[test-matrix.md L284](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L284)。 相关笔记见 [按需查看原始分辨率素材](../feature/2026-10-29-on-demand-original-media-viewer.md)。
