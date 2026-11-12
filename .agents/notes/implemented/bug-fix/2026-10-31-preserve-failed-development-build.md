# Agent Note: 保留失败开发包构建证据

Status: Implemented

## Problem

失败构建若立即清理，就缺少诊断信息。

## Decision

保留失败构建及其可检查回执。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

失败仍报告失败，调试能查到该次构建证据。

依据见 [提交 1cd41759](https://github.com/MaojieXu/AstroPhotoFlow/commit/1cd4175923d7204451cacc4f2bc53aa927fa2f1a)。 相关笔记见 [在 workspace 绑定开发版 Bundle 源码](../feature/2026-10-31-workspace-development-bundle-binding.md)。
