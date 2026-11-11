# Agent Note: 托管发布前拒绝已变动的源文件

Status: Implemented

## Problem

扫描与发布之间源文件可能被替换或改写。

## Decision

发布托管原件前核对源文件变化，检测不一致时拒绝发布。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

任务恢复需要重新核对实际输入。

依据见 [提交 a6370d37](https://github.com/MaojieXu/AstroPhotoFlow/commit/a6370d3709c2a269f67870f4df5182fabc195f60)、[提交 c7698c88](https://github.com/MaojieXu/AstroPhotoFlow/commit/c7698c88d8b2c1876fbf7042573c1bf8b4fea92d)。
