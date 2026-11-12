# Agent Note: 采用可执行批次与共享 HTTP 客户端设计

Status: Implemented

## Problem

跨模块变更需要统一的执行顺序和可复用的传输边界。

## Decision

开发基线一度采用 22 个完整集成批次，并确认把既有 Fetch 客户端与错误契约收拢到 core。

## Alternatives considered

ADR 保留已有传输机制，未引入新的传输框架。

## Consequences

22 批次后来被降为历史参考。共享客户端方向随实现保留，测试维护窗口与运行批准仍各自核对。

依据见 [提交 9d4c729c](https://github.com/MaojieXu/AstroPhotoFlow/commit/9d4c729cb35cf961c34fa50cf55616cd6c2e4b10)、[WORKBENCH-PLAN-0061-executable-batches-and-shared-client.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/frontend/docs/adr/WORKBENCH-PLAN-0061-executable-batches-and-shared-client.md)。
