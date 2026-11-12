# Agent Note: 确立五模块架构基线

Status: Implemented

## Problem

多个模块需要共享边界和契约归属。

## Decision

基线把职责分为基础、数据、软件、节点和工作流交互，并保留一个原生可编辑图。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

当时工作流模块仍在设计中，后续现代化取消自研工作流生命周期。

依据见 [提交 9d4c729c](https://github.com/MaojieXu/AstroPhotoFlow/commit/9d4c729cb35cf961c34fa50cf55616cd6c2e4b10)、[README.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/9d4c729cb35cf961c34fa50cf55616cd6c2e4b10/docs/requirements/README.md)。 相关笔记见 [划分平台模块与原生 UI 边界](2026-10-26-organize-platform-and-native-ui.md)。
