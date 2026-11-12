# Agent Note: 修复 Siril 节点元数据引起的空白画布

Status: Implemented

## Problem

实际 object_info 中 python_module 为 null，原生节点构造按字符串读取时失败。

## Decision

从 V3 节点元数据生产端提供模块身份，保持宿主字符串契约。

## Alternatives considered

选择修正生产方，未给前端增加跳过节点的容错分支。

## Consequences

记录包含语法、构建和元数据检查，原条目中的新增自动测试未执行。

依据见 [提交 5bcb4430](https://github.com/MaojieXu/AstroPhotoFlow/commit/5bcb4430fa8eda3a7eb56f7bc07a09ce3e2efd28)、[test-matrix.md L1498](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L1498)。
