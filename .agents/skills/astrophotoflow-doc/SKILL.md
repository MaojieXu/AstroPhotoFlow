---
name: astrophotoflow-doc
description: 在本仓库新增或修改文档时使用：确定事实归属、控制预算、维护中英配对与链接，然后跑文档门禁。用户要求写需求、架构、子系统说明、开发或测试文档时先读本技能。
---

# 文档改动

## 触发

要新增页面、改写正文、调整文档结构或移动事实归属时。

## 步骤

1. 读 `.agents/../docs/AGENTS.md`（仓库内路径 `docs/AGENTS.md`），确认要写的事实归哪一层，避免在第二处重复。现状只写当前状态；历史与取舍写 Agent Note。
2. 查 `scripts/doc-budgets.json` 中该页预算。新页先加预算再写正文；超限先删重复，不要先改上限。
3. 写中文主文档。一段一行，不硬换行；链接用相对路径。
4. 写同目录英文配对 `foo.en.md`，保持标题、列表、表格、代码块与链接语义同构；中文页链 `.md`，英文页链 `.en.md`。
5. 重记哈希：`python scripts/verify_docs.py pairing --write <中文主文件>`。
6. 跑 `pnpm check:docs`；失败按提示修内容，不用 `--report` 绕过。

## 入口

- 规则：`docs/AGENTS.md`
- 双语契约：`docs/i18n/README.md`
- 门禁：`scripts/verify_docs.py`（`budgets|pairing|wrap|links|notes|skills|all`）
