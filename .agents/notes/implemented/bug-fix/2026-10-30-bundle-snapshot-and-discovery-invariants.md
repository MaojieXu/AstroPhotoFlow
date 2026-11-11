# Agent Note: 固定安装快照与发布发现不变量

Status: Implemented

## Problem

元数据读取与完整 checkout 存在换行差异，失败信息也需随工作区语言显示。

## Decision

按内容语义核对安装快照，保留真实内容变化的拒绝路径，并修正版本发现及本地化边界。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

合法换行差异和包身份变化分别处理，诊断仍可追溯。

依据见 [提交 4a84d95a](https://github.com/MaojieXu/AstroPhotoFlow/commit/4a84d95a9880efa19b3f4088399454e51626f3a7)、[test-matrix.md L2121](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L2121)。 相关笔记见 [发现并确认官方 Bundle 固定版本](../feature/2026-10-30-official-bundle-version-selection.md)。
