# AstroPhotoFlow

[English](README.en.md) | 中文

AstroPhotoFlow 是本地运行的天文图像工作台：把拍摄的 FITS 整理成可追溯素材，在原生画布上把外部软件操作连成处理图，真实执行后查看、比较并保存结果。平台运行两个常驻服务（ComfyUI 网页与引擎、FastAPI 领域服务）；用户直接操作网页，外部通用 Agent 经平台 MCP 操作同一份数据和用户明确授权的画布。

## Quickstart

准备 Git、uv、Node.js 和 pnpm，版本见[开发环境](docs/development.md)。在一个检出目录安装依赖。

```sh
git clone --branch dev --depth 1 https://github.com/MaojieXu/AstroPhotoFlow.git
cd AstroPhotoFlow
uv sync --locked --extra dev
pnpm --dir frontend install --frozen-lockfile --ignore-scripts
```

首次打开工作台时构建网页、初始化开发 workspace，再启动服务。

```sh
pnpm build
uv run --locked --no-sync apf init --workspace .artifacts/workspaces/dev --frontend-assets .artifacts/build/frontend --no-activate
uv run --locked --no-sync apf start --workspace .artifacts/workspaces/dev
```

工作台就绪后，`start` 在交互式终端显示实际前端地址。加 `--open` 可在默认浏览器打开。脚本仍可从标准输出的 JSON 读取 `web_url`。更新工作台网页时先停止该实例，再构建和初始化。

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
