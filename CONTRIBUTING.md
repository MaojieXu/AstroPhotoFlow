# 贡献指南

[English](CONTRIBUTING.en.md) | 中文

本仓库从 `dev` 开分支、向 `dev` 发 PR。改动必须通过文档门禁、产品检查与 1 名独立 reviewer；发布只做 `X.Y.Z-dev.N` 开发版本，`dev` → `main` 走发布 PR。仓库级约定见 [AGENTS](AGENTS.md)，文档规则见 [docs/AGENTS](docs/AGENTS.md)，验证方式见[测试](docs/testing.md)，发行步骤见[发行](docs/release.md)。

## 分支与提交

- 集成分支是 `dev`；所有改动从当前 `dev` 创建分支。
- 不直接推送 `dev` 或 `main`；推送与建 PR 按用户授权执行。
- 提交保持单一目的，不混入无关格式化、重构或改名。
- 提交前读改动范围附近的 `AGENTS.md`、代码与测试。
- 分支名称描述改动主题，不使用旧模块名或历史任务名。

## Pull Request

- PR 目标分支是 `dev`；描述按 `.github/pull_request_template.md` 填写。
- 动机写清问题、Issue 或场景；变更按模块列出。
- 验证部分只写实际执行过的命令与结果；未执行写明原因。
- 完整日志放 `.artifacts/reports`，PR 中引用路径，不粘贴全文。
- 文档改动说明更新了哪一层，以及是否重记 `.i18n.yaml`。

## 审查与合并

- 每个 PR 需要 1 名独立 reviewer 批准；reviewer 不继承作者上下文，只依据需求与 diff 判断。
- reviewer 提出意见，不再改代码；作者修改后请 reviewer 复审受影响的改动。
- 必需检查全部通过且已有批准后才合并。
- 合并后删除分支，从最新 `dev` 开始下一项改动。

## 必需检查

| 检查 | 命令 |
| --- | --- |
| 文档门禁 | `pnpm check:docs` |
| Python 测试 | `uv run --locked --no-sync pytest -q` |
| 前端单元测试 | `pnpm test` |
| 构建 | `pnpm build` |
| 发行验证 | `python scripts/verify_distribution.py` |

浏览器测试、打包与架构边界检查按改动范围补充，见[测试](docs/testing.md)。

## 分支保护

GitHub 仓库管理员在仓库设置中手动配置 `dev` 和 `main`：

- 禁止直接推送，所有改动经 PR 合并。
- 合并前至少 1 个批准。
- 必需状态检查为 `all checks passed`（CI 汇总文档与产品 job）。
- 管理员保留紧急处置权限；常规流程不做例外合并。

## AI 使用声明

- PR 的 AI 使用部分按阶段填写：拆解、设计、测试、实现、审查。
- 每个阶段标注协助等级：`none`、`assisted`、`generated`。
- 只声明真实使用；未使用的阶段写 `none`，不省略。
- 生成内容由提交者负责，仍按本指南验证与审查。

## 发布

- 只做 `X.Y.Z-dev.N` 开发版本，版本号来源与构建步骤见[发行](docs/release.md)。
- `main` 只接收来自 `dev` 的发布 PR；主分支合并、tag 与对外发布需用户另行授权。
