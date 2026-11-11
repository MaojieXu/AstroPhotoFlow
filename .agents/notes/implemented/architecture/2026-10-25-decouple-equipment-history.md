# Agent Note: 设备当前记录与历史快照分离

Status: Implemented

## Problem

编辑设备不应重写过去导入素材的设备事实。

## Decision

把设备管理的当前状态与素材所持设备历史快照解耦。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

后续设备精简可更改当前表单，同时保持既有科学记录。

依据见 [提交 3c3779aa](https://github.com/MaojieXu/AstroPhotoFlow/commit/3c3779aa128adb0650af855941ba04cc7eb0cc97)。
