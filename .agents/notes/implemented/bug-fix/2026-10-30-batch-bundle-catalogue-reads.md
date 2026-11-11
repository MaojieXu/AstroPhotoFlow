# Agent Note: 按请求合并 Bundle 目录读取

Status: Implemented

## Problem

全量节点读取可能重复加载同一包目录。

## Decision

在请求内合并读取。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

目录规模增长时减少冗余读取，隔离仍按请求维持。

依据见 [提交 959c6994](https://github.com/MaojieXu/AstroPhotoFlow/commit/959c699449ef6768d9200a6659a0af527571e497)。
