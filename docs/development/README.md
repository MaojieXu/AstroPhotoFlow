# 开发、测试与发行

产品范围与阶段验收以[现行需求](../requirements/README.md)为准，模块权威与调用边界见[总架构](../architecture/overview.md)，当前任务及必要验收见[当前计划](implementation-plan.md)。本文集中维护协作流程、开发及发行命令，不把待实现目标写成现有能力。

集成分支为 `dev`，每个 Worktree 的 Python 环境为 `.artifacts/venvs/dev`。需要 Python 3.12、uv、Node `>=26.8.2 <27` 和 pnpm 11.13.1；依赖锁为根 `uv.lock` 与 `frontend/pnpm-lock.yaml`。

## 并行开发与交接

一个长期 Git Manager Chat、多个独立 Feature Chat，集成时使用独立 Review Subagent；默认均用 GPT-6.1 Sol High。流程按需执行，不增加任务台账或全套设计文档前置要求。

1. **准备**：Manager 核对工作区与已有 Worktree，从确认的已提交 `dev` 基点创建 `codex/<feature>` 分支及独立空间；复用 Codex 已创建的对应 Worktree，验证分支而不假定 detached HEAD 已有分支。按用户明确要求创建 Feature Chat，交接基点 SHA、路径和环境信息，不夹带未提交修改。
2. **开发**：Feature 按用户最新明确要求做最小实现，编写必要测试、构建及类型编译并更新自己的预览，默认不执行测试套件或综合验收。共享契约先由一个 Feature 负责对齐共同提交版本；不靠各分支复制草案。报告源码与预览对应版本，健康就绪和构建成功不等于功能通过。
3. **交接**：用户明确确认可以集成后，Feature 按授权整理本地待审提交，提供下列 Brief 并暂停修改待审版本。新需求或代码变化须重新交接准确 SHA；此时状态为 Ready for Review。
4. **审查与合并**：Manager 启动不继承开发聊天历史的 Reviewer，只提供最终需求、必要约束、基点和候选 SHA；Reviewer 只找问题、不修改。Manager 按变更范围执行测试、最小修复并对受影响范围复审复测；需求争议交还用户。确认 `dev` 干净且无其他集成操作后合并准确候选并做必要集成验证；复杂冲突或高风险改动才使用临时集成 Worktree。失败时保留可恢复状态，不宣称集成成功。
5. **交付与清理**：Manager 只更新受影响的现行文档，实际验证结果进验证矩阵、日志进 `.artifacts`。默认本地交接，推送按授权，现有 CI 保持；`demo` 是指定提交的验收环境，推进 `main` 与正式发布另行授权。获准清理后先停止准确实例，保留必要证据和数据；Git 忽略的 `.artifacts` 不靠 Git 快照保存。

Brief 默认放 Feature 最终消息，无需新建文件：

```text
Feature: [名称]
最终需求／验收点: [最终行为，重要调整或限制]
Branch / Base / Commit: [分支／基点 SHA／待审 SHA]
预览: [地址及对应版本；没有则说明]
测试: [已编写但未执行的测试、关键待验证项]
跨仓库依赖: [仅涉及时填写 Bundle 等准确版本／提交]
```

### Git Manager Prompt

```text
你是 AstroPhotoFlow 的 Git Manager，遵守 AGENTS.md 与 docs/development/README.md。
本次任务：[准备并创建某个 Feature Chat／集成某分支及 SHA／清理已授权资源]。
负责隔离空间和串行 dev 集成；集成时启动独立上下文 Reviewer，由你执行测试与最小修复，需求争议交还用户。
报告实际分支、路径、提交、验证范围及未解决项；推送、main 和正式发布按单独授权。
```

### Feature Developer Prompt

```text
你是当前独立 Worktree 的 Feature Developer，遵守 AGENTS.md 与 docs/development/README.md。
本次需求：[用户当前需求]。
按用户最新明确要求做最小实现，编写必要测试、构建并提供独立预览；默认不执行测试套件或综合验收。
只在当前分支工作。用户确认可以集成后，整理本地待审提交和最终 Brief，明确预览版本与未验证项，不自行合并或推送。
```

## 安装与构建

以下 Windows 命令在当前 Worktree 根目录执行；每个新终端先设置同样的进程环境，不写入全局配置。纯文档任务无需安装或启动应用。

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$PWD/.artifacts/venvs/dev"
$env:UV_PYTHON_INSTALL_DIR = "$PWD/.artifacts/python"
$env:UV_CACHE_DIR = "$PWD/.artifacts/cache/uv"
$env:LOCALAPPDATA = "$PWD/.artifacts/local-app-data"
$env:TEMP = "$PWD/.artifacts/tmp"
$env:TMP = $env:TEMP
$env:ASTROPHOTOFLOW_CONFIG = "$PWD/.artifacts/workspaces/feature/config.toml"
New-Item -ItemType Directory -Force -Path $env:LOCALAPPDATA, $env:TEMP | Out-Null
uv sync --locked --extra dev --python 3.12
pnpm --dir frontend install --frozen-lockfile --ignore-scripts --store-dir "$PWD/.artifacts/cache/pnpm"
pnpm build
```

根 package.json 只提供任务入口，不执行根 pnpm install。`pnpm build` 生成固定引擎归档、检查私有 UI 包和原生应用类型，再构建完整网页。网页输出为 `.artifacts/build/frontend`；`frontend/build` 是上游构建源码。

进程级 `LOCALAPPDATA` 让现有代码选择该 Worktree 的独立 CPU runtime；不要依赖受限环境偶然重定向。前端依赖在本 Worktree 安装，不借用其他 checkout 的 `node_modules`。workspace 内的 SQLite、令牌、原生图、软件副本、输入输出及临时目录各自独立。

## 验证入口

以下是 Manager 集成阶段的可用入口，按改动选择范围，不默认全跑；Feature 默认只编写测试、构建和提供预览。用户本次明确要求优先。

```powershell
uv run --locked --no-sync pytest -q
pnpm test
pnpm check:boundaries
```

根 `pnpm test`／`typecheck` 委托私有 UI 包，完整原生类型检查包含在构建中。模块依赖方向由 `check:boundaries` 检查。测试位置见[模块导航](../architecture/module-map.md)，结果与缺口见[验证矩阵](test-matrix.md)。

## 隔离运行与预览

沿用上面的进程环境。32588／32590 仅为示例，Manager 为每个实例选择未占用端口；启动后核对实际地址和 workspace 身份。

```powershell
uv run --locked --no-sync apf init --workspace .artifacts/workspaces/feature --service-port 32590 --comfyui-port 32588 --frontend-assets .artifacts/build/frontend --no-activate
uv run --locked --no-sync apf start --workspace .artifacts/workspaces/feature
uv run --locked --no-sync apf status --workspace .artifacts/workspaces/feature
```

更新预览先用 `apf stop --workspace .artifacts/workspaces/feature` 停止自己的实例，再同步并启动。自己的完整 runtime 与归档哈希匹配时，初始化加 `--reuse-runtime` 只同步网页；引擎变化时仍只重建自己的 runtime。`init --no-activate` 保持默认 workspace；start／stop／restart不改变默认位置，也没有该参数。不启停或更新正常 dev。

CLI、浏览器和 MCP 分别核对目标；设置 Shell 环境不会重定向已连接的 MCP。MCP 验证使用明确绑定该 workspace 的独立 stdio 进程，不修改全局注册。

源码开发时，在已就绪的独立实例上运行以下命令，并打开 Vite 输出的地址。入口通过 core 状态查询选定 workspace 的实际网页地址，代理原生 API／WebSocket；Vue、TypeScript 和 CSS 修改由 Vite 自动更新，无需重新构建和同步静态网页。

```powershell
pnpm build:watch --workspace .artifacts/workspaces/feature --port 32589 --strictPort
```

`--workspace` 省略时沿用当前配置选择。Vite 是开发工具，发布与正常运行仍使用构建网页和两个产品服务。平台后端 Python 源码变化仍需显式重启；已安装 Bundle 的 SDK Python 适配器、清单、操作及节点 JSON 变化由原生进程检测并重新加载，安装／更新／卸载也直接刷新当前页面的节点目录。维护行为以[软件和节点需求](../requirements/README.md#fr-03-软件适配与能力目录)为准。

### 独立Bundle候选预览

Bundle须先按根规则取得本地提交／新开发tag授权；不移动旧tag，不把脏源码标成已有SHA。授权后可从干净且HEAD等于tag的独立checkout导出本地预览目录：

```powershell
python scripts/export_bundle_catalog.py .artifacts/bundles/AstroPhotoFlow-Siril --repository "$PWD/.artifacts/bundles/AstroPhotoFlow-Siril" --tag v0.2.0-dev.1 --output .artifacts/siril-preview-catalog.json
$env:ASTROPHOTOFLOW_BUNDLE_CATALOG = "$PWD/.artifacts/siril-preview-catalog.json"
```

该变量仅属于启动终端及其独立子进程；停止／启动时仍明确自己的workspace。随后走软件安装计划与当前网页确认，重启后核对程序版本、节点加载与Bundle SHA。目录覆盖只选择固定候选，不绕过安装确认，也不发布GitHub tag。源码未提交、未安装或仅静态资源就绪时须如实标注；不要据此声明节点功能通过。

浏览器验收由 Manager 在集成阶段按需执行，使用 `status` 的实际地址：

```powershell
$featureState = uv run --locked --no-sync apf status --workspace .artifacts/workspaces/feature | ConvertFrom-Json
$env:APF_WEB_URL = $featureState.web_url
pnpm --dir frontend exec playwright install chromium
pnpm test:browser
```

已有 Chromium 时可用 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指定可执行文件。浏览器使用隔离 workspace 与合成 PNG，默认报告在 `.artifacts/reports/native-web`。真实开发数据不用于导入、回收站或工作流写入验收。正常 dev 配置基线为 31388／31390，实时状态须查询，本机工具见[当前上下文](current-context.md)。

配置由 `astrophotoflow.core.config` 统一解析：显式配置路径、`ASTROPHOTOFLOW_CONFIG`、用户`~/.config/astrophotoflow/config.toml`中的`[workspace] default`依次优先，最后读取所选workspace/config.toml。不再读取旧active-workspace；没有默认位置时明确指定目标。`storage.data_dir` 相对所属 TOML 解析，`Settings.workspace`为其父目录。CLI/MCP 用进程级环境选择隔离实例，不改全局注册。当前已提供真实启动采用、端口回写及网页配置；实际地址以CLI结构化回执为准，restart繁忙或无法确认时拒绝。网页配置从原生设置中的工作台进入，实际进度见当前上下文。

## 发行与安装验证

```powershell
uv run --locked --no-sync python scripts/build_release.py
uv run --locked --no-sync python scripts/verify_distribution.py
```

发行脚本安装锁定前端依赖、构建网页并生成 wheel／sdist。Python 中间产物为 `.artifacts/build/python`，发行物为 `.artifacts/dist`。网页已构建、仅重新打 Python 包时，可用 `python -m build --installer uv --outdir .artifacts/dist`。

wheel 携带完整网页与固定引擎；sdist 携带预构建网页，支持无 Node 的 wheel 重建。验证脚本在源码目录外安装两份 wheel，检查入口、迁移、资源和源码包范围。用户安装步骤见[工作台使用](workbench.md)。

验证候选发行物且保留既有 `.artifacts/dist` 时，可向 `scripts/verify_distribution.py` 传入 `--dist`、`--report`、`--rebuilt-wheel-dir`。需要严格仓库外安装时，用`--temp-dir <仓库外可写路径>`放置临时venv和解压源；脚本会检查并报告位置。在不允许build隔离环境访问包索引的机器上，可用`--sdist-build-python <预装setuptools>=77.0.3的Python>`指定Node-free重建解释器；报告会标示是否隔离构建，不能将非隔离重建表述为隔离依赖下载通过。

新日志、临时数据、缓存和报告进入 `.artifacts`。保留原件、既有 workspace、令牌与旧 runtime；未验证的平台和依赖不得写成通过。
