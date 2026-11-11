# Agent Note: 按阶段测量导入耗时

Status: Implemented

## Problem

导入总耗时无法定位瓶颈。

## Decision

为导入阶段分别测量耗时，记录基准输入和各阶段开销。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

后续优化可以对照阶段耗时，不能把一次测量推广到其他素材。

依据见 [提交 c84f1a3b](https://github.com/MaojieXu/AstroPhotoFlow/commit/c84f1a3bb2f2698338543aa09ba93e95c885d034)。
