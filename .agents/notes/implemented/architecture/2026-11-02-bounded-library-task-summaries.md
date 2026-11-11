# Agent Note: 用独立摘要读取导入任务列表

Status: Implemented

## Problem

任务列表不需要加载全部来源、报告和逐项详情。

## Decision

为列表使用摘要查询，进度与分页项汇总由服务读取，完整数据留在详情。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

HTTP、CLI 和 MCP 共享摘要，后台刷新不重复清空已确认页面。

依据见 [提交 ae43fe41](https://github.com/MaojieXu/AstroPhotoFlow/commit/ae43fe41e80cbed621c4fbc51c9418f64b2746f0)、[test-matrix.md L2391](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L2391)。
