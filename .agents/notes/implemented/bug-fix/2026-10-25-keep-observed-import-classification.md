# Agent Note: 省略导入字段时保留观测分类

Status: Implemented

## Problem

调用方省略字段时，默认值可能覆盖已识别的分类。

## Decision

保留文件观测得到的分类，只有显式给值时才按对应契约处理。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

省略与覆盖具有不同含义。

依据见 [提交 834f08bf](https://github.com/MaojieXu/AstroPhotoFlow/commit/834f08bf53067c9cc86df08acceea0685604ea27)。
