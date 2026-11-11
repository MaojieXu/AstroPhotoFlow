# Agent Note: 划分平台模块与原生 UI 边界

Status: Implemented

## Problem

宿主协调、业务组件和后端模块需要清晰归属。

## Decision

组织平台模块及原生桥接，业务 UI 与宿主内部协调分开。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

后续工作可把业务组件留在私有包，并由宿主拥有画布及原生状态。

依据见 [提交 16025dd8](https://github.com/MaojieXu/AstroPhotoFlow/commit/16025dd89f2c3c2b25bae58bcc241e5202863c87)。
