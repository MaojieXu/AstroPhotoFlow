# Agent Note: 以 ComfyUI 扩展建立首日基线

Status: Implemented

## Problem

项目需要共享天文工作流编辑与执行能力。

## Decision

首日需求采用官方 ComfyUI 作为宿主，以独立扩展接入，保留原生画布和执行引擎。

## Alternatives considered

初版曾考虑 Langflow 和全面改造 ComfyUI Desktop，最终采用扩展。

## Consequences

这是首日架构决定。侧栏原型随后落地，网页产品形态后来改为原生工作台。

依据见 [提交 39a8bee4](https://github.com/MaojieXu/AstroPhotoFlow/commit/39a8bee4c85c8a9b38f2bf9356cd5234f3cebed2)、[README.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/39a8bee4c85c8a9b38f2bf9356cd5234f3cebed2/docs/AstroPhotoFlow_Requirements_v1.0/README.md)。
