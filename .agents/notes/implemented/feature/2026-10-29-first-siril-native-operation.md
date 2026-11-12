# Agent Note: 以 Siril Auto Stretch 接通首个原生科学操作

Status: Implemented

## Problem

平台需要验证软件包、固定科学输入和原生队列的首个闭环。

## Decision

采用 Siril 1.4.4 Auto Stretch，固定科学引用由 data 解析，操作生成新的科学输出，显示预览另行生成。

## Alternatives considered

复用原生队列及取消，从已有 CLI 原型和操作定义切入。

## Consequences

首节点使用窄的原生调用适配。它不代表完整调用库、节点覆盖或真实用户素材验收。

依据见 [提交 5bcb4430](https://github.com/MaojieXu/AstroPhotoFlow/commit/5bcb4430fa8eda3a7eb56f7bc07a09ce3e2efd28)、[WORKBENCH-SOFTWARE-0065-first-siril-native-operation.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/frontend/docs/adr/WORKBENCH-SOFTWARE-0065-first-siril-native-operation.md)、[WORKBENCH-SOFTWARE-0056-bundled-software-nodes.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/frontend/docs/adr/WORKBENCH-SOFTWARE-0056-bundled-software-nodes.md)。 相关笔记见 [区分科学数据与显示预览](../architecture/2026-10-22-separate-science-and-display.md)。
