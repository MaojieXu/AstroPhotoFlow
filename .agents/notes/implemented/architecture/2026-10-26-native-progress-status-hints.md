# Agent Note: 复用原生进度与状态提示

Status: Implemented

## Problem

领域服务和原生队列分属两个进程，显示状态需保留事实来源。

## Decision

采用原生进度和事件，事件作为变化提示，重连或收到提示后查询模块状态。

## Alternatives considered

ADR 选择先验证最小受控桥接，再决定是否需要其他通知通道。

## Consequences

设计于 10 月 26 日确认。后续原生节点接入逐项验证，事件不能代替提交和运行回执。

依据见 [提交 9d4c729c](https://github.com/MaojieXu/AstroPhotoFlow/commit/9d4c729cb35cf961c34fa50cf55616cd6c2e4b10)、[WORKBENCH-FOUNDATION-0046-native-progress-and-status-reuse.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/frontend/docs/adr/WORKBENCH-FOUNDATION-0046-native-progress-and-status-reuse.md)。
