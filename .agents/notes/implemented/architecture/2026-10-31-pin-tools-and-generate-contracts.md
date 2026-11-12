# Agent Note: 固定工具版本与接口生成链

Status: Implemented

## Problem

现代化横跨 Python、前端和 Agent 入口，手抄契约容易失配。

## Decision

固定工具版本，维护 OpenAPI、MCP、CLI 和前端 SDK 的统一生成路径。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

生成快照应与实际实现一起核对。10 月 31 日开始记录，11 月 1 日集成。

依据见 [提交 679be0cf](https://github.com/MaojieXu/AstroPhotoFlow/commit/679be0cf93b5dabbd25e59ca6375777f5277b111)、[test-matrix.md L1190](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L1190)、[test-matrix.md L933](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L933)。
