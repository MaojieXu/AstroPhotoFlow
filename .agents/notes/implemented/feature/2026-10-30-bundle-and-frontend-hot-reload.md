# Agent Note: 开发前端与 Bundle 支持热更新

Status: Implemented

## Problem

调整 UI 或已安装包适配器时，频繁重启破坏开发反馈。

## Decision

采用 workspace 感知的 Vite 更新，并按 Bundle Python 及声明内容变化刷新节点与适配器。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

平台领域服务 Python 仍需明确重启。实际验证覆盖隔离实例，未涵盖所有长期升级组合。

依据见 [提交 ef56e0ce](https://github.com/MaojieXu/AstroPhotoFlow/commit/ef56e0cef8a66f86f9d8331b41e330f8238aedf3)、[提交 88dd3c19](https://github.com/MaojieXu/AstroPhotoFlow/commit/88dd3c1987bab7421c6589343f0bc5657aba5332)、[提交 4d17208c](https://github.com/MaojieXu/AstroPhotoFlow/commit/4d17208c7381fcee3b631f5eadf576aba1964f00)。
