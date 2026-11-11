# Agent Note: 保存 workspace 配置

Status: Implemented

## Problem

用户需要在工作台配置本机 workspace。

## Decision

实现 B11 的 workspace 配置管理，把保存值与实际启动采用值分开。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

保存配置与服务启停是两个操作。

依据见 [提交 6b10657f](https://github.com/MaojieXu/AstroPhotoFlow/commit/6b10657f1904baea4237d3b8ff2b1e454e59198f)、[test-matrix.md L1864](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L1864)。
