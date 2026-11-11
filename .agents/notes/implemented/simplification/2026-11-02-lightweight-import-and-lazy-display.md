# Agent Note: 导入与派生预览解耦

Status: Implemented

## Problem

完整预生成阻塞科学导入，也可能改写旧任务的显示历史。

## Decision

扫描缓存源事实，按来源戳复用。导入不等待预览，组封面优先，其余按需并发合并生成。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

预览错误不改变科学导入事实，后续查看也不回填旧任务的历史状态。

依据见 [提交 ae43fe41](https://github.com/MaojieXu/AstroPhotoFlow/commit/ae43fe41e80cbed621c4fbc51c9418f64b2746f0)、[test-matrix.md L32](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L32)。 相关笔记见 [先登记导入，再受控处理](../architecture/2026-10-25-register-before-import-processing.md)。
