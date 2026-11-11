# Agent Note: 分离原生网页路由与子图位置

Status: Implemented

## Problem

浏览器复现子图向路由 hash 写入图 ID，与产品页面导航冲突。

## Decision

hash 保留给产品页面，子图位置放 graph 查询参数。画布首次使用时挂载，切页保持实例。

## Alternatives considered

每次切页重建画布会丢失草稿与视口，原有子图 hash 与页面路径冲突。

## Consequences

顶层跳转保留子图位置及表单导航保护。

依据见 [提交 e7180949](https://github.com/MaojieXu/AstroPhotoFlow/commit/e718094999ee19d2f003a91c8401cba5a1afd3e3)、[WORKBENCH-NAV-0044-native-pages-and-graph-location.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/e718094999ee19d2f003a91c8401cba5a1afd3e3/frontend/docs/adr/WORKBENCH-NAV-0044-native-pages-and-graph-location.md)。 相关笔记见 [迁入 ComfyUI 原生网页工作台](2026-10-25-native-web-workbench.md)。
