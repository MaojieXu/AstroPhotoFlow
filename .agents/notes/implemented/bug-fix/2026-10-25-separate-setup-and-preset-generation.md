# Agent Note: 分离组合选择与预设刷新

Status: Implemented

## Problem

同一刷新代次会把组合选择与预设请求绑在一起。

## Decision

分别跟踪组合选择和预设重新加载。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

晚返回的预设请求不会干扰后续选择。

依据见 [提交 dd4ad8f0](https://github.com/MaojieXu/AstroPhotoFlow/commit/dd4ad8f0b18cba88426aa79d089cee1bc123d5af)。
