# Agent Note: 首轮 Windows CPU 工作台交付

Status: Implemented

## Problem

首日方案把 ComfyUI、领域服务及工具放在 WSL，Windows 浏览器访问，以减少跨系统调用和路径转换。

## Decision

10 月 23 日的验收记录对应 Windows x64、Python 3.12、CPU。10 月 24 日的提交随包提供 ComfyUI 和 Windows CPU 锁文件，验证仓库外安装及 apf init。10 月 27 日的需求明确 Windows 优先，Linux／WSL 单独验收。

## Alternatives considered

原先的 WSL 单环境是已记录方案。历史未记载选择 Windows 的完整讨论或导致切换的 WSL 故障。

## Consequences

Windows 安装与初始化已有当时证据。首日 WSL 记录和后续 Linux CI 均不能代替完整 WSL 工作台验收。

依据见 [提交 f969d8bc](https://github.com/MaojieXu/AstroPhotoFlow/commit/f969d8bcd4a2c72c4f5633f6ea13bf2939c086d6)、[README.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/39a8bee4c85c8a9b38f2bf9356cd5234f3cebed2/docs/AstroPhotoFlow_Requirements_v1.0/README.md)、[README.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/9d4c729cb35cf961c34fa50cf55616cd6c2e4b10/docs/requirements/README.md)、[提交 31dab18c](https://github.com/MaojieXu/AstroPhotoFlow/commit/31dab18c5e700f836f742f480fb664b68fe9f57f)。
