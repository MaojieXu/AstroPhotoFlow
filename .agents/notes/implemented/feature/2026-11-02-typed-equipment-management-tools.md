# Agent Note: 用类型化 MCP 工具登记设备

Status: Implemented

## Problem

聊天输入需要通过可验证工具登记器材，避免在模型层直接改数据。

## Decision

按设备类别提供类型化登记、修改与删除预检，沿用 HTTP 和 data 服务。

## Alternatives considered

前期候选曾使用不同数量的工具和独立预设工具，最终按合入目录为准。

## Consequences

部分参数、同名设备和未知写入结果在隔离环境核对。历史目录数量随候选而变。

依据见 [提交 ae43fe41](https://github.com/MaojieXu/AstroPhotoFlow/commit/ae43fe41e80cbed621c4fbc51c9418f64b2746f0)、[test-matrix.md L75](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L75)。
