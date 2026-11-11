# Agent Note: 在现有素材表显示校准列

Status: Implemented

## Problem

独立校准卡片和重复成员表需要用户来回查找。

## Decision

采用素材表内的校准列，组显示统一或混合状态，成员及独立图可就地选择。

## Alternatives considered

独立卡片、重复表与搭配筛选被用户最终选择替代。

## Consequences

历史成员保持只读，编辑以起始 revision 检查冲突。

依据见 [提交 ae43fe41](https://github.com/MaojieXu/AstroPhotoFlow/commit/ae43fe41e80cbed621c4fbc51c9418f64b2746f0)、[test-matrix.md L16](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L16)。
