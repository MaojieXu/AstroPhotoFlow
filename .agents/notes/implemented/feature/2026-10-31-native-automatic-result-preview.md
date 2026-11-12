# Agent Note: 复用原生队列自动计算预览结果

Status: Implemented

## Problem

用户希望在目标明确时直接看到节点完成结果。

## Decision

由操作声明自动结果资格，按显式目标及支持的依赖链接入原生执行。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

未声明资格的操作保持普通运行行为，科学文件仍需显式保存。

依据见 [提交 c1392711](https://github.com/MaojieXu/AstroPhotoFlow/commit/c139271125f49584313ef883c7250062e14cc85e)、[提交 6d2bba1b](https://github.com/MaojieXu/AstroPhotoFlow/commit/6d2bba1b1ea0e274785db9b0dbb000ddd2f544e7)、[提交 bbb6f4a9](https://github.com/MaojieXu/AstroPhotoFlow/commit/bbb6f4a9f872fc1b79defa6dddf849247b5099d6)。
