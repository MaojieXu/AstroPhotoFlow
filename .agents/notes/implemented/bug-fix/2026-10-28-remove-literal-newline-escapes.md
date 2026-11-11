# Agent Note: 修正 M2 源码中的字面换行转义

Status: Implemented

## Problem

部分 M2 文件写入了字面转义，影响源码解析。

## Decision

移除错误的字面换行转义。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

修复限定于源码表示，与业务行为更新分开。

依据见 [提交 15f74c29](https://github.com/MaojieXu/AstroPhotoFlow/commit/15f74c29d6ba2350ba0a1be8d5944430dd6ab23d)。
