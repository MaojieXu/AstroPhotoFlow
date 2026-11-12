# AstroPhotoFlow

[English](README.en.md) | 中文

AstroPhotoFlow 是本地运行的天文图像工作台：把拍摄的 FITS 整理成可追溯素材，在原生画布上把外部软件操作连成处理图，真实执行后查看、比较并保存结果。平台运行两个常驻服务（ComfyUI 网页与引擎、FastAPI 领域服务）；用户直接操作网页，外部通用 Agent 经平台 MCP 操作同一份数据和用户明确授权的画布。

## Quickstart

首次开发先准备 Git、uv、Node.js 和 pnpm，版本见[开发环境](docs/development.md)。安装依赖、构建网页并打开开发工作台。

```sh
git clone --branch dev https://github.com/MaojieXu/AstroPhotoFlow.git
cd AstroPhotoFlow
uv sync
pnpm -C frontend install
pnpm build
pnpm web
```

之后每次开发使用同一个启动命令。

```sh
pnpm web
```

打开 Vite 页面后，前端保存即热更新，Python 保存后开发脚本重启工作台。日常源码修改无需再运行 `pnpm build`。

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
| 参与开发与集成 | [贡献指南](CONTRIBUTING.md) |
| 了解仓库级 Agent 约定 | [AGENTS](AGENTS.md) |
