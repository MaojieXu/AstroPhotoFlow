# Agent Note: 先登记导入，再受控处理

Status: Implemented

## Problem

大批素材处理需要可见进度和可恢复任务，同时限制后台工作量。

## Decision

先登记素材和任务，再运行有界的内容处理及预览生成。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

素材登记、原件就绪和预览就绪分别观察。

依据见 [提交 4448b372](https://github.com/MaojieXu/AstroPhotoFlow/commit/4448b3726aa922f07fd7d7020c55621029046d3a)、[提交 a5b87e09](https://github.com/MaojieXu/AstroPhotoFlow/commit/a5b87e095de2ba68b4db9fcc9c4c1b8cbec95733)。
