# Agent Note: 登记前只读检查扫描素材的校准条件

Status: Implemented

## Problem

Agent 在导入前要发现未知字段和校准冲突。

## Decision

复用分类与派生规则，对已扫描文件执行不落库的校准预检，返回需明确确认的范围。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

未知、已知冲突和已确认选择分别表达，预检不自动登记或处理素材。

依据见 [提交 ae43fe41](https://github.com/MaojieXu/AstroPhotoFlow/commit/ae43fe41e80cbed621c4fbc51c9418f64b2746f0)、[test-matrix.md L32](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L32)。 相关笔记见 [以明确素材范围完成导入与校准管理](2026-11-02-explicit-image-library-mcp-workflows.md)。
