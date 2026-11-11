# Agent Note: 保留 Bundle 编辑并清理不可用目录项

Status: Implemented

## Problem

包更新可能覆盖有效编辑或继续显示已不可用节点。

## Decision

热更新保留相应编辑，并从派生目录移除不可用入口。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

当前节点目录反映实际可用包，已有图内容按各自边界保留。

依据见 [提交 52da8319](https://github.com/MaojieXu/AstroPhotoFlow/commit/52da83199a86e09ce38354503e25f99e4c2ca18a)。
