# Agent Note: 将自动 CI 收窄到 main 发布流程

Status: Implemented

## Problem

个人开发日常先在本地运行适用检查。每次推送 dev 又启动完整的 GitHub Actions，重复消耗时间和运行额度。

## Decision

CI 工作流的 PR 目标分支和推送分支均限定为 main。发布 PR 继续提供分支保护所需的检查状态。

## Alternatives considered

保留 dev 的每次推送检查会重复本地验证。完全关闭 CI 会取消发布前在干净环境运行的检查。

## Consequences

dev 的验证依赖本地检查回执。发布流程保留 Windows 与 Ubuntu 的构建和打包验证。
