# 当前开发上下文

更新时间：2026-10-25。当前实施分支为 **branch/redesign**，起点 dev `b6759abd800052f0c1d41693e5385a428db755a3`，保留起点未提交的自动拉伸预览改动。main 起点为 `c8366e640eeab97f3336a6b3c12c80678a235f69`；本轮所有修改与提交限定在 redesign。

## 当前架构

项目已转为基于固定 ComfyUI 前后端源码的天文专用网页软件。原生前端提供素材库、工作流、设置三个页面，默认进入素材库；内部 FastAPI 继续保存业务权威，定制 ComfyUI 服务直接注册同源网关。

固定引擎0.42.0／前端1.57.1；原生前端开发使用 Node26.8.2–26.x 和 pnpm11.13.1。源码与构建见[架构](../architecture/overview.md)和[开发流程](README.md)。

## 运行与数据边界

- Python：`.artifacts/venvs/dev`，根 uv.lock。
- 本轮隔离 workspace：`.artifacts/workspaces/redesign`，网页32388／领域服务32390。
- 独立 runtime：LocalAppData/AstroPhotoFlow/runtime/native-web-0.1.0。
- 原 dev workspace、31388／31390实例、根.env、默认 workspace 指针和全局 MCP 注册保持。
- schema仍为0009，58个MCP工具，原件只读、固定版本、设备快照、校准关联和回收站保护保持。

当前旧的0.1.0 CPU依赖可只读复用；本轮实际运行环境使用独立目录。完整网页资源由 workspace/web 提供，启动不再依赖 AstroPhotoFlow custom node 或 ComfyUI 侧栏扩展加载。

自动拉伸仍采用打开单图时计算 RGB 背景白平衡和 MTF 配方，并同步大图与缩略图；原件、版本身份及其他成员不变。

## 验证与后续范围

已有 Python 回归、前端组件、原生生产构建、浏览器验收和发行安装的实际证据集中到[原生网页记录](native-web.md)。未实际运行的平台或依赖不得标为通过。

完整 Agent、天文软件适配、项目工作流版本权威、结果比较和项目记忆仍需后续实施。本轮原生工作流保留 ComfyUI 引擎能力，不将普通引擎执行冒充已实现的天文处理及来源追溯闭环。
