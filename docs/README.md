# 文档入口

[English](README.en.md) | 中文

从本页按任务找文档。每类事实的归属、写作要求和门禁见 [文档规则](AGENTS.md)。

## 任务入口

| 我要… | 读 |
| --- | --- |
| 了解产品要求与边界 | [产品需求](product/README.md) |
| 定位模块、数据与依赖 | [架构](architecture.md) |
| 改一个子系统 | [子系统索引](subsystems/README.md) |
| 搭环境、跑本地命令 | [开发](development.md) |
| 跑测试、写验证回执 | [测试](testing.md) |
| 发版本 | [发行](release.md) |
| 查接口与生成物 | [参考](references.md) |
| 操作工作台 | [使用说明](user/workbench.md) |
| 理解已经做过的决定 | [Agent Notes](../.agents/notes/README.md) |
| 维护中英文配对 | [双语文档](i18n/README.md) |

## 约定

- 文档只写当前状态；历史、被放弃的方案与讨论过程写进 Agent Notes、提交信息或 PR，不留在正文。
- 中文主文档都有英文配对，改一侧必须同时改另一侧。
- 门禁入口是 `pnpm check:docs`，CI 与本地执行同一命令。
