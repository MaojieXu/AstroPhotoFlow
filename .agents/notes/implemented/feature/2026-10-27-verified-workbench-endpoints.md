# Agent Note: 发现并验证工作台实际端口

Status: Implemented

## Problem

已有端口可能被其他程序或 workspace 占用。

## Decision

工作台启动时核对目标进程及健康状态，端口冲突时选择实际可用地址，分别报告网页和领域服务端点。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

配置端口和已启动服务的实际端口可以不同，控制入口需使用实际回执。

依据见 [提交 c23e10de](https://github.com/MaojieXu/AstroPhotoFlow/commit/c23e10de49053541298c69ea8c7416014294fae1)、[WORKBENCH-FOUNDATION-0054-automatic-startup-endpoints.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/frontend/docs/adr/WORKBENCH-FOUNDATION-0054-automatic-startup-endpoints.md)。
