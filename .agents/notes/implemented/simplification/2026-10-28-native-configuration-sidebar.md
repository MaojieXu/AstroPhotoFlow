# Agent Note: 将配置移入原生侧栏

Status: Implemented

## Problem

悬浮配置按钮和弹窗偏离原生工作台导航。

## Decision

用原生侧栏注册配置面板，复用侧栏尺寸、切换和主题。

## Alternatives considered

原方案使用挂在画布上的配置弹窗，配置与控制语义沿用。

## Consequences

用户可在原生设置中维护配置。

依据见 [提交 3d126d3d](https://github.com/MaojieXu/AstroPhotoFlow/commit/3d126d3d834efe27ff52d6d6f8877d35012c7ec5)、[WORKBENCH-FOUNDATION-0063-native-configuration-sidebar.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/frontend/docs/adr/WORKBENCH-FOUNDATION-0063-native-configuration-sidebar.md)。 相关笔记见 [以单一控制入口管理双服务生命周期](../architecture/2026-10-27-controlled-workbench-lifecycle.md)。
