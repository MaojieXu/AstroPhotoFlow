# Agent Note: 按需查看原始分辨率素材

Status: Implemented

## Problem

小缩略图不足以判断细节，全组预生成大图成本高。

## Decision

在原生 Vue 壳内使用 OpenSeadragon。数据模块管理区域读取、显示配方、可取消准备及可丢弃缓存。

## Alternatives considered

ADR 比较了放大缩略图、加载全尺寸图和全量预生成金字塔。

## Consequences

查看器提供原始分辨率区域的显示，不改变科学输入或画布。

依据见 [提交 366a3112](https://github.com/MaojieXu/AstroPhotoFlow/commit/366a3112911918e95b959439e2da4f0dc58582b0)、[APF-PREVIEW-0001-on-demand-media-viewing.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/frontend/docs/adr/APF-PREVIEW-0001-on-demand-media-viewing.md)。 相关笔记见 [按需生成固定配方显示预览](2026-10-25-lazy-recipe-display-preview.md)。
