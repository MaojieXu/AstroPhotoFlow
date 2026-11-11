# Agent Note: 确立 Windows 优先并单独验收 Linux／WSL

Status: Implemented

## Problem

首轮交付已经有 Windows 原生工作台的安装和运行记录，需要明确平台支持证据。

## Decision

10 月 27 日的需求将 Windows 定为优先交付目标，把 Linux／WSL 留作后续独立验收。

## Alternatives considered

首日曾选用 WSL 单环境。现存资料没有记录切换讨论或确认某项 WSL 故障是原因。

## Consequences

Windows 的安装、运行和发行证据只覆盖实际平台组合。之后的 Windows bootstrap 固化了本机开发入口。

依据见 [提交 9d4c729c](https://github.com/MaojieXu/AstroPhotoFlow/commit/9d4c729cb35cf961c34fa50cf55616cd6c2e4b10)、[README.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/9d4c729cb35cf961c34fa50cf55616cd6c2e4b10/docs/requirements/README.md)、[提交 242b6133](https://github.com/MaojieXu/AstroPhotoFlow/commit/242b6133257fb3d9230d82527caaf7c032536125)。 相关笔记见 [首日采用 WSL 单环境的开发路径](2026-10-22-wsl-first-development-path.md)、[首轮 Windows CPU 工作台交付](2026-10-23-windows-first-workbench.md)。
