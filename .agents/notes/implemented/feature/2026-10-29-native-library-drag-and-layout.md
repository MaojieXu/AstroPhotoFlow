# Agent Note: 素材库布局与整行拖入原生画布

Status: Implemented

## Problem

用户需要从库列表把已选素材放进同一个编辑器。

## Decision

改进素材列表布局、长名称显示和整行拖拽，使用原生放置路径。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

素材数据仍按其引用进入画布，拖拽不另建编辑器。

依据见 [提交 cbfb8914](https://github.com/MaojieXu/AstroPhotoFlow/commit/cbfb89145e3402807f7b334b48a346a50a4a49de)、[test-matrix.md L1353](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L1353)。 相关笔记见 [素材库进入原生画布侧栏](2026-10-25-native-canvas-library-sidebar.md)。
