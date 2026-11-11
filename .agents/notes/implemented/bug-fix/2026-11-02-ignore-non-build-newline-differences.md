# Agent Note: 复用检查忽略非构建换行差异

Status: Implemented

## Problem

非构建文件的 checkout 换行变化造成无意义的复用拒绝。

## Decision

把这类换行差异排除在前端产物匹配条件之外。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

实际构建输入变化仍影响匹配。

依据见 [提交 f4468f14](https://github.com/MaojieXu/AstroPhotoFlow/commit/f4468f14efeb6d6f52f7a2e3974b6f8e0499895d)。 相关笔记见 [复用已核验的前端产物和包缓存](../process/2026-11-02-reuse-verified-frontend-builds.md)。
