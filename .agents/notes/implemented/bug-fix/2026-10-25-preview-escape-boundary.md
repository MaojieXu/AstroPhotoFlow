# Agent Note: 在 workspace 内处理预览 Escape

Status: Implemented

## Problem

关闭预览的 Escape 可能被宿主快捷键同时处理。

## Decision

在 workspace 的键盘边界处理预览关闭。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

预览关闭和宿主快捷键各按自身边界工作。

依据见 [提交 6107fbe6](https://github.com/MaojieXu/AstroPhotoFlow/commit/6107fbe6d16f36a184f68038aad664fd72c69209)。
