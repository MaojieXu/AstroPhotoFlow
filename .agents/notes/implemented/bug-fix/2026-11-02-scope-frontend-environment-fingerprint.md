# Agent Note: 限定前端环境输入指纹范围

Status: Implemented

## Problem

构建目录之外的环境输入可错误影响复用判断。

## Decision

将前端环境输入范围收敛到实际构建目录。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

复用指纹与构建所读取的环境一致。

依据见 [提交 b9a1a017](https://github.com/MaojieXu/AstroPhotoFlow/commit/b9a1a017a4e3dce243b2ede6e110b55b3beb94e5)。 相关笔记见 [复用检查忽略非构建换行差异](2026-11-02-ignore-non-build-newline-differences.md)。
