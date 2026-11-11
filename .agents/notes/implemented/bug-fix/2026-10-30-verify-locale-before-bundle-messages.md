# Agent Note: 替换 Bundle 消息前核对已加载语言

Status: Implemented

## Problem

异步消息可能在另一语言已加载后返回。

## Decision

替换 Bundle 消息时校验当前实际加载的语言。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

消息更新遵循工作区语言选择。

依据见 [提交 080b7897](https://github.com/MaojieXu/AstroPhotoFlow/commit/080b78977a9625287e5c39c72b91bd6200402ce1)。 相关笔记见 [使用 workspace 级中英语言](../feature/2026-10-30-workspace-locale.md)。
