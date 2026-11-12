# Agent Note: 处理极速完成队列与已连接 Data 输入

Status: Implemented

## Problem

原生队列可能在观察开始前就完成，自动结果也必须沿用真实连线输入。

## Decision

保留快速完成的原生执行回执，并使用连接的 Data 自动输入。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

自动预览沿原生队列关联实际输入与完成状态。

依据见 [提交 2a1b98cd](https://github.com/MaojieXu/AstroPhotoFlow/commit/2a1b98cdb9dd26c39d79886525a567e1a7456b63)。 相关笔记见 [核对原生自动队列回执](2026-10-31-reconcile-automatic-queue-receipts.md)。
