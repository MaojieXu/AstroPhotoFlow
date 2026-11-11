# Agent Note: 以单一控制入口管理双服务生命周期

Status: Implemented

## Problem

启动、停止和重启需要处理占用、并发和未知结果。

## Decision

沿用两个本机服务和文件回执，通过 core 串行控制同一 workspace，维护前检查活动任务和原生队列。

## Alternatives considered

M1 ADR 采用现有进程和状态记录，未引入第三个常驻控制服务。

## Consequences

保存值、实际采用值和运行状态分开。网页配置的表现形式随后迁入原生侧栏。

依据见 [提交 c23e10de](https://github.com/MaojieXu/AstroPhotoFlow/commit/c23e10de49053541298c69ea8c7416014294fae1)、[WORKBENCH-FOUNDATION-0062-configuration-and-lifecycle.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/frontend/docs/adr/WORKBENCH-FOUNDATION-0062-configuration-and-lifecycle.md)。
