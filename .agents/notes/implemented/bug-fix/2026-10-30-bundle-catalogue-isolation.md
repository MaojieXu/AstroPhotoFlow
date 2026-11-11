# Agent Note: 隔离完整 Bundle 目录

Status: Implemented

## Problem

扩大 Bundle 目录后，安装状态及目录上下文不能互相混入。

## Decision

收紧目录隔离，并覆盖包状态差异的回归。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

目录发现与实际就绪状态维持各自归属。

依据见 [提交 b15b6088](https://github.com/MaojieXu/AstroPhotoFlow/commit/b15b6088f89102a157c07963fa8a3861673d5434)。
