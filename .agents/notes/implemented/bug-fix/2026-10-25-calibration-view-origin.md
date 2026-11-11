# Agent Note: 校准创建结果留在发起视图

Status: Implemented

## Problem

校准异步创建结束时，用户可能已经切到其他视图。

## Decision

保持创建请求与发起视图绑定。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

完成结果只作用于对应的视图。

依据见 [提交 11a267f9](https://github.com/MaojieXu/AstroPhotoFlow/commit/11a267f99e881984b1cd6f56f98b43393267445c)。
