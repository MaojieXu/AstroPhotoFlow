# 原生网页版本开发

开发分支为 `branch/redesign`。Python 环境使用 `.artifacts/venvs/dev`；依赖锁为根 `uv.lock`、原生前端 `frontend/pnpm-lock.yaml`。

## 构建与测试

需要 Python 3.12、uv、Node.js `>=26.8.2 <27`、pnpm 11.13.1。

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$PWD/.artifacts/venvs/dev"
pnpm --dir frontend install --frozen-lockfile --ignore-scripts
pnpm build
uv sync --locked --extra dev --python 3.12
uv run --locked --no-sync pytest -q
pnpm test
```

`pnpm build` 更新定制引擎归档，并运行原生前端类型检查与生产构建。完整网页产物位于 `.artifacts/build/frontend`，包括 HTML、分块脚本、样式、语言及静态文件。原生前端复用上游构建与依赖；业务组件通过构建去重使用同一个 Vue/Pinia。

## 隔离运行

```powershell
uv run --locked --no-sync apf init --workspace .artifacts/workspaces/redesign --service-port 32390 --comfyui-port 32388 --frontend-assets .artifacts/build/frontend --no-activate
uv run --locked --no-sync apf start --workspace .artifacts/workspaces/redesign --no-activate
uv run --locked --no-sync apf status --workspace .artifacts/workspaces/redesign
uv run --locked --no-sync apf stop --workspace .artifacts/workspaces/redesign
```

重新构建后，在停止测试实例时再次运行 `apf init ... --reuse-runtime --no-activate`，同步完整网页目录并复用已准备的原生 CPU 环境。浏览器地址为 `http://127.0.0.1:32388/#/workflows`。

配置解析继续由 `astrophotoflow.config` 统一负责。显式 workspace 优先；`.env` 与默认 workspace 指针不因这组命令改变。`[comfyui].allowed_origins` 继续描述网页服务来源，`storage.data_dir` 相对 TOML 解析。令牌保存在 workspace/data/service.token。

当前 `.env` 和既有 MCP 注册仍可指向原开发实例。访问原生实例的业务 CLI/MCP 时，在该进程环境中显式设置 ASTROPHOTOFLOW_CONFIG 为 redesign 的 config.toml，不修改全局注册。

## 浏览器验收与发行

```powershell
$env:APF_WEB_URL = 'http://127.0.0.1:32388'
pnpm --dir frontend exec playwright install chromium
pnpm test:browser
uv run --locked --no-sync python scripts/build_release.py
uv run --locked --no-sync python scripts/verify_distribution.py
```

已有本机 Chromium 时可通过 PLAYWRIGHT_CHROMIUM_EXECUTABLE 指定完整可执行路径。浏览器验收仅使用隔离 workspace 与合成 PNG，记录位于 `.artifacts/reports/native-web`。

新报告、临时数据和缓存放在 `.artifacts`。原始照片、真实数据集、既有 dev workspace 和旧 runtime 保留。固定源码、构建边界与验收记录见 [native-web.md](native-web.md)。

## 模块与产物入口

[七模块导航](../architecture/module-map.md)列出代码、公开入口和验证范围。根命令 pnpm test／typecheck 委托私有 UI 包；pnpm check:boundaries 检查 Python 与界面依赖方向。根无前端运行依赖，不执行根 pnpm install。

Python 中间产物为 .artifacts/build/python，发行物为 .artifacts/dist。直接构建使用 `uv run --locked --no-sync python -m build --installer uv --outdir .artifacts/dist`；scripts/build_release.py 先构建网页再生成发行物。

本次重构的实际验收环境、命令文件占用说明和证据见[文件重构验收](restructure-acceptance.md)。需要复用验收环境时显式设置 `UV_PROJECT_ENVIRONMENT="$PWD/.artifacts/venvs/restructure"`；不修改已有默认 workspace 或 MCP 注册。
