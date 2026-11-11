# Agent Note: 为 Siril 原生执行创建本地 HTTP 会话

Status: Implemented

## Problem

跨事件循环复用网页服务会话导致原生处理报 Timeout context manager 错误。

## Decision

在执行循环内创建、使用和关闭对应 HTTP 会话。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

原历史候选完成语法、构建和隔离更新，当时未执行自动测试或真实 Siril 科学处理。

依据见 [提交 5bcb4430](https://github.com/MaojieXu/AstroPhotoFlow/commit/5bcb4430fa8eda3a7eb56f7bc07a09ce3e2efd28)、[test-matrix.md L1482](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L1482)。
