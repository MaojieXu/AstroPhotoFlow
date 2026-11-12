# Agent Note: 核对原生自动队列回执

Status: Implemented

## Problem

自动提交与运行状态返回之间可能发生竞态。

## Decision

依据同一次原生执行核对回执，避免误认运行状态。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

无法确认时继续查询实际执行状态。

依据见 [提交 1cd41759](https://github.com/MaojieXu/AstroPhotoFlow/commit/1cd4175923d7204451cacc4f2bc53aa927fa2f1a)。 相关笔记见 [复用原生队列自动计算预览结果](../feature/2026-10-31-native-automatic-result-preview.md)。
