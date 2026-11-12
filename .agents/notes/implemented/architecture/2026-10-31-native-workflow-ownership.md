# Agent Note: 取消自研工作流生命周期与完整图副本

Status: Implemented

## Problem

自研图管理、运行库和先保存准入与 ComfyUI 原生能力重复。

## Decision

把可编辑图、草稿、队列、历史和取消交由 ComfyUI。调用归 software，已检查科学结果归 data，跨模块桥接归 interfaces。

## Alternatives considered

10 月 27 日 ADR 曾规划项目图关联、完整运行记录、保存前置及接管。

## Consequences

旧计划在现代化中取消。未保存草稿、取消和选中结果沿用各自原生或领域机制。

依据见 [提交 679be0cf](https://github.com/MaojieXu/AstroPhotoFlow/commit/679be0cf93b5dabbd25e59ca6375777f5277b111)、[WORKBENCH-WORKFLOWS-0058-native-workflow-execution-and-agent-interaction.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/frontend/docs/adr/WORKBENCH-WORKFLOWS-0058-native-workflow-execution-and-agent-interaction.md)、[WORKBENCH-WORKFLOWS-0059-native-editing-save-and-agent-target.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/frontend/docs/adr/WORKBENCH-WORKFLOWS-0059-native-editing-save-and-agent-target.md)、[提交 9e27ef51](https://github.com/MaojieXu/AstroPhotoFlow/commit/9e27ef51134ac140b447e3a2ff8c2e9a6c85dd0d)。 相关笔记见 [确立五模块架构基线](2026-10-27-five-module-baseline.md)、[取消接管往返并直接编辑当前画布](../simplification/2026-10-30-direct-local-canvas-edit.md)。
