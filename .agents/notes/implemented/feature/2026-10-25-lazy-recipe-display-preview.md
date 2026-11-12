# Agent Note: 按需生成固定配方显示预览

Status: Implemented

## Problem

浏览组成员时预生成所有大图的成本高。

## Decision

在共享 worker 上按需生成固定显示配方的约 1080 像素预览，由预览缓存管理产物。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

随后针对原始分辨率细节采用按需区域读取。

依据见 [提交 8ad0f119](https://github.com/MaojieXu/AstroPhotoFlow/commit/8ad0f119d372155827c0614b7eb60486329903df)。 相关笔记见 [组浏览只用缩略图并共享拉伸](../simplification/2026-10-24-group-thumbnail-shared-stretch.md)。
