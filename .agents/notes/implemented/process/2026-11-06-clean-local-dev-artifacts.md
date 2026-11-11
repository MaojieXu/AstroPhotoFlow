# Agent Note: 分批清理本地 dev 历史环境

Status: Implemented

## Problem

本地 `dev` 的 `.artifacts` 在清理前约有 63.4 GiB 的逻辑文件大小。旧测试、开发环境和验收产物与含 SQLite、FITS、XISF 的历史 workspace 并存。仓库根旧 `node_modules` 还保留了指向改名前路径的链接。

## Decision

按可重建性和用户授权分两批处理。先核对并删除 25 个旧 pytest 临时目录和无使用引用的根 `node_modules`，合计约 2.26 GiB。用户随后逐项批准删除 16 个历史目标，涵盖旧发行物、环境和验证副本、验收产物及指定预览和归档数据。确认目标路径和进程状态后删除，只解除符号链接和目录联接本身，并注销已并入 `dev` 历史的 `bootstrap-reuse-verification` worktree 登记。

## Alternatives considered

整目录清空 `.artifacts` 会同时移除当前依赖缓存、工作台数据和未裁决的验收证据，因此按明确路径清理。含数据库和科学图像的历史目录先列清单，收到单独授权后才删除。

## Consequences

第二批删除约 42.60 GiB 的逻辑文件，清理前后 C 盘可用空间增加约 42.12 GiB。当前 `dev` workspace、开发虚拟环境、前端依赖、共享缓存和独立测试样本均保留。第一批清理后 `pnpm typecheck` 通过，`pnpm test` 首次遇到沙箱临时目录文件缺失，将该次命令的 `TEMP` 和 `TMP` 指向仓库内后复测通过 87 个测试文件、537 项测试。

启动流程只做了只读核查。已有回执显示一次复用启动通过双服务健康检查，但用户级配置锁拒绝写入，实际端口未保存。该次双服务启动阶段约 30 秒，另一次构建阶段约 178 秒。此次清理期间的服务控制和 bootstrap 源码均无改动。安装与准备入口见[开发环境](../../../../docs/development.md)。
