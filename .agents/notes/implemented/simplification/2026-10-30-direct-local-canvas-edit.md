# Agent Note: 取消接管往返并直接编辑当前画布

Status: Implemented

## Problem

按用户明确指令编辑同一在线画布时，额外接管和交回步骤增加操作成本。

## Decision

Agent 编辑使用实际在线目标和明确的内容校验，通过原生操作及撤销落地。

## Alternatives considered

旧方案要求手工编辑接管后由用户显式交回。

## Consequences

仍需核对目标和内容。历史提案中的完整 Agent 编排和图持久化未因此实现。

依据见 [提交 ef56e0ce](https://github.com/MaojieXu/AstroPhotoFlow/commit/ef56e0cef8a66f86f9d8331b41e330f8238aedf3)、[WORKBENCH-WORKFLOWS-0059-native-editing-save-and-agent-target.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/frontend/docs/adr/WORKBENCH-WORKFLOWS-0059-native-editing-save-and-agent-target.md)、[提交 88dd3c19](https://github.com/MaojieXu/AstroPhotoFlow/commit/88dd3c1987bab7421c6589343f0bc5657aba5332)。
