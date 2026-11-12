# Agent Note: 用真实 MCP 进程验证重载和显式重连

Status: Implemented

## Problem

工具描述更新需要通过实际连接确认。

## Decision

在隔离服务上用 stdio、HTTP watcher 和 Inspector 验证进程替换、工具新增删除及参数变更。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

验证使用合成探针，不证明原会话透明刷新或真实素材验收。

依据见 [提交 ae43fe41](https://github.com/MaojieXu/AstroPhotoFlow/commit/ae43fe41e80cbed621c4fbc51c9418f64b2746f0)、[test-matrix.md L89](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L89)。 相关笔记见 [为私有 workspace 接入 FastMCP 热重载](../feature/2026-11-02-isolated-fastmcp-development-reload.md)。
