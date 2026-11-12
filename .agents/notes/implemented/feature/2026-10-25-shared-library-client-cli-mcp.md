# Agent Note: 用统一客户端开放素材库

Status: Implemented

## Problem

网页、脚本和 Agent 需要使用相同素材操作。

## Decision

通过共享客户端暴露结构化 CLI 和 MCP 素材库操作。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

接口复用领域服务，后续继续细化扫描、确认和状态查询。

依据见 [提交 4dd11873](https://github.com/MaojieXu/AstroPhotoFlow/commit/4dd11873894baf07dc69a8e359947903a4adffb8)。 相关笔记见 [以单张素材工具验证 MCP 接入](2026-10-24-single-photo-mcp.md)。
