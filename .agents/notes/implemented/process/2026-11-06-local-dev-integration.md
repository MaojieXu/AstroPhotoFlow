# Agent Note: 功能分支本地合入 dev

Status: Implemented

## Problem

[此前的 PR 流程](2026-11-06-pr-workflow.md)要求功能分支经 GitHub PR 和独立审批才能合入 `dev`。用户在单人开发场景中取消了这项要求。

## Decision

贡献指南改为从 `dev` 开分支，通过适用检查后在本地合入 `dev`，经授权推送集成结果。发布仍通过从 `dev` 到 `main` 的发布 PR。

## Alternatives considered

保留功能 PR 并只取消独立审批仍需要在 GitHub 上创建请求，无法简化到用户要求的本地集成流程。

## Consequences

功能改动的验证结果记在交付说明中，推送 `dev` 后由 GitHub Actions 检查。贡献指南分别描述 `dev` 和 `main` 的 GitHub 设置。
