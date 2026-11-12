# Agent Note: 采用 workspace 节点定义与实际加载事实

Status: Implemented

## Problem

可重用节点需要明确来源、更新内容和加载状态。

## Decision

落地 workspace JSON 定义及由 Bundle 派生的目录，发现经公开接口。

## Alternatives considered

旧 ADR 另设完整测试历史的替代是读取实际运行与加载事实。

## Consequences

当时的通用编辑器、完整端口重映射和全部节点更新场景仍待验证。

依据见 [提交 679be0cf](https://github.com/MaojieXu/AstroPhotoFlow/commit/679be0cf93b5dabbd25e59ca6375777f5277b111)、[WORKBENCH-NODES-0057-shared-editable-node-definitions.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/frontend/docs/adr/WORKBENCH-NODES-0057-shared-editable-node-definitions.md)、[current-context.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/current-context.md)。
