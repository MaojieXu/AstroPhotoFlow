# Agent Note: 用 PR 流程替代 Git Manager-Feature 分工

Status: Implemented

## Problem

旧流程把空间准备、审查、测试、合并和推送集中给一个 Git Manager 角色，Feature 只在自己的 Worktree 工作并回传 Brief。它适合单人多 Feature 串行推进，但角色边界重、交接靠聊天记录、审查与合并不在仓库里留痕，也无法直接承接外部贡献者的 PR。

## Decision

开发流程改为基于分支与 PR：从 `dev` 开分支，完成后向 `dev` 发 PR；PR 必须通过文档门禁与产品检查，并获得 1 名独立 reviewer 批准后合并；`dev` 通过发布 PR 合入 `main`。审查意见、验证回执与 AI 使用声明都写在 PR 中。分支保护由管理员在 GitHub 设置必需检查 `all checks passed` 与 1 个批准，仓库内只记录配置清单。

## Alternatives considered

- 保留 Git Manager-Feature 双角色：流程成熟，但与 PR 审查、CI 门禁和外部贡献者模型不兼容。
- 采用 DeepSeek Harness 的加权批准与堆叠合并：保护更强，但需要仓库成员与 CI 权限配套，当前仓库只有单一维护者。
- 只加 CI 不改流程：检查会自动运行，但合并仍依赖聊天交接，审查不留痕。

## Consequences

每个改动都要走 PR，紧急修复也必须留下检查与批准记录；单人维护时 reviewer 需以独立上下文审查同一改动。分支保护无法由仓库代码声明，管理员漏配时 PR 仍可被直接推送绕过。此前基于 Worktree 的并空间准备与 Feature Brief 格式不再使用，相关旧文档随文档重建一并删除。
