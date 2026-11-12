# 贡献指南

[English](CONTRIBUTING.en.md) | 中文

本仓库从 `dev` 开分支，在本地验证并合入 `dev`。仓库级约定见 [AGENTS](AGENTS.md)，文档规则见 [docs/AGENTS](docs/AGENTS.md)，验证方式见[测试](docs/testing.md)，发行步骤见[发行](docs/release.md)。

## 分支与提交

- 集成分支是 `dev`；所有改动从当前 `dev` 创建分支。
- 提交、合并、推送与创建 PR 按用户授权执行。
- 提交保持单一目的，不混入无关格式化、重构或改名。
- 提交前读改动范围附近的 `AGENTS.md`、代码与测试。
- 分支名称描述改动主题，不使用旧模块名或历史任务名。

## 集成到 `dev`

- 合并前同步最新 `dev`，运行与改动范围匹配的检查并记录结果。
- 检查通过后可在本地将功能分支合入 `dev`，无需 PR 或独立审批。
- 本地合并完成后，可按授权推送 `dev`。检查流程见[测试](docs/testing.md)。

## 发布 PR 的审查与合并

- 按 `.github/pull_request_template.md` 填写发布 PR，说明变更与实际验证结果。
- 发布 PR 需要 1 名独立 reviewer 批准。Reviewer 根据需求与 diff 判断。
- reviewer 提出意见，不再改代码；作者修改后请 reviewer 复审受影响的改动。
- 必需检查全部通过且已有批准后才合并。

## 检查入口

| 检查 | 命令 |
| --- | --- |
| 文档门禁 | `pnpm check:docs` |
| Python 测试 | `uv run --locked --no-sync pytest -q` |
| 前端单元测试 | `pnpm test` |
| 构建 | `pnpm build` |
| 发行验证 | `python scripts/verify_distribution.py` |

浏览器测试、打包与架构边界检查按改动范围补充，见[测试](docs/testing.md)。

## 分支保护

GitHub 仓库管理员在仓库设置中配置以下规则。

- `dev` 允许授权的常规推送，以接收本地集成结果。
- `main` 经发布 PR 更新，要求至少 1 个批准和 `all checks passed` 状态检查。

## AI 使用声明

- 发布 PR 的 AI 使用部分按拆解、设计、测试、实现、审查五个阶段填写。
- 每个阶段标注协助等级：`none`、`assisted`、`generated`。
- 只声明真实使用；未使用的阶段写 `none`，不省略。
- 生成内容由提交者负责，仍按本指南验证与审查。

## 发布

- 只做 `X.Y.Z-dev.N` 开发版本，版本号来源与构建步骤见[发行](docs/release.md)。
- `main` 只接收来自 `dev` 的发布 PR；主分支合并、tag 与对外发布需用户另行授权。
