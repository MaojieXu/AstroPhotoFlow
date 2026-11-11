# Agent Note: 保护 bootstrap 状态并同步网页产物

Status: Implemented

## Problem

运行中实例可能与候选依赖或网页产物不一致。

## Decision

检查准备状态与实例占用，并按 workspace 同步匹配的前端资产。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

准备入口能报告冲突，避免悄悄把现有运行态当作新候选。

依据见 [提交 3c76ab50](https://github.com/MaojieXu/AstroPhotoFlow/commit/3c76ab50dcde0d3df3eb909604481f48dbd3d10c)。
