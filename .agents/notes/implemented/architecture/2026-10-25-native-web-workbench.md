# Agent Note: 迁入 ComfyUI 原生网页工作台

Status: Implemented

## Problem

独立入口与宿主编辑器之间需要共享导航和领域服务。

## Decision

使用单一 Vue／Pinia 原生网页，FastAPI 经同源网关提供领域能力，启动器管理两个进程。

## Alternatives considered

重写领域服务会扩大到验证和认证契约，独立桌面包在当期范围之外。

## Consequences

从首日扩展原型过渡到原生网页，继续复用原生画布和领域数据。

依据见 [提交 6e0d3e56](https://github.com/MaojieXu/AstroPhotoFlow/commit/6e0d3e561ebf39d98b33dbed3f2882dc97155573)、[提交 e7180949](https://github.com/MaojieXu/AstroPhotoFlow/commit/e718094999ee19d2f003a91c8401cba5a1afd3e3)。 相关笔记见 [以 ComfyUI 扩展建立首日基线](2026-10-22-comfyui-extension-baseline.md)。
