# Agent Note: 用合成 Bundle 验证通用命令契约

Status: Implemented

## Problem

Siril 特化清理后需要证明平台可传递其他包的实际事实。

## Decision

修正合成参数、示例和媒体夹具，并验证 HTTP、客户端和 FastMCP 对非 Siril 包的名称、版本及评估保真。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

测试覆盖平台协议，不能据此宣称独立软件科学运行已验。

依据见 [提交 fe642105](https://github.com/MaojieXu/AstroPhotoFlow/commit/fe642105a725fda1ce3b7830980c2c374da6cccb)、[提交 3b43b043](https://github.com/MaojieXu/AstroPhotoFlow/commit/3b43b0430368b7433d00f55c3b7bdd4f8bcebf1e)。 相关笔记见 [明确文件归属并解除平台的 Siril 特例](../architecture/2026-11-01-file-ownership-and-siril-decoupling.md)。
