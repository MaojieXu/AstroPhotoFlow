# ADR-WORKBENCH-SOFTWARE-0065: 首个 Siril 原生操作

Date: 2026-10-29

## Status

Accepted

## Context

用户要求完成 M3 实现候选、精简软件包页面，并从 CLI 选择一个工具供画布使用；测试只编写，编译更新后由用户验收。

## Decision

选择已存在定义和 CLI 原型的 Siril 1.4.4 Auto Stretch。一个固定 V3 节点从包／workspace JSON 读取控件，复用原生队列及停止。科学端口统一使用 APF_SCIENCE，固定引用经数据模块解析；一份脚本按固定顺序处理各成员，生成新的科学文件，预览单独生成。

当前首节点使用仅原生内部可调用的窄适配，不发布软件执行 HTTP／MCP 工具，不另建执行队列。必要调用事实置于该原生 prompt 的运行目录；M5 完整 SQLite 运行权威、项目图保存、准入与维护影响仍按原计划接入，不能把这个候选当作完整 M5。

软件页只保留软件名、红绿就绪点和安装／卸载；准确计划放入原生弹窗，通过原生连接确认。提前交付的卸载只移除平台程序，保留定义、图和素材；不改写图，因此不假装已完成 B55 的更新影响闭环。运行、准备及未知占用阻止维护。

## Consequences

无需安装或注册任意插件即可在原生节点库展示首工具；软件缺失时保留节点，执行明确报未就绪。后续扩展其他操作或通用 JSON 加载仍由 M4 完成。真实软件与停止能力尚未执行本轮验证。

CLI 参数依据 [Siril 1.4.4 命令](https://siril.readthedocs.io/en/stable/Commands.html)和 [Headless](https://siril.readthedocs.io/en/stable/Headless.html)；工作目录和独立配置使用准确版本的 `-d`／`-i`，不修改用户现有 Siril 配置。
