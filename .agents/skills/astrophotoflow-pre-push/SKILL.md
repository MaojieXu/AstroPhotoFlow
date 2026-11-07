---
name: astrophotoflow-pre-push
description: 提交、集成、推送或发发布 PR 前使用，按改动范围运行检查并记录结果。
---

# 提交前检查

## 触发

准备提交、集成、推送、发发布 PR 或回复 reviewer 时。

## 步骤

1. `git status` 与 `git diff --stat`：确认只有预期文件，未混入生成物或 `.artifacts`。
2. 文档改动：`pnpm check:docs`；改了配对文档先跑 `python scripts/verify_docs.py pairing --write <文件>`。
3. Python 改动：`uv run --locked --no-sync python -m pytest <相关测试> -q`；全量用 `python -m pytest -q`。
4. 前端改动：`pnpm test`；必要时 `pnpm typecheck` 与 `pnpm build`。
5. 只跑与改动范围匹配的检查；已通过且未再改动的检查不重复。失败先修，不注释测试。
6. 按测试文档记录命令、退出码与关键输出，完整日志放 `.artifacts/reports`。区分自动验证、真实运行与用户验收。
7. 发发布 PR 时在 AI Usage 中如实填写五个阶段与协助等级。

## 入口

- 流程与分支：`CONTRIBUTING.md`
- 测试分层：`docs/testing.md`
- 命令：`docs/development.md`
