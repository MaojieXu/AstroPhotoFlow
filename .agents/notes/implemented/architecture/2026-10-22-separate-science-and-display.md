# Agent Note: 区分科学数据与显示预览

Status: Implemented

## Problem

显示增强后的像素可能被误作下一步科学输入。

## Decision

初版需求约定科学链路传递 FITS 或科学数据引用，显示预览独立派生。

## Alternatives considered

把通用图像数据作为两条链路的共同输入会丢失科学约束。

## Consequences

首日文档确立了边界。后续素材库、Siril 与查看器各自实现其对应部分。

依据见 [提交 39a8bee4](https://github.com/MaojieXu/AstroPhotoFlow/commit/39a8bee4c85c8a9b38f2bf9356cd5234f3cebed2)、[README.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/39a8bee4c85c8a9b38f2bf9356cd5234f3cebed2/docs/AstroPhotoFlow_Requirements_v1.0/README.md)。
