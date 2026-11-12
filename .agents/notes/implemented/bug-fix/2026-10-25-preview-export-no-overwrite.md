# Agent Note: 预览导出保留已有文件

Status: Implemented

## Problem

导出预览可能与目标目录里的既有文件重名。

## Decision

修改导出写入规则以保护既有文件。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

已有文件不会因预览导出被静默覆盖。

依据见 [提交 81a1149c](https://github.com/MaojieXu/AstroPhotoFlow/commit/81a1149ccb6480ae5f688ad1d04752b993268c21)。
