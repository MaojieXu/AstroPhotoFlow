# Agent Note: 优化 FITS 采样并保持结果一致

Status: Implemented

## Problem

FITS 缩略图采样有性能成本，改变抽样会影响显示。

## Decision

优化相同像素样本的读取路径，核对与旧采样等价。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

性能改动以相同采样结果为边界。

依据见 [提交 c84f1a3b](https://github.com/MaojieXu/AstroPhotoFlow/commit/c84f1a3bb2f2698338543aa09ba93e95c885d034)。
