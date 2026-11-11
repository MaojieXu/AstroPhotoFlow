# Agent Note: 固定 Windows bootstrap 并拆分准备阶段

Status: Implemented

## Problem

工作树准备混合工具发现、依赖安装、网页构建和服务启动。

## Decision

新增 Windows x64 PowerShell 入口校验工具，并将准备工作转给 Python。按 workspace 记录分阶段回执。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

可按需构建、复用网页或启动双服务。冷缓存与 WSL 验收独立记录。

依据见 [提交 242b6133](https://github.com/MaojieXu/AstroPhotoFlow/commit/242b6133257fb3d9230d82527caaf7c032536125)、[提交 ccee0da2](https://github.com/MaojieXu/AstroPhotoFlow/commit/ccee0da2b6229cdc934166ad3f3fa20de36d19f6)、[test-matrix.md L2081](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L2081)。 相关笔记见 [首轮 Windows CPU 工作台交付](2026-10-23-windows-first-workbench.md)。
