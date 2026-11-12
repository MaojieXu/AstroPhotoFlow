# Agent Note: 保留 AstroPhotoFlow 启动画面的进度条

Status: Implemented

## Problem

本地发行模式的 Vite 品牌插件替换了整个启动容器，导致 HTML 中新增的进度条在浏览器收到页面前就被移除。

## Decision

品牌转换仅替换启动容器内的 Logo SVG，并更新容器的无障碍名称。进度条由共用 HTML 模板提供。

## Alternatives considered

在品牌插件中重新插入进度条会使两个入口各自维护一份加载标记。

## Consequences

品牌模式沿用共用的进度条和启动完成条件。验证启动画面时需要检查经过 Vite 转换的页面。
