# Agent Notes

本目录记录已经发生的决定、修复与简化，以及当时的取舍和后果。它是历史，不是现状；现状写在 `docs/`。

## 位置即状态

- `implemented/<class>/YYYY-MM-DD-slug.md`：已经实现的记录。
- class 取 `feature`、`bug-fix`、`simplification`、`architecture`、`process`、`testing`；没有对应类别的改动不写笔记。
- 文件名日期是做出决定的日期，slug 用短横线连接的小写英文。

本目录只保留 `README.md` 与 `implemented/`；不再使用 `proposed/`、`rejected/`、`archived/`。被后续决定取代的笔记保持原文，由新笔记链接前一条。

## 何时写

- 写了非显然的取舍：选了一个方案、放弃了其他候选，或承担了已知代价。
- 修了一个需要解释根因的缺陷，或做了一次影响行为的简化。
- 引入或改变流程、文档规则、门禁。
- 不写计划、不写待办、不写“下次再做”。只写已经生效的事实。

## 格式

每条笔记固定开头：第一行 `# Agent Note: <标题>`，第二行空行，第三行 `Status: Implemented`。正文标题必须是下面四节且按此顺序出现。

```markdown
# Agent Note: 示例标题

Status: Implemented

## Problem

要解决的问题，以及当时观察到的现象。

## Decision

实际做了什么，关键选择是什么。

## Alternatives considered

考虑过但没有采用的方案，以及不采用的原因。

## Consequences

现在需要承担的约束、代价和后续影响。
```

禁止 `Proposal`、`Plan`、`Migration plan`、`Acceptance criteria` 等章节；笔记是记录，不是提案。禁止 `INDEX.md`，导航靠目录与文件名。

## 与其他记录的分工

- 现状与规则：`docs/`。
- 讨论过程与审查意见：PR。
- 验证结果与日志：PR 的 Testing 与 `.artifacts/reports`。
- 决定与后果：本目录。

## 门禁

`python scripts/verify_docs.py notes` 校验路径、分类、文件名、固定头、四节顺序与禁用章节。CI 执行同一检查；笔记写坏时修内容，不绕过。
