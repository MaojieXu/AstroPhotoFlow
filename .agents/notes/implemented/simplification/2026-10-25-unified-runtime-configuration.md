# Agent Note: 统一运行配置与 workspace

Status: Implemented

## Problem

旧工作空间路径和运行配置重复。

## Decision

收敛运行配置入口并退役旧 workspace 机制。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

开发隔离与工作台生命周期使用统一路径体系。

依据见 [提交 940f49e0](https://github.com/MaojieXu/AstroPhotoFlow/commit/940f49e038bffb6a150831b3397f917f7d6fe70e)。
