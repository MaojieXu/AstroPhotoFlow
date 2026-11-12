# Agent Note: Bundle SDK v2 使用具名输入和结果

Status: Implemented

## Problem

完整 Siril 目录需要多输入、多输出及结构化评估。

## Decision

用具名输入、结果和分析元数据接入 SDK v2，平台从包声明读取操作和节点。

## Alternatives considered

早期 SDK v1 与首个固定节点只能覆盖更窄的交互。

## Consequences

10 月 30 日集成。160 节点和命令目录覆盖是接入规模，未逐项完成科学验收。

依据见 [提交 0f53b719](https://github.com/MaojieXu/AstroPhotoFlow/commit/0f53b719584ec68a8dd277c27713fde84e084a7c)、[提交 a7eaf242](https://github.com/MaojieXu/AstroPhotoFlow/commit/a7eaf2421c7b31e8b9aee20341dc7e601f59d4fe)、[提交 b625045c](https://github.com/MaojieXu/AstroPhotoFlow/commit/b625045c388953ac9dc4b28ec5d1a318385ac239)。 相关笔记见 [以 Siril Auto Stretch 接通首个原生科学操作](../feature/2026-10-29-first-siril-native-operation.md)。
