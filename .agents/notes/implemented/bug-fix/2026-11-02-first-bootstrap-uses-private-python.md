# Agent Note: 首次 bootstrap 使用私有 Python 加载 Bundle 阶段

Status: Implemented

## Problem

uv 创建 venv 后，最初的系统 Python 进程不会自动切换解释器。

## Decision

把 Bundle 源码阶段交给已准备好的私有 Python 子进程，用 JSON 回执返回。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

当时在独立 Worktree 验证一次启动及重复复用，使用已有缓存，未验证无缓存机器或 WSL。

依据见 [提交 a3857c74](https://github.com/MaojieXu/AstroPhotoFlow/commit/a3857c745b63d830800dfe49362a39480fe69788)、[test-matrix.md L2362](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/development/test-matrix.md#L2362)。
