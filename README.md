# AstroPhotoFlow

[English](README.en.md) | 中文

AstroPhotoFlow 是本地运行的天文图像工作台：把拍摄的 FITS 整理成可追溯素材，在原生画布上把外部软件操作连成处理图，真实执行后查看、比较并保存结果。平台运行两个常驻服务（ComfyUI 网页与引擎、FastAPI 领域服务）；用户直接操作网页，外部通用 Agent 经平台 MCP 操作同一份数据和用户明确授权的画布。

## Quickstart

需要 Windows x64、Git 与 PowerShell。入口复用 PATH 中符合版本的本机工具，缺失时下载固定归档到项目 `.artifacts` 并校验，不修改全局 PATH、Python 注册或默认 workspace。

```powershell
git clone --branch dev --depth 1 https://github.com/MaojieXu/AstroPhotoFlow.git
cd AstroPhotoFlow
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 --workspace .artifacts/workspaces/dev --build --start
```

首次运行安装依赖并构建前端，完成后按回执中的实际地址打开工作台。同一源码基点再次运行可省略 `--build` 复用产物。

前端热更新使用同一入口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 --watch --workspace .artifacts/workspaces/dev --port 32589 --strictPort
```

## 文档入口

| 我想… | 读 |
| --- | --- |
| 查看全部文档与任务入口 | [文档入口](docs/README.md) |
| 了解产品要求与边界 | [产品需求](docs/product/README.md) |
| 定位模块、数据归属与依赖 | [架构](docs/architecture.md) |
| 搭建环境、运行本地命令 | [开发](docs/development.md) |
| 跑测试、写验证回执 | [测试](docs/testing.md) |
| 构建与发布开发版本 | [发行](docs/release.md) |
| 查询 HTTP、MCP 与 CLI 接口 | [参考](docs/references.md) |
| 操作工作台 | [使用说明](docs/user/workbench.md) |
| 参与开发与提交 PR | [贡献指南](CONTRIBUTING.md) |
| 了解仓库级 Agent 约定 | [AGENTS](AGENTS.md) |
