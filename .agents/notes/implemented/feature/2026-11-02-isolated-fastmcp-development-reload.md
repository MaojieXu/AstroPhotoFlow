# Agent Note: 为私有 workspace 接入 FastMCP 热重载

Status: Implemented

## Problem

开发工具需要在保留真实领域服务的同时快速刷新定义。

## Decision

新增 pnpm dev:mcp，显式绑定私有 workspace，只监听源码与回环接口。

## Alternatives considered

使用官方 FastMCP watcher 和 Inspector，避免额外常驻控制进程。

## Consequences

重载后显式重连。实际验证工具目录、参数变化与新 worker，未宣称聊天会话自动更新。

依据见 [提交 ae43fe41](https://github.com/MaojieXu/AstroPhotoFlow/commit/ae43fe41e80cbed621c4fbc51c9418f64b2746f0)、[test-matrix.md L89](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L89)。
