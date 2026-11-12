# Agent Note: 验证 FastMCP 设备录入与独立 Master 导入

Status: Implemented

## Problem

需要用实际校准文件验证外部 Agent 能在指定工作区登记设备组合，并把已有 Master 按独立素材导入校准库。导入登记、固定原件可用和预览状态需要分别核对。

## Decision

在独立预览工作区用显式配置连接 FastMCP，每批操作复用一个 stdio 客户端。组合引用已登记的主相机、望远镜、赤道仪和滤镜，导星相机独立登记，升级计划放在说明。导入按检查结果的文件 ID 提交，先验证一张 60 秒暗场，再逐张提交剩余文件。为每张保留请求 ID，按原回执读取任务与固定版本。 [FastMCP 入口](../../../../src/astrophotoflow/interfaces/mcp/server.py) · [显式导入工具](../../../../src/astrophotoflow/interfaces/mcp/data/imports.py)

## Alternatives considered

图像组可以保存一组成员，但校准目标按单个 Master 的固定版本选择。整批直接提交会在确认首张文件的分类和原件状态前扩大导入范围。

## Consequences

回读确认八条设备记录和一个组合。十张 FITS 均为可用的托管 Master，暗场三张、平场七张，校准库界面显示十条独立素材。固定版本的 BLAKE3 与源文件一致，关键 FITS 头卡可读，设备关联和校准绑定留空。十个导入回执的预览状态均为 `not_requested`。 [校准与固定版本](../../../../docs/subsystems/library.md) · [FastMCP 选型记录](../architecture/2026-11-01-official-fastmcp-and-generated-cli.md)
