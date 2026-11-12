# Agent Note: Bundle 源码与通用节点界面的联调归档

Status: Implemented

## Problem

Bundle 开发时需要在已打开的工作台看到源码改动。节点界面也需要一套跨软件的参数与结果表达，供画布用户和 MCP Agent 读取。来源为 Codex chat「调研插件实现与 Bundle 管理」，ID 为 `01a1b559-5f68-7813-a5fa-b7b8e944a673`。

## Decision

开发 workspace 可通过 `scripts/dev_bundle_sources.py --repo-bundles` 启用根目录检出发现。普通适配器改动在下次执行生效，参数或端口定义变动刷新节点目录，画布旧实例保留位置和连线并提示重新添加。[源码直连记录](../feature/2026-11-07-develop-bundles-from-checkouts.md)

通用节点卡片由宿主按 Bundle 声明展示全部参数和已检查产物。允许自动执行的节点改参后仍走原生队列处理完整输入。小图和大图读取同一产物，通道和小图尺寸属于查看状态。坐标编辑、直方图和逐帧定位按实际声明与数据启用，HTTP 与 MCP 共用结果契约。[节点卡片记录](../feature/2026-11-07-use-checked-results-in-bundle-cards.md)

## Alternatives considered

调研参考了 ComfyUI 的目录式插件加载与 deepseek-harness 的声明式插件入口。每次打包再安装会拉长开发反馈。独立的低分辨率运算会带来另一套参数和结果来源，按软件单独实现节点界面也会重复维护控件与结果逻辑。

## Consequences

源码直连使用隔离工作台和实际 Siril checkout 验证，覆盖新增目录、同一节点执行新代码、旧定义失效、错误修复与目录移除。通用节点界面使用测试 Bundle 在实际浏览器验证单图与直方图、原图选点和逐帧质量表。两次浏览器回执分别在 `.artifacts/reports/bundle-hot-ebcf6c92/results.json` 和 `.artifacts/reports/bundle-ui-browser.log`。

节点界面的针对性验证为 65 项 Python 和 48 项前端测试通过。扩大到素材库媒体回归时复现了 4 项已有的缩略图用例失败。源码直连阶段的全量 Python 回执在 `.artifacts/reports/bundle-hot-all-python.xml`。
