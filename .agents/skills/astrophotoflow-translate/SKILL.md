---
name: astrophotoflow-translate
description: 维护本仓库中文主文档的英文配对时使用：按结构镜像翻译、修正语言切换行与链接 locale、重记哈希并跑配对门禁。收到英文文档更新或配对失败提示时先读本技能。
---

# 英汉配对维护

## 触发

新增或修改中文主文档后需要补英文；`pairing` 门禁报哈希过期、缺英文、结构不一致或链接 locale 错误时。

## 步骤

1. 读中文主文档与 `docs/i18n/README.md`，确认小节数与结构。不要改中文结构与事实来迁就英文。
2. 在 `foo.en.md` 中按顺序镜像：标题层级、列表类型与条目数、表格行列、代码块语言与内容、链接语义目标。
3. 英文页 H1 后保留切换行 `English | [中文](foo.md)`；链接到配对文档用 `.en.md`，配对范围外目标保持原路径。
4. 中文页切换行保持 `[English](foo.en.md) | 中文`。
5. 重记：`python scripts/verify_docs.py pairing --write <中文主文件>`。
6. 跑 `pnpm check:docs`。哈希通过只说明两侧在记录时一致，语义由 reviewer 判断。

## 入口

- 契约：`docs/i18n/README.md`
- 清单：`scripts/doc-pairs.json`
- 状态：`python scripts/verify_docs.py pairing --list`
