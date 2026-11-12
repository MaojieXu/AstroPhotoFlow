---
name: astrophotoflow-note
description: 在本仓库完成一个非显然的决定、修复或简化后使用：把已发生的事实写成 Agent Note，记录问题、决定、备选方案与后果。收尾任务或需要追溯历史决定时先读本技能。
---

# 写 Agent Note

## 触发

完成一次需要解释的取舍、修复或流程变更后；或需要追溯某个决定的原因时。

## 步骤

1. 判断是否值得写：选择了方案并放弃了其他候选、承担了已知代价、修了需要解释根因的缺陷、改变了流程或门禁。计划与待办不写。
2. 选 class：`feature`、`bug-fix`、`simplification`、`architecture`、`process`、`testing`。
3. 新建 `.agents/notes/implemented/<class>/YYYY-MM-DD-<slug>.md`，日期用决定日期，slug 用小写短横线英文。
4. 使用固定头与四节：第一行 `# Agent Note: <标题>`，空行，`Status: Implemented`，然后 `## Problem`、`## Decision`、`## Alternatives considered`、`## Consequences`，顺序不可变。
5. 只写已发生的事实；不写 Proposal、Plan、验收标准。被后续决定取代时保留原文，另写一条并链接前一条。
6. 跑 `python scripts/verify_docs.py notes`。

## 入口

- 规则：`.agents/notes/README.md`
- 校验：`python scripts/verify_docs.py notes`
