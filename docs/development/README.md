# 开发、测试与发行

本文是环境准备、角色交接和命令的唯一操作入口。产品目标见[需求](../requirements/README.md)，模块职责见[架构](../architecture/overview.md)，有效状态见[当前上下文](current-context.md)。

源码、生成物、安装副本、workspace和缓存的归属、写入者及实际读取链统一见[文件归属与读写关系](../architecture/repository-layout.md)。

需要 Python 3.12、uv、Node `>=26.8.2 <27`、pnpm 11.13.1，工具须在当前进程 PATH 可用；不修改全局环境。依赖锁为根 `uv.lock` 和 `frontend/pnpm-lock.yaml`，根 package.json 是任务入口，不执行根 pnpm install。

首次 clone 的工具自动准备与启动见根 [Quickstart](../../README.md#quickstartwindows-x64)。工具尚未在 PATH 时用 `scripts/bootstrap.ps1` 转发本页参数；`--watch` 转发给 Vite 入口。自动准备只支持 Windows x64，其他平台单独验证。

## 并行开发与交接

一个长期 Git Manager Chat、多个独立 Feature Chat；集成分支为 `dev`。默认模型 GPT-6.1 Sol High，独立 Reviewer 不继承开发聊天历史。

1. Manager 核对 dev、工作区和已有 Worktree，从确认的已提交 SHA 创建 `codex/<feature>`；复用 Codex 创建的空间并核对实际分支。用户要求时才创建 Feature Chat。
2. Feature空间默认准备到可见的独立前端：源码空间、开发依赖、空workspace、前端构建、私有CPU runtime、双服务启动及页面展示连续完成。用户明确要求源码空间或依赖等较低等级时才提前结束。交接基点、分支、路径、工具／缓存位置及实际完成等级。
3. 指定一方执行下方固定入口，另一方读取回执。Manager 使用带 cursor 的状态等待，失败、需用户处理或完成时再读详情；初始化交接不重复整套核对。Manager 交接原 Manager Chat 和对应 Feature Chat 的准确标识及可用的 host 标识；准备完成后，主动向该 Feature Chat 发送下方开发指令并启动开发，用户无需再发送开始指令。发送失败时明确报告，不将准备就绪描述为开发已启动。
4. Feature 按最终需求实现、编写必要测试、构建及提供独立预览，默认不执行测试套件或综合验收。用户在 Feature Chat 反馈、试用和调整需求，满意后授权整理本地待审提交。Feature 冻结准确 SHA，整理完整 Brief，主动发送回原 Manager Chat，并在 Feature Chat 展示 Brief 和发送结果；用户无需手动复制。继续修改须另作提交并回传更新后的 Brief。无法定位原 Chat 或发送失败时明确报告，不将未发送描述为已交接。
5. Brief 回传仅为交接，不代表授权集成；Manager 收到后等待用户确认。用户可用下方一次交付 Prompt 一并授权审查、测试、修复、本地合并、普通推送、Feature 空间清理及 Feature Chat 归档，Manager 使用对应 Feature 最新冻结的 Brief，不要求用户再次粘贴。Manager 按此顺序串行执行，不再逐步请求相同授权；审查或验证未通过则不合并、不推送，远端 dev 未包含最终提交则不清理。清理时删除该 Feature 的 workspace、私有 runtime、已合并分支及可安全删除的 Worktree，包含其中的证据、运行数据、依赖和缓存，不额外备份或迁移保留副本；已提交到 Git 的源码和验证记录继续保留。归档对应 Feature Chat，保留 Git Manager Chat 和其他 Feature。只删除本 Feature 私有路径，不删除外部引用的原始素材或共享缓存。用户明确要求暂不推送或保留空间时，以该要求为准。main、tag 和正式发布仍须另行授权；demo 只表示验收环境。Git 忽略的运行数据删除后不能靠 Git 恢复。

两个角色的交接 Prompt 只需包含：角色、当前需求、授权范围及基点／路径；操作规则引用本页，不复制整套命令。最终 Brief 默认放聊天：

```text
Feature / 最终需求:
Branch / Base / Commit:
准备回执 / 预览及对应版本:
已执行验证 / 已编写未执行测试 / 待验证项:
跨仓库依赖: [涉及时填写Bundle准确版本与SHA]
```

### 用户操作 Prompt（三步）

用户只需创建 Feature、要求整理交付、确认集成。开发开始指令由 Manager 自动发送，最终 Brief 由 Feature 主动回传；开发期间用户直接在 Feature Chat 试用、反馈和调整需求。

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
准备等级：默认完整准备并展示独立前端；仅在这里明确指定较低等级时提前结束。
由指定的一方使用bootstrap固定入口，默认传入--build --start，连续完成依赖、网页构建、私有runtime和双服务启动。
就绪后使用回执返回的web_url打开页面并确认加载，交接准确SHA、分支、路径、环境、回执和实际地址。
分别报告服务就绪、页面打开请求及实际展示结果；queued不等于页面已展示。如涉及独立Bundle仓库，分别交接准确基点。
准备完成后，由你向对应 Feature Chat 发送开发指令并启动开发，
同时交接原 Git Manager Chat 的准确标识，供完成后主动回传 Brief。
不修改正常 dev 实例、默认 workspace 或全局 MCP；暂不推送、不合并。
```

**2. 开发满意后，在 Feature Chat 整理并回传交付**

```text
开发完成，请整理本地待审提交和最终 Brief，
并将完整 Brief 主动发送回创建本 Feature 的原 Git Manager Chat。
同时在当前 Feature Chat 展示 Brief 和发送结果。
允许本地提交，不推送、不合并。
按开发流程的 Brief 格式提供最终需求、验收点、各仓库准确 SHA、
预览版本、已完成检查、已编写未执行测试、待验证项、已知限制及跨仓库依赖。
交接后暂停修改待审版本，等待用户授权 Manager 集成。
如需继续修改，重新提交并向 Manager 发送更新后的 Brief。
无法定位原 Manager Chat 或发送失败时明确报告，
不将未发送描述为已交接。
```

**3. 回到 Git Manager Chat，确认集成并一次授权交付**

```text
确认 Feature「名称」可以集成，并授权通过后推送、清理空间及归档 Feature Chat。
请使用该 Feature 已回传的最新冻结 Brief，
遵守 AGENTS.md 和 docs/development/README.md，连续完成：

1. 组织独立上下文 Reviewer 只读审查，执行必要测试和最小修复，
   对受影响范围复审复测；通过后将准确候选本地合并到干净的 dev。
2. 核对本地与远端 dev，通过普通推送将已集成提交推送到 origin/dev。
   涉及平台和 Bundle 时，分别核对并推送两个仓库。
3. 确认远端 dev 已包含最终候选、Feature 工作区无未提交内容，
   检查 MCP 或其他配置是否仍引用该空间；存在未安全处理的引用时保留空间并报告。
   停止本 Feature 的准确实例（含 Vite），删除本 Feature 原有 workspace、私有 runtime、
   已合并分支及可安全删除的 Worktree，包括其中的证据、运行数据、依赖和缓存。
   不额外备份或迁移保留副本；已提交到 Git 的源码和验证记录继续保留。
   只删除本 Feature 私有路径，不删除外部引用的原始素材或共享缓存。
4. 归档对应的原 Feature Chat，保留当前 Git Manager Chat 和其他 Feature Chat。

以上步骤无需再次逐项确认；出现阻塞时保留可恢复状态并报告，
不要越过失败步骤继续推送或清理；被占用或无法安全删除的内容如实报告，不强行关闭用户应用。
不强制推送、不修改 main、不发布 tag，不影响正常 dev 或其他 Feature。
报告各仓库远端最终 SHA、验证结果、已提交的验证记录位置、空间删除及 Chat 归档结果和未解决项。
```

### Manager 自动发送的开发指令

以下指令由 Manager 在空间准备和交接完成后发送给对应 Feature Chat，不是用户的额外步骤。发送时填入准确 Feature 名称及原 Manager Chat 标识，附上已核对的准备交接信息。

```text
请按交接信息实现 Feature「名称」。
原 Git Manager Chat：[准确 Chat 标识及可用的 host 标识]。
遵守 AGENTS.md 和 docs/development/README.md，只在本 Feature 空间工作。
按最新需求做最小实现，编写必要测试，完成构建和类型检查，
提供独立预览并说明对应源码版本。
默认不执行测试套件或综合验收，由 Manager 在集成阶段组织。
产品选择不明确时询问用户，常规实现选择自行处理。不自行合并或推送。
用户要求整理交付后，本地提交并冻结准确 SHA，
将完整最终 Brief 主动回传上述 Manager Chat，在当前 Chat 展示 Brief 和发送结果。
回传不代表获准集成；交接后暂停修改，等待用户确认。
继续修改须另作提交并回传更新后的 Brief；无法定位或发送失败时明确报告。
```

## 安装与构建

在当前Worktree根目录执行。Feature默认通过bootstrap选择本地工具、安装／复用依赖、构建网页、准备私有CPU runtime并启动两个服务：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 --workspace .artifacts/workspaces/feature --service-port 32590 --comfyui-port 32588 --build --start
```

启动后按下方[页面展示](#页面展示)完成交接。只有用户明确要求仅准备开发依赖和空workspace时，省略`--build --start`；底层`pnpm dev:prepare`仍保持只准备依赖和workspace的语义，且要求当前进程PATH已选好工具。

同一Worktree已有仍在使用的runtime时，可显式传`--runtime-dir .artifacts/runtimes/<本任务名称>`准备另一私有runtime；路径必须位于当前Worktree的`.artifacts`内。该参数仅作用于本次子进程环境及回执，不修改默认runtime或全局设置。新workspace仍需显式指定，启动前检查目标端口，不用旧成功回执判断进程已经停止。

入口设置进程级隔离环境，使用本 Worktree 的 `.artifacts/venvs/dev`、`frontend/node_modules`、runtime 和 workspace；不借用其他 checkout 的 venv 或 node_modules，不共用可变 runtime。数据库、令牌、图、软件副本和输入输出独立；默认 workspace 与全局 MCP 不变。

包缓存按`--cache-dir <已约定的长期缓存目录>`、`ASTROPHOTOFLOW_DEV_CACHE`、本Worktree的`.artifacts/cache`依次选择，bootstrap工具阶段与依赖阶段共用所选位置。由包管理器维护，不复制整套缓存、不直接修改其他Feature的缓存。托管Python安装在本空间`.artifacts/managed-python`，工具在`.artifacts/toolchains`，两者不互相链接。`--offline`明确使用离线包和元数据；缺失时根据日志补齐，不反复尝试网络。工具和权限问题在实际失败步骤处理，不改产品路径解析或全局Git配置。

`.artifacts/dev-prepare.json`是最新调用回执，包含调用标识、参数、起止时间、从bootstrap开始的总耗时、SHA、脏状态、路径、阶段日志及实际地址。开始即清除旧成功状态；日志按调用标识保存在`.artifacts/logs/dev-prepare/<run_id>`。终端Python结果输出后bootstrap还会补齐最终总耗时，交接以磁盘最终回执为准。`completed`表示本次请求完成，`ready`表示服务就绪，都不表示页面已经展示。相同输入和完整本地依赖再次准备会跳过安装。成功读取回执，失败读取对应阶段日志；不为等长命令不断搜索源码。

需要完整构建时：

```powershell
pnpm build
```

构建包含 UI 包／原生应用类型检查和网页打包，输出 `.artifacts/build/frontend`；`frontend/build` 是源码。创建同基点 Feature 优先使用已确认 SHA 的网页产物，不能把 unknown 或其他提交当作当前版本。实际开发后的必要构建仍保留。

## 隔离运行与预览

默认完整准备使用上述`--build --start`。已有经过确认的同SHA网页时，可省略`--build`或传`--frontend-assets <同HEAD的构建目录>`复用；缺少或版本不匹配时明确失败，不把unknown或其他提交当作当前版本：

```powershell
pnpm dev:prepare --workspace .artifacts/workspaces/feature --start
pnpm build:watch --workspace .artifacts/workspaces/feature --port 32589 --strictPort
```

默认展示静态网页。需要热更新时才运行上面的`build:watch`，并打开Vite实际输出的URL。入口自动使用本地Python环境及指定workspace的实际网页地址，代理原生API／WebSocket；Vue／TypeScript／CSS由Vite更新。静态网页的构建SHA和当前源码的脏状态分别交接，不将开发预览当成已发布构建。

### 页面展示

Agent读取本次调用回执，核对源码SHA、workspace、`completed`及`ready`，使用`preview.web_url`打开页面，不猜测配置端口。页面打开属于Agent交接动作，不在产品启动脚本中调用系统默认浏览器。

通过浏览器工具确认实际URL、工作台已渲染且没有停在加载或错误页，再报告展示完成。仅HTTP成功或打开请求返回`queued`时，只报告服务就绪／打开请求已提交，保留可点击地址；不能声称页面已经展示。此检查只确认预览加载，不替代功能或用户验收。

交接分别记录空间创建、工具／依赖、网页构建、runtime、服务启动及页面展示的耗时与结果。脚本总耗时不包含创建Worktree、Agent打开页面和用户指令之间的等待，不能混为端到端总耗时。

平台后端 Python 修改后显式停止并重新启动自己的实例；需要同步新静态网页或引擎时先停止，再使用 `--build --start`：

```powershell
pnpm dev:prepare --workspace .artifacts/workspaces/feature --stop
pnpm dev:prepare --workspace .artifacts/workspaces/feature --start
```

固定 runtime 仅在归档、依赖和版本匹配且上次准备完成时复用。准备失败不写就绪回执。首次 runtime 使用本空间 Python 和缓存，不启停或更新正常 dev。Vite 是开发工具，产品仍只有两个常驻服务。

CLI 的 `apf runtime prepare` 独立准备软件；`apf workspace create --workspace <路径>` 只建配置和目录，可用 `--frontend-assets` 同步已有网页。`apf init` 保留为完整初始化入口，自动复用就绪 runtime；`--no-activate` 保持默认 workspace，`--reuse-runtime` 要求已有完整环境。产品使用见[工作台](workbench.md)，参数以 `--help` 为准。

CLI、浏览器和 MCP 各自核对目标；Shell 环境不会重定向已连接的 MCP。MCP 使用明确绑定该 workspace 的独立 stdio 进程，不改全局注册。端口以 core 返回地址为准，不猜测。

### 独立Bundle候选预览

#### 开发源码绑定

在本 Feature workspace 中，固定入口可直接绑定独立 Bundle Worktree：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 --workspace .artifacts/workspaces/node-ui-bundle --bundle-source siril=.artifacts/bundles/AstroPhotoFlow-Siril --start
```

首次平台代码／网页修改仍先停止自己的实例，再使用 `--build --start`。绑定记录只写入该workspace的 `run/bundle-sources.json`，两个服务共享；不更改默认workspace、全局MCP或已安装Bundle副本。Siril Worktree的 `development.json` 声明Python生成入口和作者资料／辅助文件监听范围，使用本空间开发Python生成。之后修改Bundle源码会自动生成、校验、热加载并刷新节点目录及预览；修改Vue／CSS继续使用上文Vite入口。

软件面板、准备回执和调用记录标明开发路径、HEAD、dirty与内容指纹。适配器依赖和预览缓存随指纹失效。生成／校验失败会使开发源不可用，软件面板显示诊断，停止新预览／调用；修正后自动恢复，画布及自定义标题保留。开发模式沿用在途调用行为，不保存旧实现快照。

解除绑定并恢复已安装版本，无需重新安装：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 --workspace .artifacts/workspaces/node-ui-bundle --clear-bundle-source siril --start
```

#### 固定版本候选

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

浏览器验收统一使用Playwright Test。先通过固定准备入口启动自己的Feature预览，显式指定它的网页地址和workspace；fixture会先验证实际健康／配置路径与目标一致，拒绝dev／default。测试只用专属合成输入，不启动浏览器外的第二套调度或自动启动服务。

```powershell
$env:APF_WEB_URL = 'http://127.0.0.1:32588' # 使用自己的准备回执地址
$env:APF_TEST_WORKSPACE = "$PWD/.artifacts/workspaces/modernization-current"
pnpm test:browser --list
pnpm test:browser
```

默认入口为[playwright.config.mjs](../../tests/browser/playwright.config.mjs)，报告在`.artifacts/reports/browser/`，失败保留trace／截图。并行执行其他发现／验证命令时，使用`APF_BROWSER_REPORT`指定本工作树`.artifacts/reports/`内的独立子目录，避免报告覆盖。并行worker为1，有写入的测试不自动重试。已有Chromium可通过`PLAYWRIGHT_CHROMIUM_EXECUTABLE`指定。

原生队列测试需显式设置`APF_ALLOW_NATIVE_QUEUE=1`；配置真实重启测试需`APF_ALLOW_WORKBENCH_RESTART=1`，仅在队列为空、没有既有待采用配置时运行，完成后恢复本轮修改的配置。未启用的场景记为skip，不记为通过。不要在共享dev上运行。

现代化的固定52成员场景另用`pnpm test:browser:modernization`，依赖该隔离workspace已准备的G2 seed；原生Siril／安装／画布专项用`pnpm test:browser:native`及对应显式opt-in。它们仍是Playwright Test，不是旧脚本别名。具体来源与断言去向见[浏览器迁移清单](browser-test-migration.md)。

结果写[验证记录](test-matrix.md)，完整日志进 `.artifacts`；实现、构建、启动就绪、功能验证和用户验收分别报告，已通过检查不无故重复。

并行执行pytest时，每个进程必须显式使用不同的`--basetemp=.artifacts/pytest-<任务>`，不使用默认目录或其子目录；pytest启动会清理指定目录，不能与另一个仍在运行的检查共享。

## 发行与安装验证

```powershell
uv run --locked --no-sync python scripts/build_release.py
uv run --locked --no-sync python scripts/verify_distribution.py
```

仅开发版本，正式发布另行批准。发行物在 `.artifacts/dist`，Python 中间产物在 `.artifacts/build/python`；wheel 携带网页与固定引擎，用户不需要 Node。已有网页时可单独重打 Python 包；发行验证的独立目录、报告和离线重建参数见脚本 `--help`，不把非隔离构建或未验证平台写成通过。
