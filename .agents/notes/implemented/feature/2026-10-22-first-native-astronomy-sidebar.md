# Agent Note: 接入首个原生天文侧栏

Status: Implemented

## Problem

需要先验证扩展能在 ComfyUI 宿主中显示天文界面。

## Decision

通过扩展注册接入 Vue 侧栏，以 Vite 构建前端，并通过测试宿主的自定义节点目录加载。

## Alternatives considered

初版架构选择复用原生界面，未采用独立桌面壳。

## Consequences

当时记录了构建和侧栏截图，WSL 用于前端构建。证据只覆盖侧栏原型。

依据见 [提交 1c16ca45](https://github.com/MaojieXu/AstroPhotoFlow/commit/1c16ca457680fcea4ee5d056308d8baa8c5b5857)、[README.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/39a8bee4c85c8a9b38f2bf9356cd5234f3cebed2/docs/AstroPhotoFlow_Requirements_v1.0/README.md)。
