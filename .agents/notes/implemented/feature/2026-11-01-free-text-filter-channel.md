# Agent Note: 滤镜 Channel 采用自由文本

Status: Implemented

## Problem

通道值既有常见缩写，也有组合和非标准波段。

## Decision

让滤镜 Channel 可手填，组合标签展示通道与可选带宽，选择器保留实际名称。

## Alternatives considered

固定枚举会遗漏用户器材和波段命名。

## Consequences

通道标签便于辨认，旧设备资料保持可追溯。

依据见 [提交 679be0cf](https://github.com/MaojieXu/AstroPhotoFlow/commit/679be0cf93b5dabbd25e59ca6375777f5277b111)、[test-matrix.md L2265](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L2265)。
