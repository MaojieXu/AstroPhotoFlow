# Agent Note: 将开发环境收回单个检出目录

Status: Implemented

## Problem

Windows bootstrap 将安装工具、切换解释器、构建网页和准备工作台合成一次操作。用户级开发目录还负责为多个检出目录编号并维护共享快照。开发流程改用单个检出目录后，这些职责增加了依赖安装和故障排查的路径。

## Decision

Python 由 uv 按项目版本和锁文件装进 `.venv`，前端由 pnpm 按现有锁文件安装。删除自制准备入口、开发目录索引和快照清理命令。构建输出与固定 CPU 引擎都在项目 `.artifacts` 下，初始化通过现有 CLI 将网页复制到显式指定的 workspace。引擎通过 uv 创建独立环境并保留现有准备锁和 Torch 复用校验。

Windows 验证中 pnpm 的 junction 回退使嵌套依赖解析到了错误版本。前端改用 pnpm 的平铺布局。干净依赖树的构建、前端单测和架构检查通过，依赖锁文件保持原值。

## Alternatives considered

继续使用[用户级开发目录](../process/2026-11-07-user-level-dev-home.md)可在多个检出目录间复用构建和运行时，同时要维护指纹、目录链接和引用检查。单个检出目录由包管理器复用下载缓存。

## Consequences

装包和启动各自运行，工作台数据继续保存在既有 workspace。第一次构建解除旧输出链接，正在使用旧快照的工作台可继续读取原来的网页。正式 wheel 安装的引擎仍通过应用数据路径解析。
