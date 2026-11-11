# Agent Note: 元数据重试保留文件 CFA 优先级

Status: Implemented

## Problem

重试元数据处理时，预设有机会覆盖原件已声明的 CFA。

## Decision

让重试沿用导入时的文件 CFA 优先级。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

重试与初次处理得到相同的元数据优先级。

依据见 [提交 21542574](https://github.com/MaojieXu/AstroPhotoFlow/commit/215425743387dd8fd56ed7208cbcfa30e3947e60)。
