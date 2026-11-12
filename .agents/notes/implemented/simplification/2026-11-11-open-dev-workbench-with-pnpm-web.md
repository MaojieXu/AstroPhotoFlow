# Agent Note: 用 pnpm web 打开开发工作台

Status: Implemented

## Problem

源码开发需要分别初始化工作区、启动双服务并启动 Vite。Python 变更后还需要手动重启服务。

## Decision

pnpm web 复用现有前端脚本和工作台控制入口。首次使用已构建网页初始化工作区。Vite 处理前端更新，现有 watchfiles 监听 Python 并通过受管入口重启。

## Alternatives considered

扩大 apf start 的职责会影响打包版。重新实现进程启停会重复工作台的准入、健康检查和端口选择。

## Consequences

日常开发用同一个命令。Python 重启沿用工作台的忙碌保护；上游地址改变时，Vite 重新连接实际地址。
