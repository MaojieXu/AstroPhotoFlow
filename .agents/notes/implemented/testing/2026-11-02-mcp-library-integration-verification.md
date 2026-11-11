# Agent Note: 隔离核对 MCP 重载与素材库集成

Status: Implemented

## Problem

合入前需要区分工具协议、导入、迁移与页面媒体行为的证据。

## Decision

分开复核 MCP／设备、导入／校准和媒体预览，并用私有 workspace 运行定向检查及实际 MCP 重连。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

历史记录指出正常 dev 库未迁移，测试数有重叠，未验全部 Siril 操作或用户素材。

依据见 [提交 a3857c74](https://github.com/MaojieXu/AstroPhotoFlow/commit/a3857c745b63d830800dfe49362a39480fe69788)、[test-matrix.md L2446](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L2446)。
