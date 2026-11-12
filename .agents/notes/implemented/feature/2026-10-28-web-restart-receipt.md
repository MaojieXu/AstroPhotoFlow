# Agent Note: 网页重启与可查询回执

Status: Implemented

## Problem

已保存设置需要可显式重启采用，丢失响应时需要核对是否已启动。

## Decision

接入网页重启及当前操作回执，浏览器先生成操作 ID，未保存编辑时阻止重启。

## Alternatives considered

沿用本机控制器的启停行为和已有运行记录。

## Consequences

丢失回复时查询同一 ID。实际地址变化可能需要用户重新访问。

依据见 [提交 be0422e5](https://github.com/MaojieXu/AstroPhotoFlow/commit/be0422e5b0e2cc121be2df81dfcded81a97398f3)、[WORKBENCH-FOUNDATION-0064-web-restart-and-native-controls.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/frontend/docs/adr/WORKBENCH-FOUNDATION-0064-web-restart-and-native-controls.md)。 相关笔记见 [将配置移入原生侧栏](../simplification/2026-10-28-native-configuration-sidebar.md)。
