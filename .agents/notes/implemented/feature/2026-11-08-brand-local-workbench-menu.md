# Agent Note: 本地工作台菜单使用 AstroPhotoFlow 标志

Status: Implemented

## Problem

本地工作台左上角的菜单沿用 ComfyUI 标志，入口缺少 AstroPhotoFlow 的视觉识别。

## Decision

在原生菜单触发器的本地网页分支中使用「叠帧成星」矢量标志。两层错开的开放画框表现图像叠加，右上角的四芒星表示天文图像。图形使用 24 像素尺寸并继承菜单的前景色，菜单保留现有无障碍名称。

## Alternatives considered

全局替换上游标志会波及其他发行形态。位图需要单独处理小尺寸清晰度和主题颜色，因此采用内联 SVG。

## Consequences

本地工作台菜单显示 AstroPhotoFlow 标志，Cloud 与 Desktop 分支继续显示 ComfyUI 标志。按钮、下拉内容及快捷操作沿用原生菜单。
