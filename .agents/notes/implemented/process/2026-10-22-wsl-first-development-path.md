# Agent Note: 首日采用 WSL 单环境的开发路径

Status: Implemented

## Problem

首版计划需要避免 Windows 和 Linux 间同时调用工具与转换路径。

## Decision

首日基线采用 WSL 内服务、ComfyUI 和工具、Windows 浏览器访问的设计，扩展提交实际记录了 WSL 中的前端构建入口。

## Alternatives considered

当时把独立桌面安装包排除在首版前置条件之外。

## Consequences

可核对证据覆盖扩展构建和侧栏原型。仓库没有首日双服务和科学处理完整验收记录。

依据见 [提交 1c16ca45](https://github.com/MaojieXu/AstroPhotoFlow/commit/1c16ca457680fcea4ee5d056308d8baa8c5b5857)、[README.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/39a8bee4c85c8a9b38f2bf9356cd5234f3cebed2/docs/AstroPhotoFlow_Requirements_v1.0/README.md)。 相关笔记见 [以 ComfyUI 扩展建立首日基线](../architecture/2026-10-22-comfyui-extension-baseline.md)。
