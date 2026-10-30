# 开发、测试与发行

本文是环境准备、角色交接和命令的唯一操作入口。产品目标见[需求](../requirements/README.md)，模块职责见[架构](../architecture/overview.md)，有效状态见[当前上下文](current-context.md)。

需要 Python 3.12、uv、Node `>=26.8.2 <27`、pnpm 11.13.1，工具须在当前进程 PATH 可用；不修改全局环境。依赖锁为根 `uv.lock` 和 `frontend/pnpm-lock.yaml`，根 package.json 是任务入口，不执行根 pnpm install。

首次 clone 的工具自动准备与启动见根 [Quickstart](../../README.md#quickstartwindows-x64)。工具尚未在 PATH 时用 `scripts/bootstrap.ps1` 转发本页参数；`--watch` 转发给 Vite 入口。自动准备只支持 Windows x64，其他平台单独验证。

## 并行开发与交接

一个长期 Git Manager Chat、多个独立 Feature Chat；集成分支为 `dev`。默认模型 GPT-6.1 Sol High，独立 Reviewer 不继承开发聊天历史。

1. Manager 核对 dev、工作区和已有 Worktree，从确认的已提交 SHA 创建 `codex/<feature>`；复用 Codex 创建的空间并核对实际分支。用户要求时才创建 Feature Chat。
2. 交接基点、分支、路径、工具／缓存位置及准备等级：源码空间、开发依赖、空 workspace、预览分别说明；不把创建 Chat 自动扩展为构建和启动。
3. 指定一方执行下方固定入口，另一方读取回执。Manager 使用带 cursor 的状态等待，失败、需用户处理或完成时再读详情；初始化交接不重复整套核对。
4. Feature 按最终需求实现、编写必要测试、构建及提供独立预览，默认不执行测试套件或综合验收。用户确认可集成后，按授权整理待审提交并暂停修改准确 SHA。
5. 用户可用下方一次交付 Prompt 一并授权审查、测试、修复、本地合并、普通推送、Feature 空间清理及 Feature Chat 归档。Manager 按此顺序串行执行，不再逐步请求相同授权；审查或验证未通过则不合并、不推送，远端 dev 未包含最终提交则不清理。清理须先保留必要证据和数据，再删除该 Feature 的 workspace、私有 runtime、已合并分支及可安全删除的 Worktree，归档对应 Feature Chat；保留 Git Manager Chat 和其他 Feature。用户明确要求暂不推送或保留空间时，以该要求为准。main、tag 和正式发布仍须另行授权；demo 只表示验收环境。Git 忽略的运行数据不能靠 Git 快照恢复。

两个角色的交接 Prompt 只需包含：角色、当前需求、授权范围及基点／路径；操作规则引用本页，不复制整套命令。最终 Brief 默认放聊天：

```text
Feature / 最终需求:
Branch / Base / Commit:
准备回执 / 预览及对应版本:
已执行验证 / 已编写未执行测试 / 待验证项:
跨仓库依赖: [涉及时填写Bundle准确版本与SHA]
```

### 用户操作 Prompt（四步）

**1. 在 Git Manager Chat 创建 Feature**

```text
请为 Feature「名称」准备独立开发空间，并创建 Feature Chat。

需求：
- 目标：[解决什么问题]
- 范围：[需要实现什么]
- 预期行为：[用户操作后应该发生什么]
- 验收点：[如何判断完成]
- 不包含：[本次明确不做的内容]

遵守 AGENTS.md 和 docs/development/README.md。
核对当前 dev、未提交内容及已有 Worktree，优先复用对应空间。
从确认的已提交 dev 基点准备 codex/<feature> 分支及独立 Worktree。
准备等级：[源码空间／开发依赖与空 workspace／构建并启动独立预览]。
使用固定准备入口，将准确基点 SHA、分支、路径、环境和回执交接给 Feature；
启动预览时提供实际地址。如涉及独立 Bundle 仓库，分别交接准确基点。
不修改正常 dev 实例、默认 workspace 或全局 MCP；暂不推送、不合并。
```

**2. 在 Feature Chat 开发**

```text
请按交接信息实现 Feature「名称」。
遵守 AGENTS.md 和 docs/development/README.md，只在本 Feature 空间工作。
按最新需求做最小实现，编写必要测试，完成构建和类型检查，
提供独立预览并说明对应源码版本。
默认不执行测试套件或综合验收，由 Manager 在集成阶段组织。
产品选择不明确时询问我，常规实现选择自行处理。不自行合并或推送。
```

**3. 在 Feature Chat 整理交付**

```text
开发完成，请整理本地待审提交和最终 Brief。
允许本地提交，不推送、不合并。
按开发流程的 Brief 格式提供最终需求、验收点、各仓库准确 SHA、
预览版本、已完成检查、已编写未执行测试、待验证项、已知限制及跨仓库依赖。
交接后暂停修改待审版本；如需继续修改，重新提交并更新 Brief。
```

**4. 回到 Git Manager Chat，一次授权交付**

```text
确认该 Feature 可以集成，并授权通过后推送、清理空间及归档 Feature Chat。
请遵守 AGENTS.md 和 docs/development/README.md，按以下 Brief 连续完成：

1. 组织独立上下文 Reviewer 只读审查，执行必要测试和最小修复，
   对受影响范围复审复测；通过后将准确候选本地合并到干净的 dev。
2. 核对本地与远端 dev，通过普通推送将已集成提交推送到 origin/dev。
   涉及平台和 Bundle 时，分别核对并推送两个仓库。
3. 确认远端 dev 已包含最终候选、Feature 工作区无未提交内容，
   检查 MCP 或其他配置是否仍引用该空间；存在未安全处理的引用时保留空间并报告。
   停止本 Feature 的准确实例（含 Vite），将必要证据和数据保留到待删除空间之外并核验，
   删除本 Feature 原有 workspace、私有 runtime、已合并分支及可安全删除的 Worktree。
4. 归档对应的原 Feature Chat，保留当前 Git Manager Chat 和其他 Feature Chat。

以上步骤无需再次逐项确认；出现阻塞时保留可恢复状态并报告，
不要越过失败步骤继续推送或清理；被占用或无法安全删除的内容如实报告，不强行关闭用户应用。
不强制推送、不修改 main、不发布 tag，不影响正常 dev 或其他 Feature。
报告各仓库远端最终 SHA、验证结果、证据位置、workspace 删除及 Chat 归档结果和未解决项。

[粘贴 Feature 最终 Brief]
```

## 安装与构建

在当前 Worktree 根目录执行。下面创建独立开发依赖和空 workspace，不构建、不安装 CPU runtime、不启动服务：

```powershell
pnpm dev:prepare --workspace .artifacts/workspaces/feature --service-port 32590 --comfyui-port 32588
```

入口设置进程级隔离环境，使用本 Worktree 的 `.artifacts/venvs/dev`、`frontend/node_modules`、runtime 和 workspace；不借用其他 checkout 的 venv 或 node_modules，不共用可变 runtime。数据库、令牌、图、软件副本和输入输出独立；默认 workspace 与全局 MCP 不变。

包缓存通过 `--cache-dir <已约定的长期缓存目录>` 或 `ASTROPHOTOFLOW_DEV_CACHE` 复用，由包管理器维护，不复制整套缓存、不直接修改其他 Feature 的缓存。`--offline` 明确使用离线包和元数据；缺失时根据日志补齐，不反复尝试网络。工具和权限问题在实际失败步骤处理，不改产品路径解析或全局 Git 配置。

终端输出及 `.artifacts/dev-prepare.json` 是本次回执，包含 SHA、脏状态、路径、各阶段耗时、日志和实际地址；失败不表示已准备好。相同输入和完整本地依赖再次准备会跳过安装。成功读取回执，失败读取对应阶段日志；不为等长命令不断搜索源码。

需要完整构建时：

```powershell
pnpm build
```

构建包含 UI 包／原生应用类型检查和网页打包，输出 `.artifacts/build/frontend`；`frontend/build` 是源码。创建同基点 Feature 优先使用已确认 SHA 的网页产物，不能把 unknown 或其他提交当作当前版本。实际开发后的必要构建仍保留。

## 隔离运行与预览

需要预览时显式启动。入口使用已有本地网页；也可传 `--frontend-assets <同HEAD的构建目录>`。缺少产物时明确失败，首次需要构建则显式加 `--build`：

```powershell
pnpm dev:prepare --workspace .artifacts/workspaces/feature --start
pnpm build:watch --workspace .artifacts/workspaces/feature --port 32589 --strictPort
```

打开 Vite 实际输出的 URL。入口自动使用本地 Python 环境及指定 workspace 的实际网页地址，代理原生 API／WebSocket；Vue／TypeScript／CSS 由 Vite 更新。静态网页的构建 SHA 和当前源码的脏状态分别交接，不将开发预览当成已发布构建。

平台后端 Python 修改后显式停止并重新启动自己的实例；需要同步新静态网页或引擎时先停止，再使用 `--build --start`：

```powershell
pnpm dev:prepare --workspace .artifacts/workspaces/feature --stop
pnpm dev:prepare --workspace .artifacts/workspaces/feature --start
```

固定 runtime 仅在归档、依赖和版本匹配且上次准备完成时复用。准备失败不写就绪回执。首次 runtime 使用本空间 Python 和缓存，不启停或更新正常 dev。Vite 是开发工具，产品仍只有两个常驻服务。

CLI 的 `apf runtime prepare` 独立准备软件；`apf workspace create --workspace <路径>` 只建配置和目录，可用 `--frontend-assets` 同步已有网页。`apf init` 保留为完整初始化入口，自动复用就绪 runtime；`--no-activate` 保持默认 workspace，`--reuse-runtime` 要求已有完整环境。产品使用见[工作台](workbench.md)，参数以 `--help` 为准。

CLI、浏览器和 MCP 各自核对目标；Shell 环境不会重定向已连接的 MCP。MCP 使用明确绑定该 workspace 的独立 stdio 进程，不改全局注册。端口以 core 返回地址为准，不猜测。

### 独立Bundle候选预览

Siril 在独立私有仓库维护；不因普通 Feature 初始化而准备 Bundle。需要候选预览时，按授权取得干净且 HEAD 等于开发 tag 的 checkout，再导出目录：

```powershell
uv run --locked --no-sync python scripts/export_bundle_catalog.py <Bundle路径> --repository <同一Bundle路径> --tag <开发tag> --output .artifacts/siril-preview-catalog.json
$env:ASTROPHOTOFLOW_BUNDLE_CATALOG = "$PWD/.artifacts/siril-preview-catalog.json"
```

目录只属于自己的启动进程，不改默认发布目录。安装继续走网页确认，核对程序版本、节点与 Bundle SHA。已安装 Bundle 的 SDK Python 适配器和声明 JSON 支持热加载；平台后端 Python 仍显式重启。未提交、未安装或未真实运行分别说明。

## 验证入口

以下由 Manager 在集成阶段按范围选择，Feature 默认只编写测试、构建与提供预览：

```powershell
uv run --locked --no-sync pytest -q
pnpm test
pnpm check:boundaries
```

浏览器验收使用 core 返回的实际网页地址及独立 workspace、合成素材；已有 Chromium 可通过 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 指定。入口 `pnpm test:browser`，默认报告在 `.artifacts/reports/native-web`。不操作真实素材。

结果写[验证记录](test-matrix.md)，完整日志进 `.artifacts`；实现、构建、启动就绪、功能验证和用户验收分别报告，已通过检查不无故重复。

## 发行与安装验证

```powershell
uv run --locked --no-sync python scripts/build_release.py
uv run --locked --no-sync python scripts/verify_distribution.py
```

仅开发版本，正式发布另行批准。发行物在 `.artifacts/dist`，Python 中间产物在 `.artifacts/build/python`；wheel 携带网页与固定引擎，用户不需要 Node。已有网页时可单独重打 Python 包；发行验证的独立目录、报告和离线重建参数见脚本 `--help`，不把非隔离构建或未验证平台写成通过。
