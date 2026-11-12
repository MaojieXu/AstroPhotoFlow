# Agent Note: 按真实原生扩展回调测试重载

Status: Implemented

## Problem

测试替身回调形态与原生扩展契约不一致。

## Decision

把热加载回归改为使用实际扩展回调形态。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

测试验证真实接入契约，而非宽松替身。

依据见 [提交 ee11164e](https://github.com/MaojieXu/AstroPhotoFlow/commit/ee11164eaf3b90e6ca2124ff2fa15a4338192ed8)。
