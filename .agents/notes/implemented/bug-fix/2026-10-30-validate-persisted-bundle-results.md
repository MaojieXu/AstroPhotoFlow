# Agent Note: 以 JSON 契约读取已持久化 Bundle 结果

Status: Implemented

## Problem

已持久化内容和内存对象的表示不同。

## Decision

读取持久结果时走 JSON 校验路径。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

历史结果读回与写入所用契约一致。

依据见 [提交 e322d074](https://github.com/MaojieXu/AstroPhotoFlow/commit/e322d0744db82d26fb1b138e0818b75d1fdcbbe1)。
