# Agent Note: 共享模块契约与隔离工作空间

Status: Implemented

## Problem

并行开发要避免端口、运行资源与数据相互干扰。

## Decision

建立共享模块契约和隔离 workspace，并在开发记录里分开源码、运行环境与实际验证。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

可在私有 workspace 验证模块，隔离验证与默认实例的实际状态分开。

依据见 [提交 3f72b71c](https://github.com/MaojieXu/AstroPhotoFlow/commit/3f72b71ca2b4e3a13aad7bc0ef4893008906a325)、[提交 0664ea73](https://github.com/MaojieXu/AstroPhotoFlow/commit/0664ea7358d4b7b7f3f9d027b1b6edf2a452d2aa)。
