# Agent Note: 以官方 FastMCP 和生成 CLI 共用领域能力

Status: Implemented

## Problem

多个外部入口若各自手写协议，参数和错误会漂移。

## Decision

以官方 FastMCP 注册工具，CLI 从工具契约生成，两者经 HTTP 客户端复用领域服务。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

协议实测与生成目录分开验证。

依据见 [提交 679be0cf](https://github.com/MaojieXu/AstroPhotoFlow/commit/679be0cf93b5dabbd25e59ca6375777f5277b111)、[test-matrix.md L902](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L902)。 相关笔记见 [用统一客户端开放素材库](../feature/2026-10-25-shared-library-client-cli-mcp.md)。
