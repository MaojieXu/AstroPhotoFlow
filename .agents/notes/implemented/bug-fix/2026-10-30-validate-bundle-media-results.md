# Agent Note: 验证 Bundle 媒体结果

Status: Implemented

## Problem

适配器返回内容需要与平台可消费的媒体结果契约一致。

## Decision

核对 Bundle 返回的媒体结果及元数据。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

无效媒体结果保持可诊断，无法以返回对象冒充合格输出。

依据见 [提交 b15b6088](https://github.com/MaojieXu/AstroPhotoFlow/commit/b15b6088f89102a157c07963fa8a3861673d5434)。
