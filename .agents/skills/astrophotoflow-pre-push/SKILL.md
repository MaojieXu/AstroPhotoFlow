---
name: astrophotoflow-pre-push
description: 提交、请求审查或发 PR 前使用：按改动范围跑对应检查，收集可复核的回执，并把结果写进 PR 的 Testing。准备推送或回复 reviewer 时先读本技能。
---

# 提交前检查

## 触发

准备提交、请求审查、发 PR 或回复 reviewer 时。

## 步骤

1. `git status` 与 `git diff --stat`：确认只有预期文件，未混入生成物或 `.artifacts`。
2. 文档改动：`pnpm check:docs`；改了配对文档先跑 `python scripts/verify_docs.py pairing --write <文件>`。
3. Python 改动：`uv run --locked --no-sync python -m pytest <相关测试> -q`；全量用 `python -m pytest -q`。
4. 前端改动：`pnpm test`；必要时 `pnpm typecheck` 与 `pnpm build`。
5. 只跑与改动范围匹配的检查；已通过且未再改动的检查不重复。失败先修，不注释测试。
6. 把命令、退出码与关键输出摘要写进 PR 的 Testing；完整日志放 `.artifacts/reports`。区分自动验证、真实运行与用户验收。
7. 在 PR 的 AI Usage 中如实填写五个阶段与协助等级。

## 入口

- 流程与分支：`CONTRIBUTING.md`
- 测试分层：`docs/testing.md`
- 命令：`docs/development.md`
