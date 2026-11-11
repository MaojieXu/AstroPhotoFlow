# Agent Note: 素材 MCP 支持整夜确认导入

Status: Implemented

## Problem

外部 Agent 要处理整晚目录，并明确实际文件和完成状态。

## Decision

通过统一的 HTTP／CLI／MCP 领域能力提供递归扫描、明确选择及聚合等待。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

发现、确认、执行和回执分别可核对，不由扫描推断用户批准。

依据见 [提交 55484461](https://github.com/MaojieXu/AstroPhotoFlow/commit/55484461b2f9cbccfe404a3b9f9f58d903f3ce71)、[提交 974347a3](https://github.com/MaojieXu/AstroPhotoFlow/commit/974347a3d14379c25ab06e16b54fb8423b22629b)。 相关笔记见 [用统一客户端开放素材库](2026-10-25-shared-library-client-cli-mcp.md)。
