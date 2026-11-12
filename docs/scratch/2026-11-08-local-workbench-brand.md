# 本地工作台品牌清理交接

[English](2026-11-08-local-workbench-brand.en.md) | 中文

## 负责人和有效期

接手本地工作台验证的维护者负责。2026-11-08 创建，2026-11-22 到期。长期事实归[前端](../subsystems/frontend.md)和[发行](../release.md)，决策归[品牌与入口笔记](../../.agents/notes/implemented/simplification/2026-11-08-local-workbench-brand-and-entrypoints.md)。

## 当前状态

品牌和本地入口清理（`fab5e835`）以及素材库、设备管理单行工具栏（`8fcbf51f`）已推送到 `origin/dev`。其余未提交改动仍在本地工作区。

## 验证与接手

提交候选通过 651 项前端测试、3 项生产浏览器回归、类型检查和文档门禁。wheel 在候选源码目录之外安装通过，sdist 在无 Node 环境重建通过。回执在 `.artifacts/reports/dev-push-fca4301f/`，打包报告为 `features-packaging.json`。

Siril 完整回归未通过。节点注册、真实处理和定义更新断言通过，随后 Windows 在重命名隔离工作区内的测试检出目录时返回 `EPERM`。证据在 `.artifacts/reports/apf-brand-bundle/results.json`，失败步骤位于 `tests/browser/bundle-hot-reload.spec.ts` 的 `rename(checkout, retired)`。

需要完整回归回执时，在新的隔离工作区使用同一 Siril 源检出复跑。若再次失败，先查明占用目录的句柄，再判断是否是短时占用。持久结论写入测试回执，事项解决后移除本交接及其配对登记。
