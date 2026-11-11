# Agent Note: 修正中文设备删除预检检索

Status: Implemented

## Problem

中文查询未稳定找到设备删除预检。

## Decision

修正删除预检的检索文本并同步生成目录。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

预检可经相应中文词找到，实际删除仍使用单独的明确确认。

依据见 [提交 dcfe6939](https://github.com/MaojieXu/AstroPhotoFlow/commit/dcfe693974185a02609ddd345246b64afbe01f5a)、[test-matrix.md L2446](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L2446)。 相关笔记见 [用类型化 MCP 工具登记设备](../feature/2026-11-02-typed-equipment-management-tools.md)。
