# Agent Note: 以明确素材范围完成导入与校准管理

Status: Implemented

## Problem

文件扫描、导入、校准和修正需要能按实际固定素材调用。

## Decision

增加结构化图像管理能力，保存请求标识、明确文件集合和固定版本，查询导入及校准状态。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

验证包含已知冲突、复制失败恢复和补发布。合成素材的结果不外推为科学验收。

依据见 [提交 ae43fe41](https://github.com/MaojieXu/AstroPhotoFlow/commit/ae43fe41e80cbed621c4fbc51c9418f64b2746f0)、[test-matrix.md L61](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L61)。 相关笔记见 [素材 MCP 支持整夜确认导入](2026-10-30-confirmed-night-import-and-aggregate-wait.md)。
