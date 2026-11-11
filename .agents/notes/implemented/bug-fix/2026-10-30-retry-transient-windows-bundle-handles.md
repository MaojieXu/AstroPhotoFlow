# Agent Note: 处理 Windows 暂占句柄的 Bundle 替换

Status: Implemented

## Problem

版本探测或系统扫描可短时持有程序文件句柄。

## Decision

仅对观察到的 Windows 暂时占用错误做有限重试。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

瞬时占用可恢复，持续错误继续报告失败。

依据见 [提交 30d6d947](https://github.com/MaojieXu/AstroPhotoFlow/commit/30d6d947562d220f8629b0bc7b2591bc3219c538)。
