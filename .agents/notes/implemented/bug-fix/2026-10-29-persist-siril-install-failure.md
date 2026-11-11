# Agent Note: 持久保存 Siril 安装的真实失败

Status: Implemented

## Problem

Windows 目录移动失败后，类型化错误被普通字典替代，导致任务失败而磁盘仍显示 running。

## Decision

调整安装发布与终态记录，保留类型化错误及部分安装事实，并在最终位置核对程序版本。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

原记录未证明真实重装通过。后来短时 Windows 句柄导致的替换问题另行修复。

依据见 [提交 5bcb4430](https://github.com/MaojieXu/AstroPhotoFlow/commit/5bcb4430fa8eda3a7eb56f7bc07a09ce3e2efd28)、[test-matrix.md L1475](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L1475)。
