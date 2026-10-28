# 开发、测试与发行

产品范围与阶段验收以[现行需求](../requirements/README.md)为准，模块权威与调用边界见[总架构](../architecture/overview.md)，阶段依赖与联调出口见[开发路线](platform-roadmap.md)。本文维护当前开发及发行命令，不把待实现目标写成现有能力。

开发分支为 `dev`，Python 环境为 `.artifacts/venvs/dev`。需要 Python 3.12、uv、Node `>=26.8.2 <27` 和 pnpm 11.13.1；依赖锁为根 `uv.lock` 与 `frontend/pnpm-lock.yaml`。

## 安装与构建

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$PWD/.artifacts/venvs/dev"
pnpm --dir frontend install --frozen-lockfile --ignore-scripts
pnpm build
uv sync --locked --extra dev --python 3.12
```

根 package.json 只提供任务入口，不执行根 pnpm install。`pnpm build` 生成固定引擎归档、检查私有 UI 包和原生应用类型，再构建完整网页。网页输出为 `.artifacts/build/frontend`；`frontend/build` 是上游构建源码。

## 验证入口

```powershell
uv run --locked --no-sync pytest -q
pnpm test
pnpm check:boundaries
```

根 `pnpm test`／`typecheck` 委托私有 UI 包，完整原生类型检查包含在构建中。模块依赖方向由 `check:boundaries` 检查。测试位置见[模块导航](../architecture/module-map.md)，结果与缺口见[验证矩阵](test-matrix.md)。

## 隔离运行与浏览器验收

```powershell
uv run --locked --no-sync apf init --workspace .artifacts/workspaces/docs-update --service-port 32590 --comfyui-port 32588 --frontend-assets .artifacts/build/frontend --no-activate
uv run --locked --no-sync apf start --workspace .artifacts/workspaces/docs-update --no-activate
uv run --locked --no-sync apf status --workspace .artifacts/workspaces/docs-update
$env:APF_WEB_URL = 'http://127.0.0.1:32588'
pnpm --dir frontend exec playwright install chromium
pnpm test:browser
uv run --locked --no-sync apf stop --workspace .artifacts/workspaces/docs-update
```

已有完整固定 runtime 时，初始化可加 `--reuse-runtime`，只同步网页；重建后先停止目标实例，再同步并启动。`--no-activate` 保持默认 workspace 选择。已有 Chromium 时可用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指定可执行文件。

浏览器使用隔离 workspace 与合成 PNG，默认报告在 `.artifacts/reports/native-web`。真实开发数据不用于导入、回收站或工作流写入验收。正常 dev 使用 31388／31390，本机工具与状态见[当前上下文](current-context.md)。

配置由 `astrophotoflow.core.config` 统一解析：显式 workspace、环境、默认指针、默认配置依次优先。`storage.data_dir` 相对 TOML 解析；令牌位于 workspace/data/service.token。CLI/MCP 用进程级 `ASTROPHOTOFLOW_CONFIG` 选择隔离实例，不改全局注册。

## 发行与安装验证

```powershell
uv run --locked --no-sync python scripts/build_release.py
uv run --locked --no-sync python scripts/verify_distribution.py
```

发行脚本安装锁定前端依赖、构建网页并生成 wheel／sdist。Python 中间产物为 `.artifacts/build/python`，发行物为 `.artifacts/dist`。网页已构建、仅重新打 Python 包时，可用 `python -m build --installer uv --outdir .artifacts/dist`。

wheel 携带完整网页与固定引擎；sdist 携带预构建网页，支持无 Node 的 wheel 重建。验证脚本在源码目录外安装两份 wheel，检查入口、迁移、资源和源码包范围。用户安装步骤见[工作台使用](workbench.md)。

新日志、临时数据、缓存和报告进入 `.artifacts`。保留原件、既有 workspace、令牌与旧 runtime；未验证的平台和依赖不得写成通过。
