# Agent Note: 以原生侧栏替代独立素材页面

Status: Implemented

## Problem

页面式原生网页接入后，素材和设备需要与画布同时可用。

## Decision

修改原生导航 ADR，改为单一 workspace 路由和持续挂载的画布。Library 位于 Node Library 和 Workflows 之间，器材入口留在库内。

## Alternatives considered

早期原生网页把 Library、Workflows、Settings 分到产品页面。

## Consequences

侧栏切换不另走页面路由，仍保留 graph 查询参数、表单草稿保护和画布视口。

依据见 [提交 c11745a7](https://github.com/MaojieXu/AstroPhotoFlow/commit/c11745a7b6499baa508d9062d1658edde9f0c925)、[WORKBENCH-NAV-0044-native-pages-and-graph-location.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/frontend/docs/adr/WORKBENCH-NAV-0044-native-pages-and-graph-location.md)。 相关笔记见 [分离原生网页路由与子图位置](2026-10-25-native-page-graph-location.md)、[素材库进入原生画布侧栏](../feature/2026-10-25-native-canvas-library-sidebar.md)。
