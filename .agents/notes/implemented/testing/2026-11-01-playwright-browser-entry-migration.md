# Agent Note: 统一真实浏览器测试为 Playwright

Status: Implemented

## Problem

旧手动脚本及默认入口残留，使收尾核对过早。

## Decision

将有效断言迁入 Playwright fixture 和统一入口，使用受控 workspace、trace 及独立用例。

## Alternatives considered

旧脚本作为历史审计证据，不保留可执行兼容入口。

## Consequences

原生队列和重启使用显式开关，skip 与实际通过分别统计。

依据见 [提交 679be0cf](https://github.com/MaojieXu/AstroPhotoFlow/commit/679be0cf93b5dabbd25e59ca6375777f5277b111)、[browser-test-migration.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/browser-test-migration.md)、[test-matrix.md L122](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L122)。
