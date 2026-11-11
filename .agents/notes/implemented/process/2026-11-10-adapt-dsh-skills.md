# Agent Note: 按需改编 DSH skills

Status: Implemented

## Problem

`reference/deepseek-harness/.agents/skills/` 有 22 个技能可借鉴流程；原样复制会带入 Cordis、DSH 会话与 GitHub stack 等本仓库不存在的机制，且 6 份正文超过 `docs/AGENTS.md` 的 8000 非空白字符预算。仓库已有覆盖文档、笔记、提交检查、翻译与素材库操作的 5 个技能。

## Decision

只安装 3 个经重写的中文技能：`astrophotoflow-error-handling`、`astrophotoflow-test-reliability`、`astrophotoflow-performance`；其余 19 个跳过。技能为单文件，只写触发、步骤与入口并链接 `docs/` 事实，不建 references，不引用未跟踪的 `reference/` 路径。

## Alternatives considered

- 原样复制 22 个技能：预算超限，且 DSH 专有目录与命令在本仓库不可用。
- 全部跳过：丢失测试隔离、失败语义与性能测量的可复用流程。
- 安装 5 个（加 prose 与 simplification）：写作规则已有单一出处，简化调查与“最小正确改动”易冲突，且当前无第二次实际需求。

## Consequences

技能目录由 5 个变为 8 个，新增维护面；后续新增技能需按真实需求评审。DSH 参考仓被 `.gitignore` 排除，技能必须自包含。三个技能不改变现有技能与文档，只在对应任务中按需加载。
