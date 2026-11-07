# Agent Note: 修复 CI 产品任务缺少 pnpm

Status: Implemented

## Problem

`CI` 的 `product` job 在 `Build frontend` 步骤失败：ubuntu 报 `FileNotFoundError: [Errno 2] No such file or directory: 'pnpm'`，Windows 报 `'pnpm' is not recognized as an internal or external command`。根因是 job 只用 corepack 调用 `corepack pnpm build`，而根 `build` 脚本 `scripts/frontend_build_record.py:70` 通过 `subprocess.check_output(['pnpm', '--version'])` 直接查找 PATH 上的 pnpm；CI 没有安装独立 pnpm。该失败在文档重建前就存在，dev 上的历史 push run 同样停在同一步。

## Decision

在 `product` job 的 `actions/setup-node@v4` 之后加入 `pnpm/action-setup@v4`（版本 `11.13.1`），并把该 job 内的 `corepack pnpm` 全部改为 `pnpm`。修复作为独立提交进入 `codex/docs-rebuild`，随后随分支合入 `dev`。

## Alternatives considered

- 改 `scripts/frontend_build_record.py` 改用 corepack：只需要改 Python 入口，但 CI 与本地仍走不同入口，且 shim 行为依赖 corepack 状态。
- 在 CI 里执行 `corepack enable` 与 `corepack prepare`：需要额外的权限与缓存处理，版本仍由 `packageManager` 决定，步骤比直接安装更绕。
- 保留失败步骤不修：产品检查无法给出可信结论，文档改动也会被无关失败阻塞。

## Consequences

CI 安装的 pnpm 版本与 `package.json` 的 `packageManager: pnpm@11.13.1` 一致，本地仍可用 corepack；`product` job 首次真正执行全量 pytest 与前端测试，成为推送的关键路径，耗时明显长于文档 job。
