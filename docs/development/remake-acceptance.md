# feature/remake 验收记录

日期：2026-10-25。基线为 `material-setting-improvement` 的 `d40d6c496cbc16e29bd0d54f3cc1afaeabc5d3ef`。本次改变工程组织和构建／测试接线，保留已接受功能，不新增 Agent、软件适配、数据库字段或 MCP 工具。

## 实际结果

| 检查 | 结果 |
|---|---|
| 完整 Python 产品测试 | **129 passed、1 skipped**，38.87 秒；包括真实 CLI／五工具 stdio MCP 和新增 workbench／包结构测试 |
| 完整前端测试 | **14 文件、111 passed**，12.17 秒 |
| 类型检查与生产构建 | `vue-tsc --noEmit`、Vite 生产构建通过，151 modules |
| HTTP 契约 | 运行时 OpenAPI 与迁移前快照相等；独立 reviewer 核对 60 个操作的路径、方法、operation ID 和定义一致 |
| 测试保留 | 迁移前清单中的 98 个 Python 测试函数和前端测试名称均保留；未弱化回收站回归 |
| 数据库与需求基线 | 0001–0006 迁移内容经换行归一化后与基线相同；冻结需求包逐文件字节一致 |
| Python 发行构建 | wheel、sdist 均成功构建；wheel 资源与本次前端构建一致 |
| 安装与源码包验证 | 从仓库外安装 wheel，通过 CLI 帮助、Python 模块导入、包资源和新库迁移检查；在 PATH 无 Node 的环境从 sdist 重建 wheel，再安装检查通过 |
| 独立审查 | GPT-6 Luna / xhigh，只读复核固定候选与最终小增量，106 个文件散列匹配；未发现范围内 blocker |
| 最终工程检查 | `git diff --cached --check`、Bash 脚本语法、活动文档链接和暂存文件边界检查通过；原 pnpm 锁内容未变 |
| 展示实例 | 原有 CPU 环境复用，31388／31390 加载重构代码；主页、代理健康、垃圾桶、JS/CSS 均 200 |

唯一跳过项为 `test_ffmpeg_extracts_one_video_frame`，原因是本机缺少 FFmpeg。已有 ORM 迁移对比出现循环外键排序 warning，本次未调整模型。Windows 本机结果已实际执行；Linux CI 已配置，尚无本分支远端运行结果，不宣称 Linux 验收通过。

第一次根测试运行暴露 pytest 把仓库根 ComfyUI 插件入口当作测试包初始化的问题；已通过 `--confcutdir=tests` 限定测试发现，保持插件运行行为不变。前端一条旧回收站标签断言按基线已接受 UI 更新。第一次打包发现旧 SOURCES 缓存将 `web` 混入 sdist，已明确 prune；Python 包数据显式声明，前端源码只随 sdist 保留，运行 wheel 不含前端源码、tests 或 node_modules。

## 独立复审边界

Reviewer 检查了后端拆分、导入和路由，checkout／installed 插件的不同资源根，工作台命令、cwd/env，构建配置、发行验证及前端类型化上下文和页面提取。既有测试报告由主代理执行，reviewer 没有复跑；文档归档、模板移除和实际展示 HTTP 由主代理核对，不冒充独立复测。

最终仅去掉一个测试文件的 EOF 空行（AST 一致），并添加冻结需求的 `-text` 属性，防止 Windows checkout 自动转换换行破坏原始散列；这两个增量已经只读复核，没有重复运行已通过的测试。

## 展示与资源

地址：`http://127.0.0.1:31388/`。旧 workspace 的名称含 `dev-preview-31dab18`，但当前运行的是 feature/remake 实现，schema 仍为 `0006_library_trash_cleanup_state`。

停止前核对了 PID、创建时间、命令、解释器、workspace 环境和监听归属；只重启该展示实例的服务与 ComfyUI。新服务使用单根开发环境，ComfyUI 使用原 CPU 环境，未重新安装 CPU 依赖。

| 实际 HTTP 资源 | 字节数 | SHA-256 |
|---|---:|---|
| `astrophotoflow.js` | 434749 | `09cd91761a38188f76ec6473c8cc5903afcc532efc43378eccb096ceff82ca88` |
| `astrophotoflow.css` | 23536 | `01beba68f94d1c1c04512a7d9fb6599193172fea70b148b611f8eff8de9d672f` |

构建文件、插件 assets 和 HTTP 响应逐字节一致。已通过 Codex 请求打开页面，工具返回 queued；不据此声称用户屏幕已显示或手动交互已验收。用户可刷新该地址自行点击，本次没有 computer use。

## 本地证据与边界

详细日志位于忽略的 `.artifacts/reports/`：`python.xml/log`、`frontend.xml/log`、`frontend-build.log`、`build.log`、`packaging.json/log`、`candidate.json` 和 `deployment.json`。本文件保存关键结果，生成日志不进入 Git。

未重新导入真实 Astro Dataset，未移动原图、ZIP、旧虚拟环境或展示 workspace，未改全局 MCP 注册和默认 workspace。旧的本机 `service`、`frontend`、`test` 目录可能仍含忽略的环境／缓存；它们不再是产品实现或测试源入口，新产物统一 `.artifacts/`。

未向 dev/main 合并。本次实现留在 feature/remake，后续产品扩展单独确定范围。
