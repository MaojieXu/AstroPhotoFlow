# Agent Note: 文档体系全面重建

Status: Implemented

## Problem

旧文档按需求、架构、开发、验证记录分散在 `docs/` 下，混有历史批次、验收日志、`test-matrix.md` 与 1.2 MB 的候选清单，多数页面长期只增不拆。读者需要在多份文档间拼出同一事实，Agent 每次改动都要先判断哪份是当前状态。仓库没有文档预算、链接、配对或笔记门禁，也没有独立于实现的决策记录。

## Decision

以 DeepSeek Harness 的文档管理方式为蓝本整体重建：`docs/` 只保留产品、架构、子系统、开发、测试、发布、参考与用户说明；中文为主文档并配 `.en.md` 与 `.i18n.yaml` 哈希记录；新增 `scripts/verify_docs.py` 与三份清单，统一检查预算、配对、一段一行、链接、Agent Notes 与 Skills；`AGENTS.md` 收敛为 11 个层级；历史与取舍改由 `.agents/notes/implemented/**` 记录；旧目录 `docs/archive`、`docs/references`、`docs/decisions`、`docs/requirements`、`docs/development` 及两份巨型记录文件删除。

## Alternatives considered

- 增量整理旧树：改动小，但无法消除事实重复与历史包袱，门禁也只能覆盖新页。
- 只引入门禁、不改目录：预算与链接可落地，但读者仍要面对旧的分层和历史记录。
- 保留 `docs/archive` 与 `docs/references`：能保留历史证据，但与“只写当前状态”冲突，且让链接门禁不得不继续豁免整棵子树。
- 保留 ADR 目录：决策历史与 Agent Notes 职责重叠，两份记录会再次分叉。

## Consequences

迁移是一次性破坏性改动，旧文档删除后只能从 Git 历史找回。所有 25 个中文主文档都必须维护英文配对，翻译不同步会直接失败；页面受非空白字符预算约束，超限需先删减或调整归属。链接与笔记格式由 CI 强制执行，绕过门禁的改动无法合并。删除 `scripts/export_source_inventory.py` 后不再提供旧清单的生成入口。
