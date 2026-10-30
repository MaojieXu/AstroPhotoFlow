# 需求、实现与验证矩阵

<a id="library-simple-list-width"></a>

## 2026-10-29 精简列表和长名称：未执行验证

候选：`codex/library-ui-layout` 本地代码。用户报告窄侧栏中长名称逐字竖排，要求精简模式只显示预览／名称。已修改WorkspaceRecords语义列标记、Workspace简约列隐藏／宽度／省略样式及InlineField可选完整标题提示；本段只记录修改和待验证范围，不证明视觉修复已通过。

按用户约定，本轮未运行测试、类型／样式检查、构建或浏览器验收，34388仍使用本轮修改前的构建。后续待用户明确要求验证时检查：窄侧栏中含英文长文件名／中文名称不逐字竖排且预览／名称对齐，悬停读到完整名称；分类／曝光表头及单元格均隐藏；图像组导航、批量勾选、名称双击编辑、整行拖拽继续可用；切至细节模式保留完整资料列。此前45项或其他历史通过记录均不覆盖本次修改。

<a id="library-row-drag"></a>

## 2026-10-29 素材整行拖拽

候选：`codex/library-ui-layout`，Windows、Node26.8.2、独立34388／34390实例。以下验证均在本轮用户同步“默认不执行test和最终验收构建”约定之前完成；收到约定后停止追加测试及构建，仅保存既有结果。

- 原生4文件25项通过，8.85秒：LibraryCanvasSource、canvasDataBridge、dataReferenceDisplay、CanvasDataWidget。整行新增用例覆盖状态说明／参数值／行背景起拖、一次固定引用插入、aria-selected保留、普通行选择与名称点击放置区分、编辑输入拖动隔离；预览和固定引用既有用例继续通过。日志：`.artifacts/verification/library-row-drag-20261029/native-tests.log`。
- UI组及成员文件20项通过，8.97秒：每条记录只交接一个整行拖拽宿主，组及成员固定版本保持，既有导航和编辑回归通过。UI包vue-tsc及LibraryCanvasSource.vue定向ESLint通过。Vite构建通过，8.80秒，日志同目录build.log；未执行原生全库类型检查或全库回归。
- 真实页面在新页的独立Unsaved Workflow (4)验证：从“原件已就绪”等状态说明起拖，生成一个29成员数据节点且保留图片、名称、切换按钮及曝光等信息；原生撤销后画布为空。再从行中无文字／按钮的空白区域起拖，生成一个相同固定组节点。原页面保留，未执行科学处理、修改素材资料或批量拖入多条记录。截图：`.artifacts/verification/library-row-drag-20261029/row-drag.jpg`。
- 部署：stop `ac9b5633-1c5b-4fe0-af1d-2469bb50e4c0`、init `--reuse-runtime --no-activate`、start `c32ff26f-f0c5-42bc-be45-782f6703e8d2`均完成，blockers为空。仅更新当前worktree，未提交／推送／合并，用户验收待反馈。

<a id="library-preview-preservation"></a>

## 2026-10-29 素材预览保留修复

候选：`codex/library-ui-layout`，Windows、Node26.8.2、独立34388／34390实例。此前加入交互验证没有覆盖节点内图片，用户报告缺失后补充本次验证，不将此前节点创建通过解释为预览已通过。

- 最终定向5文件27项通过，9.68秒：dataReferenceDisplay、CanvasDataWidget、WidgetDOM、LibraryCanvasSource、canvasDataBridge。新增实际隐藏状态、DOM生命周期注册／释放、原生内容高度与canvas显示／不显示两种显式vueNode组件挂载；保留固定引用唯一序列化、成员切换及0值、迟到响应隔离和拖放回归。日志：`.artifacts/verification/library-preview-preservation-20261029/tests.log`。
- Vite生产构建通过，10.66秒，日志同目录build.log；保留既有资源及动态导入警告。dataReferenceDisplay.ts和WidgetDOM.vue定向ESLint通过。CanvasDataWidget.vue检查报告4条既有Tailwind规范错误，均在本次未修改行：两条break-words命名和两条类排序；本轮未顺带整理，因此不声称三个生产文件lint全部通过。未运行全库回归或原生全库类型检查。
- 真实页面：最终新页确认加载`index-B6TIzAyj.js`，旧版canvas模式未切换。单独空白图拖入Astro_Dataset，显示29成员数据节点、图片和当前成员名称；连按下一张到3／29，名称为Andrew M Weeks - L、曝光从180s变120s。详情显示12238×8082、Bin1／1、fits和BITPIX等既有资料；关闭详情后名称实测19.2px高，修复前为0px。无reference输入框、无页面错误；未运行科学处理或改写素材资料。Nodes 2.0由WidgetDOM的两种surface用例覆盖，本轮没有实际切换全局设置。
- 部署：最终stop `93d5af4c-9eef-4b2d-ba1e-cbf53ee90f57`，init `--reuse-runtime --no-activate`，start `914f6733-29ba-4b61-b5fc-e0bbaaf4d067`完成且blockers为空。旧页面保留，未保存验证页的刷新未真正离页，改用新页验证最新资源。截图：`.artifacts/verification/library-preview-preservation-20261029/preview-restored.jpg`。仅当前worktree实例；未提交／推送／合并，用户验收待反馈。

<a id="library-native-node-placement"></a>

## 2026-10-29 素材原生节点放置

候选：`codex/library-ui-layout`，Windows、Node26.8.2，独立34388／34390实例。

- 原生定向6文件56项通过（12.07秒）：LibraryCanvasSource、canvasDataBridge、useNodeDragToCanvas、useNodePreviewAndDrag、useCanvasDrop和LibrarySidebarTab。覆盖点击落点、原生拖放、Esc／画布外／双击取消、不就绪、拖起后固定版本不随列表刷新变化，以及原生节点既有交互。首次新增拖放用例因happy-dom事件未携带坐标失败，测试显式构造MouseEvent坐标后通过，生产代码未为测试增加分支。日志：`.artifacts/verification/library-native-node-placement-20261029/native-tests.log`。
- UI固定组及成员用例20项通过（27.65秒），名称与缩略图交接固定组版本和固定成员版本，原预览／编辑回归通过。UI包vue-tsc通过。定向生产文件ESLint零错误；测试文件由既有ESLint配置忽略。Vite生产构建通过（32.44秒），保留既有资源／动态导入警告；未执行原生全库类型检查或全量回归。
- 真实浏览器：保留原页面，在新页新建Unsaved Workflow (2)；点击Astro_Dataset名称后落点生成29成员数据节点，缩略图拖入另生成一节点，两次原生撤销逐个移除。打开组后拖动Andrew M Weeks - B名称生成单件asset_version节点；双击名称进入编辑，Esc取消，无资料保存或运行提交。页面错误日志为空。最终验证图留一个单件示例节点。
- 部署：stop `a50dfe9f-2dac-47ae-99a6-64e435c67425`、init复用私有runtime且不激活默认workspace、start `fbb8ed01-fcd1-4f7f-b1af-9a39412bc155`均完成，blockers为空。只更新当前worktree实例。截图：`.artifacts/verification/library-native-node-placement-20261029/placement.jpg`。上述为Agent验证，用户验收尚待反馈；未提交／推送／合并。

<a id="library-modern-folder-picker"></a>

## 2026-10-29 素材库新版文件夹选择窗口

候选：`codex/library-ui-layout`，基线 `366a311`；环境：Windows、独立worktree及34388／34390实例。用户确认“好的，已经完成了”，窗口呈现按本次用户确认通过。

- 自动检查：`tests/modules/data/test_local_selection.py` 全部用例，加 `test_import_pipeline.py` 的原生选择取消／空根目录、繁忙、断连取消、文件夹固定当前层四项，共13通过（3.49秒）。覆盖取消不返回素材、单窗口互斥、子进程回收及当前层枚举。
- 原生检查：实际 Windows PowerShell 编译生产选择器C#并创建／释放COM对象成功；通过独立网页接口得到取消空清单，未建立导入任务。Agent未完成中文测试目录的成功选择回传，不将此项记为已实测通过。
- 部署：平台restart完成，blockers为空；仅本worktree运行实例，沿用已有前端构建。未运行全量回归或重新构建前端。
- 证据：`.artifacts/verification/folder-picker-20261029/pytest.log`、`compile-picker.log`、`restart.log`；用户确认保留于本chat。

## 2026-10-29 设置精简验证

候选：`codex/comfyui-ui-cleanup`未提交工作区，基点366a311；Windows、Node26.8.2、pnpm11.13.1、独立35388／35390。

| 验证范围 | 实际结果 | 证据 |
|---|---|---|
| 导航、设置搜索、默认值、设置窗口、工作台交互、快捷键及菜单 | 最终7文件136项通过；包括旧Nodes关闭值转启用、默认自动保存及明确关闭保留 | tests-final.log |
| 工作台配置保存、重启及错误处理 | UI包12项通过 | package-workbench.log |
| 定向静态检查、类型及生产构建 | 通过；构建保留资源引用及分包告警 | lint-final.log、build-final.log |
| 静态资源同步与服务启动 | 目标实例停止、复用匹配runtime同步及启动完成 | deploy.log、deployment.json |
| 实际视觉 | 未完成：浏览器接口不可用；自动审批因未保存工作流拒绝刷新，原页保留，独立查看页打开请求已排队 | 本轮工具回执；无新版视觉截图 |

证据目录：`.artifacts/verification/settings-cleanup-20261029/`。初轮导航顺序断言、版本全局类型和既有工作台测试风格问题均已修正，最终结果以上述日志为准。

## 2026-10-29 主菜单精简验证

候选：`codex/comfyui-ui-cleanup`，基点 `366a311`，未提交改动；Windows、Node26.8.2、pnpm11.13.1及独立35388／35390实例。范围对应现行需求中的“2026-10-29 主菜单精简决策”。

| 检查 | 实际结果 | 证据 |
|---|---|---|
| 主菜单隐藏指定入口，设置仍可打开；保留桌面版开关行为 | ComfyMenuButton与settingStore两文件61项通过；按规范将新增参数化用例改为it.for后，设置Store55项复跑通过 | targeted-tests.log、settings-final.log |
| 未保存开关值的本地安装默认Nodes 2.0，含无安装版本、1.30.0及1.57.1 | 三种安装版本输入均通过真实Store注册和默认值读取 | settingStore.test.ts、上述测试日志 |
| 四个修改文件静态检查；前端类型及生产构建 | Oxlint通过；ESLint零错误，测试文件由Oxlint覆盖；生产构建成功，仍有资源引用及分包告警 | oxlint.log、lint.log、frontend-build.log |
| 定向同步与实际页面 | 停止目标实例、复用匹配runtime同步、启动均完成；浏览器主菜单仅新建／文件／编辑／视图／主题／设置，设置可打开且Nodes 2.0启用，原graph标识保留 | deploy.log、deployment.json、menu.png、menu-detail.png |

证据目录：`.artifacts/verification/menu-cleanup-20261029/`。本轮只验证上述UI与默认值范围，不代表其他工作流能力或用户里程碑验收。

## 2026-10-29 Siril Bundle dev 集成验证

用户本轮明确授权检查 chat `01a183fd-e65c-7b32-b71e-8220c5245b55` 的实现、解决冲突、执行测试及构建，并将主项目 `codex/siril-bundle` 集成推送到远端 `dev`，独立 AstroPhotoFlow-Siril 保持并推送 `dev`。主项目基点为 `366a3112`；Bundle 为 `0.1.2-dev.1` / `12fd2d1d55daeadf7acb3972385d5c2bfcb52d4d`，仍是开发版本，不构成正式发布。

发现并修复两处实现不一致：移除 `bundles.py` 中重复的 `remove_checkout` 定义与重复导入，保留受管理目录及删除目标检查；两个仍公开的 Siril 预览适配路由恢复进入 OpenAPI，并从实际应用重新生成快照，保持代理白名单与当前服务契约一致。初始远端核对没有 Git 分叉或未合并文件，不将旧实验版本文字作为当前版本。

验证环境为 Windows / Python 3.12.4 / Node 26.8.2 / pnpm 11.13.1。后端初轮 570 passed、1 failed、4 skipped；唯一失败为上述代理/OpenAPI 一致性，修复后软件、代理、预览和失败用例合计 46 passed，清理函数修复后安装/卸载用例另有 6 passed。两个显式真实原生/Siril用例另外执行并通过，检查双成员输出及原件哈希；两个未运行的跳过项为本轮无改动的 M1 双 workspace 生命周期及失败排空真实验收。UI包 34文件267用例、宿主桥接12文件45用例、独立Bundle适配器5用例均通过。根 `pnpm build`（固定引擎、UI及原生类型、完整网页）通过；边界检查0错误、13条既有循环引用警告，后端保留一条既有互相外键排序警告。发布目录重新导出与固定Bundle checkout一致。

最终修复源码另外通过 wheel/sdist 构建、独立venv安装与隔离构建的无Node源码包重建，原始及重建wheel均通过安装smoke。结果为 `packaging.json`，日志为 `final-package-build.log` 与 `packaging.log`；临时安装/解包目录在本仓库 `.artifacts` 内，`repository_external_install=false`、`repository_external_sdist_rebuild=false`，本轮不声明严格仓库外验收。当前Bundle仍锁定 `v0.1.2-dev.1`，未新增或移动发布标签。

本轮证据位于 `.artifacts/verification/siril-dev-integration-20261029/`：`backend.log/xml` 保留初轮失败；`final-regression.log/xml` 保存修复回归；`install-regression.log`、`real-native.log/xml`、`bundle.log/xml`、`ui.log`、`native-ui.log`、`build.log`、`boundaries.log`、`bundle-catalog.json`。本轮未操作正常dev或demo-preview服务；人工视觉验收、无系统Git自举及完整升级影响验收仍不由自动测试代签。Git集成与推送结果以实际提交及远端回执为准。

## 开发/正式发布隔离（用户2026-10-29补充）

当前发布仅为开发构建。Siril Bundle默认分支为dev，当前标签 v0.1.2-dev.1，commit 12fd2d1d55daeadf7acb3972385d5c2bfcb52d4d，release_channel=dev。开发版本必须使用X.Y.Z-dev.N，正式版本使用X.Y.Z并显式标为stable；schema和发布目录导出拒绝混用标签/通道。正式发布另行由用户明确批准，不能移动开发标签来冒充正式版本。v0.1.0/v0.1.1仅为历史实验标签，未作为正式Release发布。主项目候选位于codex/siril-bundle，本轮获授权测试后集成并推送dev；未发布正式包。

历史实验版本就绪核对（已由上述v0.1.2-dev.1替代）：v0.1.1 / 7f2639441b3d00b3b3ec671b77fa5a027b4c1e8e，包ready，显式执行终点为true；最终index SHA256 535067a29c75b126a6bbcbc04261b07f0289b25975646537d91225fa63b5af42。保留原app，仅清理本轮生成的v0.1.0实验备份。

历史实验Bundle版本（非当前发布目录）：v0.1.1 / 7f2639441b3d00b3b3ec671b77fa5a027b4c1e8e（Siril1.4.4）。v0.1.0保留为早期验证记录。v0.1.1以output_nodes显式声明原生终点，默认非终点，并补齐examples/agent.md；独立包5项测试通过。当时主项目目录锁定v0.1.1，demo-preview已更新；当前锁定版本以上述开发通道记录为准。无系统Git自举、浏览器确认和用户画布视觉仍待人工验证。

交付更新：demo-preview已通过维护机制停止/启动（eb878959停止、3a48a82c启动），迁移到独立Bundle并保留原app。HTTP确认32688网页散列与最终构建一致、包ready、原生节点已注册，报告.artifacts/bundle-demo-report.json。bundle-smoke测试实例已停止并验证真实Git卸载；正常dev实例未启停。前端依赖检查0错误/13条既有警告。无系统Git时的MinGit自举分支未做真实下载验收；私有仓库仍需用户具有访问权限及系统凭据。

## 2026-10-29 Bundle 验证候选

候选分支 codex/siril-bundle，独立Bundle v0.1.0/d6be7dd3。已执行：Bundle适配器4项；软件、节点、画布、预览、边界等55项，另补跑说明文字变更门1项通过；宿主4文件14项；软件包页面12项。UI包类型检查、原生类型和生产构建通过。Windows/Python3.12；前端最终构建使用Node26.8.2/pnpm11.13.1。

真实隔离证据：.artifacts/bundle-real-install.log（私有Git固定提交与定义登记）、bundle-real-start.log、bundle-runtime-report.json（原生注册、实时PNG、队列真实Siril退出成功、96×64输出、原件哈希不变）、bundle-client-report.json（CLI/MCP目录一致，新增四工具）。真实Git卸载报告bundle-uninstall-report.json，4个受保护文件哈希保持。前端构建日志bundle-build.log、bundle-ui-typecheck.log；测试日志bundle-regression.log、bundle-metadata-test.log、bundle-frontend-tests.log、bundle-software-panel-tests.log。无浏览器操作，不将进程/协议检查写成用户视觉验收。

待人工验收：软件页面点击确认安装/卸载与自动重连；授权目标画布的连续加节点、调参、连线；旧工作流视觉与预览。没有进行多版本升级/端口变化全面验收，不宣称完整M3/M4/M5交付。
## 2026-10-29 M2 最终验证通过候选

本条覆盖此前“仅编写测试”“受阻等待确认”的状态：用户已明确授权运行工作台设置及素材库全部现有实现的测试，通过后推送并合入dev。设备管理与素材库复用侧栏内容宽度和左边界，设备组合／我的设备居左；切换类别先清空旧记录，避免设备记录被组合视图误读。根目录单文件导入补存受理时大小／mtime，保证受理后来源变化会失败且不登记素材。

验证环境：Windows、Python3.12、Node26.8.2、锁定CPU原生runtime、Siril1.4.4。后端默认全量564通过、4项显式环境测试跳过；随后单独补跑原生节点schema／真实Siril两项、真实导入失败排空一项、真实双workspace启停／端口冲突／重启采用／繁忙拒绝一项，均通过；合计568个后端用例通过，无未执行的默认跳过项。前端UI包34文件265用例、宿主桥接等16文件94用例、原生设置22文件237用例均通过，合计596用例。原生过程使用专用runtime副本与m2-final-a/b，测试结束停止自有进程；dev及demo-preview服务未被启停。

根pnpm build（固定引擎归档、UI类型、原生类型及网页）通过。依赖边界0错误、13条既有循环警告；后端迁移比较保留一条既有互相外键排序警告。浏览器在1280×900、900×900实测素材库／设备主区左边界及宽度相同，两个页签居左且页面无脚本错误，截图与结果已保存。原生Siril测试曾因测试输出绝对路径超过Windows/CFITSIO限制失败，改用项目标准短.artifacts临时路径后通过；这不证明任意长度路径受支持。

全部证据在 `.artifacts/verification/m2-final-20261029/`：pytest-final.log、native-siril-short-path.log、process-drain.log、process-lifecycle.log、ui-tests-round2.log、native-tests-round2.log、settings-native-tests.log、final-build.log、dependency-boundaries.log及layout/result.json。本条证明当前候选的测试结果，不代替用户对M3其他能力的批准。Git提交与远端集成以实际分支提交为准。


## 2026-10-29 M2 最终优化与验证进行中

用户本轮授权运行工作台设置、素材库现有实现的测试，修复后推送当前候选并合入 dev；覆盖此前仅编写测试约定。设备管理移除独立640px居中容器，复用素材库宽度，设备组合／我的设备页签左对齐。页面切换先清空旧类别记录，避免设备数据按组合结构渲染。pytest启用importlib收集，解决不同模块同名测试文件冲突。

实测：UI包34文件265用例通过；原生桥接及相关原生组件16文件94用例通过。日志位于 `.artifacts/verification/m2-final-20261029/`。Python初轮停在沙箱限制的asyncio socketpair，60秒线程堆栈已保存；非业务测试断言失败。自动审批两次未识别本轮目标中的新测试授权，拒绝受限外运行；已向用户请求简短确认。后端测试、构建最终结果、远端推送及dev合并尚未完成，不记为验收通过。


2026-10-29 Siril 参数范围修复候选：官方1.4.4 autostretch 的 shadowsclip 未规定上下限、targetbg为[0,1]。发现原生 useFloatWidget 在缺省上下限时使用0..2048；节点schema为shadowsclip显式提供双精度有限浮点范围，避免额外业务限制。targetbg仍保留0..1。补写真实schema范围断言但未运行；Python语法编译通过；仅后端schema变更，沿用现有前端构建，隔离更新证据见 .artifacts/implementation/siril-range-fix-20261029。用户调参验收待执行。

2026-10-29 Siril RGB 预览修复候选：direct_fits_image 对已知 Siril 输出的 (3,H,W) 平面 RGB 在内存中补充 CTYPE3=RGB，再复用条带读取；不修改磁盘 FITS，不改变普通素材的 RGB 判定。新增无 CTYPE3 的三通道颜色与原件哈希用例，仅编写未运行；语法编译通过。此次仅后端更新，沿用已有前端资源，隔离重启证据位于 .artifacts/implementation/siril-rgb-fix-20261029；用户视觉验收待执行。

2026-10-29 Auto Stretch 静态格式扩展候选：输入接受 fits、xisf、image、raw，完整原件交由 Siril 自身 load 解码；具体编码支持由安装的 Siril 报告。非 FITS 快速预览首次 load 原件后 resample -maxdim=1024，先保存未拉伸 linear.fit 再执行 autostretch；成功且原件大小/mtime 未变化后发布样本缓存，后续调参复用。FITS 保持既有条带采样。正式结果继续 FITS，显示不二次拉伸。视频、数值数组及指定 HDU/切片仍未接入。补写格式转发、原生解码顺序和缓存复用用例，未运行测试或实际软件处理。Python语法编译通过；仅后端及包描述变更，沿用现有前端构建；隔离重启证据见 .artifacts/implementation/siril-formats-20261029。用户预览待验收。

## 2026-10-29 Siril 安装目录发布及错误状态修复

实际证据：用户确认安装后，下载／解压／准确版本检查完成，目录移动失败（WinError5），随后嵌套ErrorDetail被dict替代导致序列化失败；安装任务已failed，而磁盘状态仍running。只读API动作和原状态／日志保存于 `.artifacts/implementation/siril-install-fix-20261029/`。修复为正式目录独占创建／归档安全解压／最终位置版本检查，失败原因为类型化ErrorDetail并保留部分安装事实。已知失败且目录不存在的隔离状态按真实动作恢复失败，不触发新安装。

新增 tests/modules/software/test_installation.py：最终位置验证、无临时程序目录移动、归档逃逸拒绝、WinError5原始原因持久化、无文件／部分文件失败终态；SoftwarePanel.test.ts 增加未确定版本但有已知失败程序目录的卸载入口。全部仅编写，未运行。语法、类型／构建及仅demo-preview维护更新以同目录日志为准；没有真实重装、软件运行或浏览器预览，不声明安装已验收。


## 2026-10-29 Auto Stretch 实时预览及执行会话修复候选

候选：codex/m2-ui-acceptance 未提交工作区。用户报告的 RuntimeError: Timeout context manager should be used inside a task 来自执行循环使用网页服务ClientSession；本轮改为执行内创建会话。证据与编译日志：`.artifacts/implementation/siril-live-preview-20261029/`。

| 用例 | 文件 | 状态 |
|---|---|---|
| 两个独立原生执行循环各自持有／关闭HTTP会话；元数据保持有效 | tests/integration/test_siril_native.py | 仅编写，未运行 |
| 直接显示浮点／16位结果亮度、RGB／奇数边界、正式结果不再次拉伸 | tests/modules/data/test_siril_preview.py | 仅编写，未运行 |
| 线性样本复用、原件不变、Preview生成保护及所属清理 | tests/modules/data/test_canvas_data.py 增量 | 仅编写，未运行 |
| 新代次取消旧任务、样本释放、认证、拒绝任意路径及PNG响应 | tests/modules/workflows/test_siril_preview.py | 仅编写，未运行 |
| 参数防抖、0保留、迟到图隔离、关闭释放 | SirilPreviewWidget.test.ts | 仅编写，未运行 |
| 仅一份非序列化展示控件，三个正式参数保存不变 | sirilPreviewDisplay.test.ts | 仅编写，未运行 |

本轮只运行语法／类型编译、OpenAPI导出及前端构建，随后仅更新并按繁忙拒绝机制重启隔离demo-preview。没有执行Siril、下载安装、自动测试、性能实验或浏览器预览；不宣称真实处理、视觉及实时延迟已验收。


## 2026-10-29 Siril 节点元数据导致空白页的修复

用户报告页面只有网格背景。只读诊断捕获新节点 object_info 的 python_module 为 null（node-info-before.json）；源码定位前端节点构造会对该字段执行 split。修复生产方的 V3 模块身份，保留前端正常字符串契约；不增加空值吞错或跳过节点分支。tests/integration/test_siril_native.py 扩展实际 GET_NODE_INFO_V1 输出断言，未运行。Python 语法、原生类型／前端构建、仅 demo-preview 更新／维护重启及修复后只读元数据记录归 `.artifacts/implementation/m3-blank-page-20261029/`；这些是诊断和编译／更新证据，不等于自动测试或人工视觉验收通过。


## 2026-10-29 M3 安装／卸载、调用与首节点候选

候选：`codex/m2-ui-acceptance` 当前未提交工作区；证据目录 `.artifacts/implementation/m3-software-20261029/`。本轮不运行任何测试，不启动 Siril 处理、不下载安装、不操作浏览器，用户验收待完成。

| 范围 | 已补齐测试文件 | 执行状态 |
|---|---|---|
| 单／多成员一次脚本、顺序、0、原件不变、非零退出及部分产物、参数／HDU／路径拒绝 | tests/modules/software/test_invocation.py | 未执行 |
| 定向取消、当前调用与维护互斥、程序卸载保留数据 | 同上；test_service.py 确认／token／无副作用增量 | 未执行 |
| 固定组解析、当前资料和增益0、顺序拒绝 | tests/modules/data/test_canvas_data.py 增量 | 未执行 |
| 同连接页面确认、真实 socket 身份覆盖、不使用客户端身份 | tests/interfaces/comfyui/test_software_page.py | 未执行 |
| 仅内部原生调用、认证、拒绝任意路径、同 call_id 不重复启动 | tests/modules/workflows/test_software_calls.py | 未执行 |
| 真实 V3 schema、真实 Siril 双成员输出及原件哈希 | tests/integration/test_siril_native.py，显式环境变量启用 | 未执行 |
| 页面只有变更按钮及状态点、确认取消、请求失败、命令目录不常驻且 API保留 | UI SoftwarePanel／CommandDirectory／api 测试 | 未执行 |

已通过编译／构建（不等于测试）：UI 包 vue-tsc；原生 typecheck 与 Vite 生产构建。Python 语法、OpenAPI 导出、隔离更新与维护重启以该目录日志及 deployment.json 为准；不声明真实软件、视觉质量、停止或 M3 Milestone 已验收。


2026-10-29 缩小错位修复候选：概览底图不再始终object-contain铺满容器；复用OpenSeadragon当前图像边界和当前视口坐标，在open、缩放动画、平移和resize时同步CSS像素位置／尺寸，取消图片默认max-width限制。首次加载尚无视口时仍适应窗口；切成员清空旧边界并拒绝迟到回调。新增坐标与组件回归用例，仅编写未运行；原生类型检查和生产构建通过；已更新隔离demo-preview网页资源，入口SHA256一致，无后端修改或重启；日志与部署记录见.artifacts/implementation/media-alignment-20261029/，视觉效果仍待用户验收。

2026-10-29 预览加载修复（media-loading）：新增FITS连续读取／跨步像素一致性／约8MiB条带／取消检查，覆盖灰度、平面和交错RGB、压缩和缩放FITS，沿用Bayer与原尺寸瓦片用例；新增共享prepare与tile取消保护、phase、缩略图先显示、1秒轮询及请求失败停止轮询用例。所有新增／受影响测试均未执行；未开展压测、性能对比或自主预览。Python语法编译7文件、UI类型检查、原生类型编译与生产构建均成功；第一次原生类型编译发现测试误引未安装工具包，已改用现有Vitest、第二次构建通过。demo-preview维护重启completed、静态入口SHA256一致，日志和deployment.json位于.artifacts/implementation/media-loading-20261029/。实际像素、取消、性能和视觉行为仍待执行／用户验收。

<a id="media-viewer"></a>

## 2026-10-29 统一媒体查看器候选

实现与验证分开：以下用例只编写，**未运行**；不把语法编译、类型检查、OpenAPI生成或前端构建当成功能／性能／视觉验收。证据目录`.artifacts/implementation/media-viewer-20261029/`，最终编译与隔离更新以其中deployment.json实际回执为准。没有启动浏览器或真实千张样本实验，没有提交、推送或合并。

编译／交付实际证据：Python16文件语法编译、OpenAPI生成、UI包类型检查、原生类型检查及生产构建退出码均为0；最终Vite49.11s。隔离维护重启fd6f461e-55f4-4ef7-be55-0b0cace38ee0已completed、blockers为空；静态资源源／目标hash见deployment.json。上述结果不替代下表未执行用例。

| 场景 | 已编写用例／预期 | 执行状态 |
|---|---|---|
| 原尺寸区域与格式 | test_media_sources：FITS单色／平面和交错RGB／压缩／缩放、CFA邻域、XISF／PNG解码复用、RAW完整解码、NumPy头／数组／切片 | 未运行 |
| 瓦片和预算 | test_media_cache：奇数尺寸边缘瓦片重组不丢像素、缓存复用、按字节LRU、活动读取保护、原件保持 | 未运行 |
| HTTP与生命周期 | test_media_view：认证／归属、共享和项目固定引用、PNG瓦片、源文件变化、失效排队请求、生成所有权／清理阻塞、Range206／416 | 未运行 |
| 视频与时间戳 | test_media_video：可变帧率整数PTS、暂停源帧、无法精确匹配拒绝、SER直接帧地址、有效时间戳及无时间戳10fps代理映射、方向／无需ffprobe | 未运行；FFmpeg通过受控替身，编码器真实能力待用户验证 |
| 网关流 | test_media_stream：范围头／服务认证、206响应头、首块在完整响应前可读、Cookie不跨网关 | 未运行 |
| 查看器与千张组 | MediaViewer.test：1000成员轻量模拟只请求当前／邻帧概览、跳转、迟到响应丢弃、关闭释放、错误不伪造高清、数组／轴、暂停实际呈现帧 | 未运行 |
| 节点与DPI | CanvasDataWidget.test更新当前高清概览和引用不变；mediaViewport.test覆盖高DPI100%及原尺寸瓦片坐标 | 未运行 |

实际手动验收待办：在用户自己的图片／组上检查清晰度、星点／瓦片接缝、缩放和平移流畅度、同尺寸组内位置保持；检查RAW／HEIF和有效图像布局、NPZ多维选择、视频／SER编码及呈现帧对应、首次准备与缓存淘汰、断连／关闭释放和繁忙拒绝。X-Trans／Quad Bayer当前明确灰度马赛克查看，不宣称完整彩色去马赛克。现有解码器瞬时内存及浏览器纹理开销不属于所列缓存字节上限，未进行真实资源测试。

<a id="object-subframe-stretch"></a>

2026-10-28 Object／分类MTF与分层随机采样候选：

| 场景与预期 | 测试文件 | 状态 |
|---|---|---|
| 分层坐标覆盖原图范围、固定种子、预算／长窄图、通道与0／非有限值；周期图案避免固定步长相位锁定 | test_auto_stretch.py、test_fits_preview.py | 仅编写／修改，未运行 |
| FITS Mono／缩放／uint16／平面与交错RGB／压缩图统计取自原图，按行读取；Bayer四种排列及偏移使用完整色彩单元 | test_fits_preview.py | 仅编写，未运行 |
| 同Object子帧只测首张，Master同Object仍各自测量，Object缺失／不同目录／布局不兼容独立，FITS与XISF原件不变 | test_import_pipeline.py | 仅编写，未运行 |
| 首张失败后选下一张、重试复用并保留身份；参考文件缺失仍回填；报告写入间隙恢复已发布首帧配方 | test_import_pipeline.py | 仅编写，未运行 |
| 大图采用已有MTF且不重复统计、100／1080及请求尺寸保持；非组来源自动测量使用原图随机样本 | test_display_previews.py | 仅编写，未运行 |
| 未知分类／非组来源、独立帧恢复、旧缓存配方、原件及元数据保护 | test_import_pipeline.py、test_ingestion.py、既有预览回归 | 仅修改，未运行 |

**本轮不运行测试、真实性能实验或浏览器／图片预览。** 编译和仅隔离demo-preview的更新证据见 .artifacts/implementation/object-subframe-stretch-20261028/。固定随机抽样仍是统计估计，尚无实测质量、精度或提速结论；已有缓存不批量重算，需用户以新导入或缺失缓存重建候选验收。前一节“所有帧独立／256×256固定网格”保留为历史候选证据，不再是当前需求。

<a id="independent-preview-stretch"></a>

2026-10-28 逐图快速拉伸候选：

| 场景与预期 | 测试文件 | 执行状态 |
|---|---|---|
| Mono／RGB统计网格最长边256、通道保持对应、0及非有限值处理、确定性与原像素不变 | test_auto_stretch.py、test_fits_preview.py | 仅编写，未运行 |
| 同参数不同亮度独立配方，首张阻塞不阻止其他张预览，恢复／失败重试保持身份及其他图片配方 | test_import_pipeline.py、test_ingestion.py | 仅编写，未运行 |
| FITS／XISF／16位TIFF导入及回填独立，XISF／高位深映射网格不超过两倍请求边长，托管原件和历史任务不改 | test_import_pipeline.py、test_ingestion.py | 仅编写，未运行 |
| 本图配方重建大图，其他图片不可用不影响；历史共享配方仍可复用，元数据重试和预览生命周期保持 | test_display_previews.py | 仅修改，未运行 |
| 公开科学输出预览保留大于100px的请求尺寸、科学输出不变 | test_science_inputs.py | 仅编写，未运行 |

编译、构建和仅隔离demo-preview资源／维护重启结果以 .artifacts/implementation/independent-preview-stretch-20261028/ 实际日志与回执为准；**未运行测试、样本性能测量或浏览器／图像预览**。待用户验收新导入的不同亮度成员均可独立显示、原件就绪与预览状态分离、组顺序／参数对应、首次大图与缓存重开。已有缓存不批量重算，采样不承诺保留所有细小结构或极值；未证明最快策略或具体提速幅度。

<a id="native-picker-focus"></a>

2026-10-28 导入选择器焦点／取消候选：补齐文件与文件夹owner及一次性置前脚本、正常返回、取消前未启动、在途关闭／回收、无响应子进程退出、并发拒绝及失败后释放锁；HTTP重复选择409且不建任务、断连终止本次选择、代理上游连接释放、前端显式取消／关闭／卸载中止、快速重试和旧结果隔离，以及HTTP客户端传递AbortSignal。**只编写测试，未运行测试或自行打开选择器／浏览器。** 编译和隔离更新的实际证据见 .artifacts/implementation/native-picker-focus-20261028/；Python／PowerShell语法与C#类型编译不等于Windows交互验收。待用户检查文件多选及文件夹窗口均出现在网页宿主前方、取消后焦点返回、切到其他应用不被持续抢焦点、取消／重新打开无残留窗口及原有资料确认流程。

<a id="hide-import-roots"></a>

2026-10-28 工作台设置隐藏导入目录候选：core/workbench.test.ts及WorkbenchSettingsPanel.test.ts覆盖空／非空配置均无目录标题、ID／路径输入、添加按钮和路径提示，重新读取后保存其他设置保留最新import_roots，原生宿主整组保存保留已有值。**仅编写／修改测试文件，未运行测试或自行预览。** 类型编译、生产构建及隔离静态资源更新以 `.artifacts/implementation/hide-import-roots-20261028/` 实际日志／回执为准；后台和配置接口未变，无需服务重启。

<a id="direct-local-selection"></a>

2026-10-28 本机直接选择候选：新增／更新无配置根目录时绝对路径托管、原件与副本独立及哈希一致、当前层范围冻结、后到文件不加入、系统选择取消不建任务、空目录反馈、不同磁盘路径、系统窗口失败、关闭后迟到结果不提交、UI不查询授权根且不上传浏览器File、既有root_id相对路径及配置行为回归用例。**仅编写，不运行测试，不打开系统选择窗口或自行预览，不做性能实验。** 编译及仅隔离demo-preview的资源更新／维护重启以 `.artifacts/implementation/direct-local-selection-20261028/` 日志和回执为准，实际文件选择交互及用户验收仍待完成。

<a id="nodes2-data-display"></a>

2026-10-28 Nodes 2.0 展示候选：测试文件新增／同步固定引用只读inspect、当前参数及0、原图与缩略图尺寸区分、RGB轴顺序、固定组子集及越界／成员不符、原件缺失资料保留、单图／组切换、详情、旧响应隔离、解码失败及显式重试、未记录值、隐藏JSON与展示不序列化、原生生命周期注册、复制恢复、ComponentWidget在WidgetDOM挂载、ImagePreview仅展示模式及默认行为回归、行右侧加入图标。**全部只编写，未运行测试、性能实验或浏览器预览。** 类型编译、生产构建、Python语法编译、OpenAPI导出及隔离资源／维护重启的实际日志与回执见 `.artifacts/implementation/nodes2-data-display-20261028/`；这些证据不代替Nodes 2.0实际功能、视觉及用户验收。

<a id="library-canvas"></a>

2026-10-28 素材入画布候选（未执行验收）：

| 场景与预期 | 测试文件／位置 | 执行状态 |
|---|---|---|
| 单件固定版本、完整有序组、子集索引、旧版不随新版变化；空组／未就绪／归属不符／回收站拒绝；预览或解析异常不替代科学原件 | tests/modules/data/test_canvas_data.py | 仅编写，未运行 |
| 原生按钮／拖放位置、异步切图拒绝、只读拒绝、原生节点服务及撤销事务 | canvasDataBridge.test.ts、useCanvasDrop.test.ts、Workspace.dataset-groups.test.ts | 仅编写，未运行 |
| 显式交回、手动变化／切图／重连撤销、视口排除、迟到内容拒绝、真实应用回执 | useCanvasDataSession.test.ts | 仅编写，未运行 |
| 同socket页面身份、错误目标回执拒绝、断线未知、同请求不重复发送 | tests/interfaces/comfyui/test_canvas_native.py | 仅编写，未运行 |
| HTTP保留目标及未知结果、认证和维护拒绝、CLI请求、MCP工具及准备引用、网关固定路由 | tests/modules/workflows/test_canvas.py、tests/integration/test_client_operations.py、test_cli_mcp_protocol.py、tests/interfaces/comfyui/test_proxy.py | 仅编写／同步，未运行 |
| 类型／语法编译、生产构建、OpenAPI导出、隔离资源／维护重启 | .artifacts/implementation/library-canvas-20261028/ | 以实际日志及回执为准，不能代替功能／视觉／用户验收 |

未运行任何测试、科学处理、性能实验或浏览器预览；未修改正常dev数据，不提交、推送或合并。

<a id="local-managed-import"></a>

2026-10-28 本机托管导入候选：新增／同步授权目录选择、文件夹不递归、无授权目录引导、托管固定清单与可选参数、原件字节及阶段进度、原件先就绪／预览后补、一次性通知及workspace隔离、失败原因和阶段重试、受理后来源变化／新增文件、托管哈希／非硬链接、登记复制衔接、主动与可见预览优先、复制／预览重试身份和配方等用例。**只编写测试，未运行测试、性能实验、并发比较、真实样本压测或浏览器预览。** Python语法／前端类型编译、生产构建、OpenAPI生成及隔离demo-preview资源／重启以 `.artifacts/implementation/local-managed-import-20261028/` 的实际日志和回执为准；候选不等于行为或用户验收通过。保留原件和正常dev，未提交、推送或合并。

<a id="import-notice-dismiss"></a>

2026-10-28 导入通知关闭候选：补齐按任务ID关闭、关闭不展开详情／不发送写请求、轮询及组件重建后保持关闭、同名新任务仍显示、任务更新时间变化不恢复旧通知，以及关闭后素材行解析异常保留的用例。**未运行测试或自行预览**；本轮仅类型编译、生产构建并更新隔离demo-preview，日志和回执见 `.artifacts/implementation/import-notice-dismiss-20261028/`。本地关闭偏好不改变后端事实，未提交、推送或合并，用户验收待完成。

<a id="library-compact"></a>

2026-10-28 素材库最小精简候选：组件用例覆盖精简工具栏、菜单单选、批量进入／计数／完成、删除取消、单页／多页／全部、组内分页与返回、表头排序和保留搜索筛选；导入用例覆盖登记及结束刷新、表格外进度、暂停恢复、读取失败、历史成功静默、完成事件及通知去重、注册处理异常无独立汇总、未登记失败原因及详情跨页。宿主用例覆盖原生Toast有限时长桥接。**仅编写／调整测试，未运行测试，未自行预览**；类型编译／构建及资源复制结果以 `.artifacts/implementation/library-compact-20261028/` 的日志和回执为准，M2人工验收待完成。不新增业务API，不提交、推送或合并。

<a id="equipment-native-management"></a>

2026-10-28 设备管理原生控件／批量模式候选：测试文件新增／同步默认无记录复选框及空列、显式进入／完成、零勾选保持、全选当前页、删除确认取消、搜索／类别／分页／排序／切换退出及原生控件适配（混合复选、菜单选项／关闭、受控页签）。已有编辑及删除回归保持。**未运行测试或浏览器预览**，仅编译更新demo-preview，日志与资源回执见 `.artifacts/implementation/equipment-native-management-20261028/`。不以编译代替功能或视觉验收，未提交、推送或合并。

<a id="equipment-simple-list"></a>

2026-10-28 我的设备简洁列表候选：组件用例补齐重复型号（忽略大小写）、独立型号、null及空白型号的副标题展示，并保留选中后行内编辑入口验证；既有编辑／保存／删除测试继续保留。**测试文件未运行，未进行浏览器预览或视觉验收**。本轮仅编译更新demo-preview；主题下的普通／悬停／选中、键盘焦点及窄栏视觉由用户自行验收。日志与回执见 `.artifacts/implementation/equipment-simple-list-20261028/`，未提交、推送或合并。

<a id="equipment-row-edit"></a>

2026-10-28 我的设备行内编辑候选：组件用例同步未选中无编辑按钮、按钮仅属于选中设备行、切换目标移动入口、无列表下方按钮、复用表单预填、双击不打开、勾选隔离及保存后保留选中；保存失败、稀疏PATCH与取消回归继续保留。**仅编写／修改测试文件，未运行测试或自行预览**。本轮仅编译更新demo-preview，无接口或数据变更，日志及资源回执见 `.artifacts/implementation/equipment-row-edit-20261028/`，未提交、推送或合并，用户验收待完成。

<a id="equipment-selected-edit"></a>

2026-10-28 我的设备选中编辑候选：生成／同步未选中隐藏操作、单击显示“编辑信息”、双击不打开、按钮打开共用表单、切换选中目标、勾选隔离及原有保存／失败／取消回归入口。**未运行测试或自行预览**，仅编译更新隔离demo-preview；日志与资源回执见 `.artifacts/implementation/equipment-selected-edit-20261028/`。保存、API及数据结构不变，未提交、推送或合并。

<a id="equipment-unified-form"></a>

2026-10-28 设备统一表单候选：测试文件同步原生输入控件预填、固定类型、取消／保存、编辑前不写入、保存失败保留、统一PATCH及revision、未修改不对称像元和隐藏规格保留、清空null、未保存取消确认及数值保存。**未运行测试或自行预览**，仅编译更新demo-preview；日志与回执见 `.artifacts/implementation/equipment-unified-form-20261028/`，未新增API或数据库变更，未提交、推送或合并。

<a id="equipment-doubleclick-edit"></a>

2026-10-28 我的设备编辑入口候选：生成／同步设备双击及键盘打开、单击无详情、预填与关闭无写入、勾选不打开、字段保存revision及失败保留输入、数值参数回归用例。**未运行测试或自行预览**，仅执行编译并更新隔离demo-preview；日志与回执见 `.artifacts/implementation/equipment-doubleclick-edit-20261028/`。业务接口及保存规则不变，未提交、推送或合并，用户验收待完成。

<a id="equipment-edit-action"></a>

2026-10-28 组合编辑入口候选：`EquipmentSetupTable.test.ts` 补齐／同步选中后的并排新建预设与编辑组合、编辑入口唯一、更多保留刷新／删除、组合表单预填及取消无写入、保存期间操作禁用。**仅修改测试文件，未运行测试或自行预览**；本轮仅编译更新隔离demo-preview，日志与资源回执见 `.artifacts/implementation/equipment-edit-action-20261028/`。未修改API或数据结构，未提交、推送或合并，用户验收仍待完成。

<a id="equipment-preset-filter-offset"></a>

2026-10-28 预设滤镜／Offset及参数命名候选：补齐组合多滤镜选择与保留顺序、预设只列所属组合滤镜、原预设组合外滤镜保留、恢复组合默认、增益Offset零值／清空与模式切换保留、保存失败保留滤镜／Offset／前缀、参数后缀实时更新、无前缀命名及再次编辑不重复后缀用例；同步可选前缀的草稿排序保护入口。**仅编写／修改测试文件，未运行测试或自行预览**。本轮仅编译更新demo-preview网页，无后端变更或重启；日志及资源更新回执见 `.artifacts/implementation/equipment-preset-filter-offset-20261028/`，不代表M2用户验收批准，未提交、推送或合并。

<a id="equipment-preset-minimal"></a>

2026-10-28 组合预设最小精简候选：组件用例同步选中组合后仅显示预设区域、组合编辑／删除进入更多菜单、移除ⓘ及文字悬停完整名单；补齐简化表单字段、旧预设隐藏资料不丢失、ISO／Gain零值与失败保留输入用例，异步选择边界仍保持。**测试文件仅生成／修改，未运行测试或自行预览**。本轮仅编译更新隔离demo-preview网页资源，无后端变更或重启需求；交付日志见 `.artifacts/implementation/equipment-preset-minimal-20261028/`，不代表M2人工验收批准，未提交、推送或合并。

<a id="equipment-setup-table"></a>

2026-10-28 设备组合横向表格与全列排序候选：新增 `EquipmentSetupTable.test.ts` 覆盖六列、空值、多件／长名称提示、历史成像系统、行选择与勾选隔离、六列排序参数／方向、回首页及清空选择、组合与预设脏草稿／保存保护和素材库排序隔离。`test_setups.py` 新增五类设备升降序、分页前排序、搜索／类别过滤、空值最后、名称／ID稳定顺序、多件顺序、历史成像系统及排序参数接口范围用例；既有设备与组合测试按表格语义入口更新。**本轮仅生成和修改测试文件，未运行任何测试或浏览器预览**。OpenAPI导出、生产编译和隔离demo-preview更新结果独立记录在 `.artifacts/implementation/equipment-setup-table-20261028/`；这些交付操作不代表功能测试通过或用户M2验收批准。候选在 `codex/m2-ui-acceptance`，未提交、推送或合并。

<a id="equipment-toolbar"></a>

2026-10-28 设备管理工具栏精简候选：统一组合／我的设备的搜索和新建操作，刷新置于更多，直接勾选后出现删除操作，固定50条且仅多页时显示分页，保留素材库分页偏好。新增 `EquipmentToolbar.test.ts` 覆盖两个页签的空状态和唯一新建入口、勾选及取消删除、直接类别筛选、固定分页与素材库偏好隔离、空末页刷新和更多关闭；`SettingsOrganization.test.ts` 同步保留脏草稿／保存中的刷新阻止及设备类别用例。**本轮测试文件未运行，未进行浏览器预览或用户验收**；编译与网页资源更新结果单独保存到 `.artifacts/implementation/equipment-toolbar-20261028/`，不以构建成功代替功能验收。当前候选位于 `codex/m2-ui-acceptance`，未提交、推送或合并。

<a id="m2-ui-optimization"></a>

## 2026-10-28 M2 UI 16项优化候选

候选为`codex/m2-ui-acceptance`的`be0422e5`加本轮未提交改动；保留B31／B32／B41等原有未提交内容。本轮不提交、推送或合并。实现逐项及证据见[报告](../../.artifacts/implementation/m2-ui-optimization-20261028/report.md)，原始问题清单保留为实施前证据。

- 前端：`pnpm --dir frontend --filter @astrophotoflow/ui test tests/modules/data`，21个文件、156项通过；包括实际纳秒响应、图像组PATCH目标、部分异常导入、迟到观察、键盘编辑、预设模式草稿／0及空筛选回归。
- 类型及构建：UI包vue-tsc、原生tsgo检查及完整生产构建通过；最后的纯呈现调整另经Vite生产构建。依赖巡检72模块、210依赖，0错误／9条已有context循环警告。没有新增包依赖、后端接口、配置存储或数据库迁移。
- 后端契约回归：`pytest tests/modules/data/test_science_inputs.py tests/architecture/test_import_boundaries.py -vv -s --basetemp .artifacts/implementation/m2-ui-optimization-20261028/pytest-tmp`，13项通过。初次受限进程无输出，显式中止后在获准环境运行成功；不把中止视为通过。测试使用自己的临时目录。
- 真实Computer Use：文件观察200且页面显示一致；切换A到B清除A结果；项目添加图像组显示正确字段，真实PATCH `/datasets/{id}` 200并重新读取，测试备注随后恢复null，项目固定组仍v1；预设未设置可见、Gain 0经模式切换保留且测试草稿已取消；侧栏500／700px，表格实测clientWidth=scrollWidth分别478／678；完整长文件名在限宽提示中换行，内容宽358、无横向溢出；原生输入Gain=0真实提交，任务completed，content／metadata／preview均available，value_sources.gain=manual。
- 证据范围：复用原隔离demo-preview（32688／32690），只更新web资源、无服务重启；原正常合成FITS的SHA-256不变，新增一份明确合成样本供验收。M2完整人工批准、永久清理、真实设备组合与历史快照的全矩阵，以及M5消费者联调未由本轮候选自动签通过。后续人工操作顺序和安全边界见报告。

## 2026-10-28 M2素材库产品／风格及真实操作审查

分支`codex/m2-ui-acceptance`，基线`be0422e5`加保留的未提交候选，隔离demo-preview网页32688／服务32690。两份GPT-6 Luna high只读审查后，主代理通过Computer Use核对空库／有数据筛选、导入、设备／组合／预设、图像组校准说明、预览、项目固定组选择、单图内容观察、切换状态、键盘编辑、校准库和回收站空态；未更改产品代码，未执行提交／推送／合并。

- 两份正常合成FITS真实上传成组，任务completed，成员content／metadata／preview均available；60／120秒及Gain=0保留。正常预览可打开，选用固定图像组v1成功。
- 实际故障：文件检查显示“服务成功响应不符合接口契约”；直接读取同一服务响应为unchanged，实际前端schema.safeParse明确在observed_mtime_ns拒绝大于9007199254740991的纳秒数。切换另一素材后还残留前一条错误。项目添加图像组展示不适用的拍摄目标和未分类；源码确认字段保存将误发项目API，本轮没有实际提交该错误编辑。Enter不能进入行内编辑，鼠标双击能进入。
- 故意无效FITS任务completed_with_errors，content=available、metadata=failed、preview=unsupported；默认简约页只显示100px占位和未分类，处理问题要切细节并横滚状态列才看到。没有把登记／内容入库误记为科学解析成功。
- 证据与16项待修清单：`.artifacts/acceptance/m2-ui-review-20261028/`下`review.md`、两份独立审查、编号截图／AX记录、HTTP任务响应、`content-contract-check.json`及`fixture-ledger.json`。73个既有源码文件状态核对不变，两份原合成文件哈希不变；没有删除记录、没有修改正常dev数据。只运行诊断性schema校验，未重跑全量回归。
- 未验：changed接纳、reference变更／缺失、409、回收站移入／恢复／永久清理、完整校准消费及B22／B24／⑤真实运行交接。以上审查不表示M2用户验收通过；本轮提出的优化尚未实施。

2026-10-28按用户最新授权完成本地Git整理：已确认的M1设置修订及两处M2语法修复提交在demo，随后快进合入dev（`be0422e5`）；本地`feature/database_management`已删除，当前分支为`codex/m2-ui-acceptance`，用于M2 UI／操作优化与功能验收。M2 Milestone尚未获用户批准。其余B31／B32／B41等未提交内容已完整保留到当前工作区，未纳入dev；没有推送，main保持不变。此前不提交／不合并约束已被本次明确授权覆盖，仅限上述交付。

集成前在移除其余未提交业务改动的干净候选上复核：Python配置／客户端／代理／架构／数据服务110项通过（保留既有SQLAlchemy表排序警告），配置组件10项、原生设置／侧栏64项通过，UI包及原生应用类型检查通过。发现并补齐了重启测试mock缺失的selectDirectory方法；OpenAPI重新生成，85项公共操作与候选语义一致。原生产构建与浏览器证据继续使用上列已验收候选，本次Git集成未重新启停实例或触碰正常dev数据。

2026-10-28用户明确确认“设置这部分可以了”：demo原生设置入口、展开section、目录选择与绝对路径展示、说明／路径悬停呈现按当前已展示候选的设置范围记为用户接受。用户要求继续M2数据与资产管理验收，尚不表示M2通过；本次Git整理按上述最新明确授权执行。M2隔离验收使用demo-preview和`.artifacts/acceptance/m2-user-20261028/`，首轮仅准备两份合成FITS，尚未导入。

## 2026-10-28 demo：工作台长说明与路径悬停提示

仅调整前端呈现，保留展开section、目录选择、运行地址及关键状态；不修改后端接口或路径解析。使用原生FormItem name-suffix与Button tooltip展示说明和完整路径，区分已保存绝对路径和当前输入。真实控件测试观察到原表单任意点击会清除保存提示，改为仅实际内容变更时清除。

- 私有UI配置测试10项、原生控件交互测试1项通过，原生类型检查及生产构建通过。
- 隔离浏览器9项检查通过：默认隐藏说明、区块与链接保留、完整路径悬停、长路径换行且表单不变宽、移开关闭、真实键盘聚焦、区分草稿／保存路径、提示点击无操作、服务端配置token不变。没有发送配置保存／重启请求，pageerror为空。
- 证据：`.artifacts/implementation/demo-settings-tooltips/browser-report.json`、`normal.png`、`hover.png`及定向测试／构建日志。首轮原生控件点击保存状态回归失败和修复、首轮浏览器程序化focus被原生策略忽略的记录均保留；后者改为实际Shift+Tab后通过。
- demo-preview保持在线供用户验收；该设置范围已由用户确认并按上述最新授权集成。

## 2026-10-28 demo：工作台迁入原生设置候选

基线为demo／741f6f1d加既有未提交实现；本次只修改前端设置、定向测试和文档，不提交、推送或合并。工作台使用原生设置窗口和FormItem／Button／Input，移除独立侧栏。隐藏规则只影响APF本地呈现，分类／搜索／面板定位一致，保留原生设置值与其他分发版本行为。

- 私有UI配置测试7项通过；原生设置导航／搜索／窗口／侧栏63项及真实原生控件集成1项通过。类型检查与生产构建通过；前端依赖检查0 error、9条既有循环warning。日志位于`.artifacts/implementation/demo-settings/`。
- 隔离demo-preview真实浏览器7类检查通过：保存不改当前采用值、双页冲突保输入、显式重启采用、无效主机拒绝、隐藏项搜索及工作台搜索、原生语言项保留、关闭设置保留画布。报告`browser-final/report.json`及截图在同目录；验后实例保持在线供用户验收。
- 首轮Vitest因sandbox临时转换文件缺失失败，使用项目内临时目录后执行；之后发现测试夹具共享对象、测试工具导入和i18n装配问题，均修复并保留各轮日志。首次浏览器测试因原生帮助图标进入可访问名称导致定位过严失败，按实际名称修正；失败截图及报告保留于`browser-first-failure/`，无pageerror。
- Figma插件未安装，网页规范不可读取；本轮直接复用仓库原生组件和主题，不声称完成Figma专项核对。真实浏览器通过不代签用户批准，也不表示M3～M5未实现能力通过。

<a id="demo-docs-code-alignment"></a>

## 2026-10-28 demo：源码与文档颗粒度对齐

基线为 `demo`／`741f6f1d` 加当前未提交实现，用户指定以当前代码为准，只改文档。补齐[源码文件／公开函数／消费者映射](../architecture/module-map.md#31-当前文件与公开函数映射)，纠正M1／M2、B31／B32／B41与⑤剩余能力的状态，以及详细设计中的已有文件／测试标记。保留原有未提交源码和历史证据，不提交、推送或合并。

本轮静态检查：Python AST核对60个具名函数／方法均存在；OpenAPI快照统计89项公共HTTP操作，其中软件5项；所改文档相对原稿没有新增失效文件链接。结果为 `.artifacts/docs-code-alignment/static-checks.json`，修改前快照位于同目录 `before/`。未重跑业务测试、构建或真实网页／软件运行，不新增Milestone批准、安装、节点加载或工作流闭环通过结论。

<a id="demo-b31-probe"></a>
## 2026-10-28 demo：B31 原型进行中

候选基线为本地 `dev` 的 `741f6f1d`；Windows，隔离目录 `.artifacts/implementation/B31/probe`。本机便携 `siril-cli.exe --version` 返回 `siril 1.4.4`；随包 `share/doc/siril/LICENSE.md` 为 GPLv3 文本。官方 [1.4.4 发布页](https://siril.org/download/2026-06-17-siril-1-4-4/)链接到 [UCRT64 Windows Portable archive](https://free-astro.org/download/siril-1.4.4-ucrt64_win.zip)。保存的 archive SHA-256 为 `AB276BEDD3E805D523C535C1FE813FD68AD4F9DD1C1E5367278B6D027E53A6EE`；抽取出的 6,839 个文件逐一与 archive 内容匹配。发布页未提供可核对的校验和或签名，故来源关联已核实但发布物来源未获独立密码学认证；细节见 `.artifacts/implementation/B31/source-verification/source-verification.json`。

- `single.ssf` 对隔离 FITS 副本运行 `autostretch -linked`，退出码 0，默认参数为 -2.8／0.25，生成 4144×2822、单通道、32 位 `result.fit`；输入和输出 SHA-256 分别为 `79734c29dcd9af8218a81bc3d709143b87984c701798130ef8e5034458d7ef5e` 和 `be0685386e6bcad4f0d41213baf52167d24767e7e5ce476f20982fa3c8478fc0`。本轮以 Siril 再次读取 FITS 并运行 `bg`／`bgnoise`，退出码 0；Astropy 确认输出尺寸一致、所有像素有限。该输入匹配 Dataset 中 IC 1805 的 Ha master light；本次未做视觉质量评分或独立图像评审。证据为 `probe/single-readback.log`、`probe/single-readback.json` 及 `probe/hashes-after.txt`。
- `sequence.ssf` 使用两份原始 FITS 的隔离副本，`convert` 和 `seqstat ... basic` 退出码 0，生成两行统计；`output/sample_conversion.txt` 记录 01、02 与输出顺序，`sequence.log` 记录读取和处理。原件及副本散列记录在 `probe/hashes-before.txt` 与 `probe/hashes-after.txt`。这只证明转换和序列统计，不证明科学叠加或取消。
- 2026-10-28重盘`tests/data/Astro_Dataset`：29个文件，18 FITS／11 XISF；FITS主HDU的形状、位深、目标、FILTER、曝光及SHA-256记录在`.artifacts/implementation/B31/dataset-inventory.json`。所有11个XISF仅读取`XISF0100`头及XML元数据，提取图像几何／样本格式／类型／通道、Object／Filter／单帧曝光和Creator；像素未解码。XISF元数据也没有同一精确Object+Filter的多成员文件组；部分目标字段缺失，保持unknown；文件内的rejection map及crop mask不是序列成员。FITS与XISF证据均未发现可确认的同目标同滤镜多文件序列，不把Ha/H或不同滤镜别名猜成同一组。XISF 1.0格式参考链接和逐文件详情在dataset inventory；当前仍待用户提供序列、选择所列样例数据来源，或接受记录缺口。
- XISF实际可读性：在隔离副本上由Siril 1.4.4运行`requires 1.4.4; load input.xisf; bg; bgnoise; close`，退出码0，读取1层、3854×3129的XISF MasterLight，背景0.003898、噪声0.00007191；未做处理、未生成输出。运行后原件与副本SHA-256均为`207c487ec7333e488717a99f9d770497a2f1b0585ced016acc900dcafb2894d2`。Object元数据缺失保持unknown；此项只证明单文件读取，不能证明序列处理。日志和测量见`.artifacts/implementation/B31/xisf-load-20261028-1240/`。
- CLI停止原型：以`tests/data/Astro_Dataset`一份3840×2160、RGB、32-bit FITS只读源的同散列隔离副本运行准确Siril 1.4.4脚本；日志已显示`autostretch -linked`正在计算时，用Windows `Stop-Process -Force`终止本次新建的PID。进程退出码为-1、进程消失、最终save未到达且未生成输出，源及副本SHA-256均为`4109F40DCBF2BC6A348ADF66749F60B61E9C44CAAF347E299D4F98B87A51BBA9`。stdout/stderr及事实见`.artifacts/implementation/B31/cancel-probe-20261028/`。这证明外部进程被强制停止，不证明Siril有优雅取消，不证明③适配器/API取消；任务仍未由原型记为完整通过。
- 参数错误原型：对隔离Ha FITS副本执行真实Siril脚本`autostretch -definitely-invalid`。stdout记录Invalid argument与第3行参数错误，脚本停止，CLI退出码1，后续save未执行且无输出；原件和副本SHA-256均为`79734C29DCD9AF8218A81BC3D709143B87984C701798130EF8E5034458D7EF5E`。证据在`.artifacts/implementation/B31/parameter-error-probe-20261028/parameter-error-outcome.json`与`direct-run.log`。仅证明这一参数错误路径会返回非零退出。
- 真实图像测量：Siril 1.4.4 `findstar -out=... -maxstars=500`分别处理Ha master-light的baseline及三轮输出，均找到上限500个Gaussian-profile星。Siril摘要FWHM依次5.471／5.031／5.201／4.551 px；逐星FWHM轴比中位数0.9478／0.9494／0.9488／0.9498；被检测500星中的Siril `Sat`标记占比42.8%／30.0%／35.4%／21.2%，Gaussian RMSE中位数0.01637／0.01498／0.01520／0.01357。完整CSV、stdout和首三轮可复算摘要在`.artifacts/implementation/B31/psf-rounds-20261028/`，第3轮完整摘要在`.artifacts/implementation/B31/round3-targetbg-20261028/round3-measurements.json`。这些是对已经拉伸数据的自有量化比较，不是光学seeing/原始PSF或4/5质量分；上限500使星样本截断，Ha单通道也不能评分色平衡。
- 真实参数调优取 IC 1805 Ha master light 的同一输入副本，不覆盖原件：baseline `autostretch -linked` 默认 -2.8／0.25；第1轮改 target background 为0.18，背景测值0.180、背景噪声0.006356；第2轮改 shadowsclip 为-3.0、target background为0.22，背景0.220、背景噪声0.006888；第3轮仅将target background设为0.12，背景0.120、背景噪声0.004581。baseline 对应0.250／0.008068。四版输出均为4144×2822单通道32-bit，像素有限；四个预览固定以0～1显示，便于观察整体亮度，不作为最终质量评分。第3轮降低背景和被检测500星中的`Sat`标记占比，但固定范围预览明显更暗、暗弱发射受抑；新增CLI、回读、catalog、hash与预览证据在`.artifacts/implementation/B31/round3-targetbg-20261028/`。这些仍是单张master light拉伸，不能替代序列校准／叠加。
- 新增Round 4真实单参数复测：准确Siril 1.4.4在同一Ha master-light副本运行`autostretch -linked -3.0 0.18`，相对Round 2只将target background从0.22降至此前试过的0.18。CLI与独立readback均退出0；原件／输入副本SHA相同`79734c29…`，输出`03f7e521…`，4144×2822单通道32-bit且像素有限。Siril测得background 0.1801、bgnoise 0.005939、500星封顶样本FWHM 4.944625；exact-1像素1、≥0.999共55。固定0–1预览见`.artifacts/implementation/B31/round4-targetbg018-20261028/round4-fixed-0-1.png`；测量／hash／命令证据在同目录。Sol Low同尺度独立视觉复评已请求，门槛仍待评价；单张master处理不能替代真实序列。
- Round 4 Sol Low独立复评：与Round 2同尺度直接看图，Round 4背景观感4（Round 2 3），但弱结构3（Round 2 4）、core/halo3、噪声／伪影3，星形／锐度4、整体4；评审者略偏Round 2。Round 4未达到全部≥4门槛。分项见`.artifacts/implementation/B31/image-review/sol-low-round4-targetbg018-20261028.md`。
- 新增Round 5真实参数中点：Siril 1.4.4在原始Ha副本运行`autostretch -linked -3.0 0.20`，相对Round 2只将target background由0.22改至Round 4与Round 2之间的0.20。CLI/readback均退出0，原件未变，输出4144×2822单通道32-bit且有限；背景／噪声0.2001／0.006430，500星FWHM 5.080234，exact-1为1、≥0.999为59。日志、hash、预览和测量见`.artifacts/implementation/B31/round5-targetbg020-20261028/`；Sol Low同尺度评分待回。
- Round 5 Sol Low独立复评：同尺度与Round 2相比，背景4（Round 2 3）、弱结构4（Round 2 4）、core/halo仍3、噪声／伪影仍3、星形／锐度4、整体4；变化较小，reviewer无强总体偏好。Round 5仍未满足所有关键≥4项。完整评审`.artifacts/implementation/B31/image-review/sol-low-round5-targetbg020-20261028.md`。
- 真实降噪试验：准确Siril 1.4.4对隔离线性Ha副本运行`denoise -nocosmetic`，随后同样执行Round 2的`autostretch -linked -3.0 0.22`作固定范围视觉比较；全尺寸32-bit FITS有限值，CLI／readback／同参数stretch均exit0，原件hash不变。NL-Bayes报告线性背景噪声由输入0.00003994降至0.00001397；拉伸后bgnoise 0.001862、FWHM 5.216903、exact-1为1。默认`denoise`与`-nocosmetic`两种运行都记录`Python validation failed`及`no suitable data in src fits`，同时报告NL-Bayes完成并保存；默认与`-nocosmetic`输出有1408像素不同，最大差0.000345。Sol Low独立评分：noise/artifacts 4、faint structure 4，core/halo 3、background 3、stars/sharpness 4、overall 4，略偏去噪版但门槛仍失败；错误日志还使denoise执行健康状态未验证。证据见`.artifacts/implementation/B31/denoise-nlbayes-default-20261028/`、`denoise-nocosmetic-20261028/`及`image-review/sol-low-denoise-nocosmetic-20261028.md`。
- 去噪＋高光压缩组合试验：在新副本上串行执行Siril 1.4.4 `denoise -nocosmetic`→`asinh 1000 0`，生成4144×2822单通道32-bit有限输出，exit0，原件hash未变，background／bgnoise 0.1447／0.0008056，exact-1为1、≥0.999为4。Sol Low独立评分：halo4、背景4、噪声4、弱结构3、星形/锐度4、整体4；背景更安静、弱上/左发射更难辨认，质量门仍失败。`denoise`仍记录Python validation／no-suitable-data错误，且组合候选没有星点profile统计，执行健康状态仍受限。命令、日志、测量、预览见`.artifacts/implementation/B31/denoise-asinh1000-20261028/`，评审见`image-review/sol-low-denoise-asinh1000-20261028.md`。
- 去噪调制中点试验：真实执行文档范围内的`denoise -nocosmetic -mod=0.5`后接`asinh 1000 0`；同源副本，CLI/readback exit0，原件hash不变、有限32-bit输出，背景／noise 0.1448／0.001770，exact-1为1、≥0.999为4。未声明星点profile数值，因为未重试先前触发的Python venv健康错误；denoise log仍有`no suitable data in src fits`。Sol Low评审与full denoise相比未见可信的弱结构恢复，m=0.5 noise回升而弱结构仍3，Round 2仍较易读。评审`.artifacts/implementation/B31/image-review/sol-low-denoise-mod050-asinh1000-20261028.md`；原始测量和预览`.artifacts/implementation/B31/denoise-mod050-asinh1000-20261028/`。
- DA3D detail-stage实验：真实运行`denoise -nocosmetic -da3d`→`asinh 1000 0`，日志明确报告DA3D完成；处理／readback exit0，输出有限4144×2822 mono 32-bit，background／noise 0.1447／0.0007404，原件hash未变。日志仍报告`no suitable data in src fits`，无findstar统计；Sol Low同尺度评审待回。命令、stdout、测量和预览见`.artifacts/implementation/B31/denoise-da3d-asinh1000-20261028/`。
- DA3D候选Sol Low独立复评：与完整NL-Bayes→Asinh图极为相似；core/halo、background、noise各4，faint structure仍3，stars/sharpness4、overall4。Round 2的弱发射可见度仍更好，故均未满足所有关键项≥4。DA3D noise估计0.0007404略低于NL-Bayes0.0008056，但不证明保留了更多真实信号；no-suitable-data日志仍使执行路径需保留限制。评审`.artifacts/implementation/B31/image-review/sol-low-denoise-da3d-asinh1000-20261028.md`。
- Numeric stored-output endpoint diagnostics: the byte-identical Ha input and all four stretched FITS outputs each have one pixel exactly 1.0 and zero pixels exactly 0; pixels >=0.999 number 1 / 77 / 59 / 62 / 47 (input / baseline / round1 / round2 / round3) out of 11,694,368. This does not establish raw sensor saturation or explain visible halos; full arrays, hashes and method are in `.artifacts/implementation/B31/pixel-clipping-diagnostics-20261028.json`.
- GPT-6.1 Sol Low independently interpreted the endpoint data: each input/output retains one exact 1.0 pixel; near-ceiling counts are 0.0000086% / 0.000658% / 0.000505% / 0.000530% / 0.000402% (input/baseline/round1/round2/round3), values >=0.999 are not themselves evidence of clipping, and the counts have no spatial/radial information for halo analysis. Visual scores remain unchanged; halo remains 3/5 in every round. Details are in `image-review/sol-low-2026-10-28.md`.
- Local endpoint-coordinate follow-up by GPT-6.1 Sol Low: the sole exact-1.0 pixel is at [y=2418,x=41] in the input and all outputs; immediate-neighbor median rises from 0.676 in input to 0.9969–0.9987 after stretching. This is near-ceiling compression around one maximum-selected, edge-near feature; it does not identify a star/PSF/halo or raw saturation, and does not change the 3/5 halo scores. See `pixel-ceiling-profile-20261028.json` and `image-review/sol-low-2026-10-28.md`.
- 独立视觉评审：GPT-6.1 Sol Low在同一显示尺度检查baseline及三轮真实预览；分项和限制见`.artifacts/implementation/B31/image-review/sol-low-2026-10-28.md`。Round 2为评审者偏好的折中；Round 3背景观感较安静但压低暗弱发射。四版星形状／清晰度均为4、光晕处理均为3；背景为3／4／3／4，噪声／平滑伪影为3／4／3／4，暗弱结构为4／3／4／3，整体为4／3／4／3。光晕关键项未达到每项≥4门槛，且预览不能判定数值剪裁或校准科学性；图像质量门槛及用户接受尚未通过。
- 第3轮CLI日志还报告sandbox内Pictures目录访问被拒及LOCALAPPDATA Siril配置文件重命名失败；脚本仍记录成功并保存／回读输出。本轮只确认图像处理与产物回读，不声称Siril设置已持久化或默认图片目录可用。
- 官方命令资料抓取于 2026-10-28；该时点的 [Commands](https://siril.readthedocs.io/en/stable/Commands.html) 明确称列出 Siril 1.4.4 全部命令，[Headless](https://siril.readthedocs.io/en/stable/Headless.html) 也标示 1.4.4。结构化记录含 199 项：181 Scriptable、18 Non-scriptable，重复 0、未知标记 0。原始页面、SHA-256、获取时间及条目位于 `.artifacts/implementation/B31/official-commands.html`、`inventory-summary.json`、`commands.json` 和 `official-headless.html`。其余命令尚未逐项独立复核语义。
- 覆盖矩阵截至2026-10-28 15:11列出16条经Siril 1.4.4 CLI脚本实际观察的命令、199条部分语义复核、0条完整语义复核、183条未执行及0条完整安全审查。source-only参数复核另覆盖asinh／autoghs／binxy／ccm／crop、calibrate／calibrate_single／register／stack、denoise／epf／fixbanding／fmedian／limit、conesearch／findcompstars／ght／linstretch／modasinh／mtf、pyscript／pm／profile／find_hot／extract_HaOIII／pcc、makepsf／platesolve、cosme／linear_match／parse／split_cfa／seqapplyreg／unsharp／wavelet、resample／rotate／rgbcomp／savejpg／savejxl／seqfindstar、rl／sb／rmgreen／satu／rgradient／seqpsf；另有source-only复核seqght／seqmerge_cfa／seqmodasinh／setfindstar／setmem／setcpu／setcompress／setphot；这八项无CLI／Node／registry证据。未知类型／范围／依赖／风险仍标unknown。`pyscript`明确标为任意Python执行高风险且不生成通用Node；pcc/catalog查询可能访问远程目录但未运行；EPF的guided选项名仍有文档歧义，`seqpsf`的headless坐标条件仅由文档说明、未实际测试。`convert`、`findstar`、`seqstat`、`jsonmetadata`运行证据有范围限制；`stat`及`jsonmetadata`曾报bundled Python初始化错误，统计/JSON仍输出且退出0，依赖影响未知。计数及逐条依据见`.artifacts/implementation/B31/coverage-matrix.json`。
- 另对18项官方Non-scriptable命令(addmax、clear、clearstar、ddp、dir、disto、inspector、load_seq、ls、new、reloadscripts、seqsetmag、sequnsetmag、setmag、show、tilt、unsetmag、visu)补了语法、参数、输入／输出与GUI／平台限制的source-only记录；仍未运行CLI、生成节点或核查安全风险，不代表可用于Siril脚本。
- 另source-only复核14项Scriptable控制／序列／设置命令(capabilities、get、getref、help、pwd、select、seqclean、seqheader、set、set16bits、set32bits、setext、setref、unselect)：记录选择范围、清理状态、FITS头输出、设置与位深／扩展名效果；INI导入、metadata写出及状态持久性风险仍未实际核查。
- 另对savebmp、savepng、savepnm、savetif、savetif32、savetif8记录官方输出格式／位深及选项；输出路径、覆盖行为与实际保存均未核实。
- 另source-only复核convertraw、link、merge、merge_cfa、dumpheader、split、update_key、sequpdate_key的序列／文件范围、FITS头读写、CFA模式及路径副作用；运行、覆盖与持久性仍未核实。
- 另source-only复核cosme_cfa、find_cosme、find_cosme_cfa、fix_xtrans、grey_flat、extract、extract_Green、extract_Ha的CFA像素校正、滤镜信号提取与小波平面语义；参数范围、输出落位和部分图像适用范围仍未知。
- 另source-only复核fdiv、fmul、iadd、idiv、imul、isub、neg、nozero、offset的算术／位深语义；除官方明示范围外，标定范围、兼容性和除数为零行为均未核实。
- 另source-only复核cdg、clahe、entropy、gauss、log、mirrorx、mirrorx_single、mirrory、rotatePi、threshlo、threshhi、thresh；其中mirrorx_single会在需要翻转时覆盖原文件，threshhi／thresh的官方语法与说明有未解歧义。
- 另source-only复核catsearch、offline、online、icc_assign、icc_convert_to、icc_remove、spcc、spcc_list；标明catalog远程请求、站点元数据、配置切换、ICC配置与SPCC输入来源，未执行网络操作或图像校正。
- 另source-only复核invght、invmodasinh、invmtf、starnet、subsky、synthstar、unclipstars、unpurple、wiener、wrecons；external StarNet、PSF/序列前置、像素变换及unpurple参数歧义均保留未验证状态。
- 另source-only复核seqccm、seqcosme、seqcosme_cfa、seqcrop、seqextract_Green、seqextract_Ha、seqextract_HaOIII、seqfind_cosme、seqfind_cosme_cfa、seqfixbanding；仅记录官方序列规则，无同滤镜科学序列运行证据。
- 另source-only复核seqinvght、seqinvmodasinh、seqlinstretch、seqmtf、seqprofile、seqplatesolve、seqresample、seqrl、seqsb、seqsplit_cfa；无同滤镜序列执行，seqresample语法与正文对-maxdim=存在未解差异。
- 本轮最后source-only复核boxselect、exit、ffill、fftd、ffti、fill、histo、light_curve、livestack、psf、seqstarnet、seqsubsky、seqtilt、seqwiener、stackall、start_ls、stop_ls、trixel，覆盖了全部余下未逐项复核的目录命令。`seqwiener`语法名称不一致；实时叠加状态、StarNet外部程序及全目录stack操作均未实际执行。
- 真实`unclipstars`实验：Round 2 FITS副本进入隔离目录，Siril 1.4.4命令及保存/readback均退出0；CLI报告179颗星去饱和，但Astropy确认主HDU 11,694,368个像素与输入逐值完全相同，Round 2与新结果的findstar统计也相同。输出仅更新FITS DATE并添加ICCProfile HDU，不记作图像改善。PNG导出日志有Python venv初始化错误，但仍写出双`.png`扩展文件；同范围预览仅有每像素最多1灰度级量化差。证据在`.artifacts/implementation/B31/unclipstars-20261028/`。
- GHT替代拉伸试验：在同一原始Ha master-light副本运行`ght -D=4 -HP=0.8`，输出4144×2822单通道32-bit并另进程回读。固定0–1图与Round 2相比背景更暗；500星样本Sat由35.4%增至59.2%，>0.999像素由62增至716；星形/背景及halo需独立评审，当前不作为采用结果。`readback.log`尾部close报告sandbox配置文件写入错误，但脚本退出码0。证据在`.artifacts/implementation/B31/ght-hp08-20261028/`。
- GPT-6.1 Sol Low独立复评Round 2、GHT D4/HP0.8和D6/HP0.8：均未达全部≥4门槛，整体分别4、2、3；Round 2仍优先。D6显著增加弱结构可见度但更亮/发白且halo/core仅2；GHT D6保存像素端点计数为2260 exact 1.0、5758≥0.999，输入各为1。评审和限制见`.artifacts/implementation/B31/image-review/sol-low-ght-20261028.md`。
- GHT D5/HP0.8独立评分：overall4，halo/core3，背景4，弱结构4；Round 2略优。D5 endpoint计数773 exact 1.0、2047≥0.999，输入各1。D5/HP0.6单参数变体与D5/HP0.8主HDU像素完全相同。复评见`.artifacts/implementation/B31/image-review/sol-low-ght-d5-20261028.md`；D4/D5/D6均未过全部关键≥4门槛。
- GHT symmetry-point follow-up: after GHT D5/HP0.8 retained core/halo 3/5, changed only documented SP (default 0, range 0-1) to 0.1, 0.01, 0.005 and 0.001 on isolated copies of the same linear Ha master. All final runs/readbacks exited 0, outputs finite, source hash unchanged. SP0.1/0.01/0.005 strongly suppressed faint emission; SP0.001 remained near SP0. Sol Low same-scale review found no candidate passed every applicable >=4 criterion; Round 2 remained slightly preferred. Measurements and output hashes: `.artifacts/implementation/B31/ght-sp-response-20261028.json`; review `.artifacts/implementation/B31/image-review/sol-low-ght-d5-sp01-20261028.md`. The first SP0.1 harness could not decode Siril output with Windows GBK; its saved FITS was read back and a fresh isolated repeat exited 0 with identical primary pixels; first exit remains unknown.
- GHT assessment reflects the final SP/LP and B-range evidence; sidecar SHA `0EBBD74E5F907CC9BDA91804C8D83F3312830BA90891A65EBA0E956916979B2E` matches manifest/coverage. Counts: 199 total, 17 CLI-observed, 182 unexecuted, 12 successful, 5 partial, 5 scope-limited, 2 parameter-error commands, 0 complete semantics/security. GHT semantic review remains partial, safe NodeDefinition not generated; parameter_error_probe is invalid_range_rejected. `tests/modules/software/test_service.py` **9 passed** after the final wording fix; log `.artifacts/implementation/B31/ght-b-range-rationale-service-tests-20261028.log`.
- GHT LP follow-up: held D5/HP0.8/SP0.01 fixed and changed only documented LP from 0 to midpoint 0.005 and boundary 0.01. Both Siril runs/readbacks exited 0, produced finite FITS and preserved source hash. Sol Low found LP0.01 brighter/more readable than LP0.005, but both remain below every-applicable >=4; Round2/D5 SP0 remain preferred. Metrics `.artifacts/implementation/B31/ght-sp01-lp-response-20261028.json`; independent supplement `.artifacts/implementation/B31/image-review/sol-low-ght-d5-sp01-lp-supplement-20261028.md`.
- GHT B-range discrepancy: captured Siril 1.4.4 official description lists B=-5..15, but real CLI `ght -D=5 -B=-1 -HP=0.8` exited1 with `B must be >= 0.0 and <= 15.0`; no output/readback was created and original SHA remained unchanged. B=0 worked in the existing D5 baseline; positive bounds were not swept. Keep both sources visible; do not silently correct the official text. Evidence `.artifacts/implementation/B31/ght-d5-bneg1-hp08-20261028/parameter-error-outcome.json` and `processing.log`.
- Sol Low independent B-range review: confirms the official -5..15 description conflicts with the B=-1 CLI error; B=0 is observed valid, positive bounds are not swept, and no 0..15 support claim is made. A follow-up review of corrected node/close wording is pending. Report `.artifacts/implementation/B31/image-review/sol-low-ght-b-range-review-20261028.md`.
- Final GHT catalog GET after the node-rationale correction: isolated schema-0009 APF returned 200/199 unique commands; served GHT assessment fields exactly matched the current sidecar, including the official/runtime B-range conflict, and SOS denoise notes remained intact. PID 78132 stopped. Evidence `.artifacts/implementation/B31/http-command-catalog-smoke-ght-sp-20261028/http-smoke-result-r5.json`.
- Updated-catalog real HTTP GET after the SP/LP/B-range assessment: isolated schema-0009 APF on 127.0.0.1:32787 returned 200/199 unique commands, current GHT SP/LP and B=-1 contradiction notes, and unchanged SOS denoise notes. Attempt1 startup failed before GET because isolated DB directories/schema were not prepared; later harness assertions missed grouped SP wording, corrected against saved actual responses without another GET. Final corrected report `.artifacts/implementation/B31/http-command-catalog-smoke-ght-sp-20261028/http-smoke-result-r4-corrected.json`; service PID8188 stopped. No ComfyUI/dev data touched.
- Final catalog GET after GHT rationale correction: isolated schema-0009 APF returned HTTP 200/199 unique commands; all served GHT assessment fields matched the local sidecar, including partial semantic status, not_generated node and the corrected B-range/settings rationale; denoise SOS notes remained. PID 78132 stopped. Report `.artifacts/implementation/B31/http-command-catalog-smoke-ght-sp-20261028/http-smoke-result-r6.json`.
- Asinh真实参数试验：从同一线性输入分别运行100、500、1000（offset=0），输出均有限且另进程回读成功；固定0–1预览仍比Round 2暗。bg从0.0252/0.0908/0.1450递增，bgnoise从0.000738/0.002286/0.002973递增； exact-1始终1，≥0.999分别2/3/4。100档readback报告嵌入Python校验/venv错误但统计仍输出。独立评分已请求，未作为采用结果。证据在`.artifacts/implementation/B31/asinh-*-20261028/`。
- GPT-6.1 Sol Low独立评分Asinh100/500/1000：overall1/2/3，Asinh1000弱结构3/5、halo4/5；Round 2仍优先，色彩对单Ha不可评，质量门未通过。review `.artifacts/implementation/B31/image-review/sol-low-asinh-20261028.md`。
- Siril 1.4.4 `asinh 1000 0 -clipmode=globalrescale`真实CLI/readback均退出0；相对同输入的默认Asinh1000候选，仅命令模式不同。两份FITS主HDU逐像素完全相同（0个差异，max absolute difference 0），HDU数相同，只有主HDU `DATE` header不同；不作为新图像变体或质量进步。证据和散列见`.artifacts/implementation/B31/asinh-globalrescale-20261028/`。
- 全部199个命令行当前都有source-based security_risk说明或明确unknown；覆盖文档记载的文件读写／覆盖、网络或外部程序、会话状态、元数据和内存图像副作用。该备注覆盖不等于逐项安全通过：完整security审查仍为0，路径、权限、真实网络和运行期行为未全面核对。依据见`.artifacts/implementation/B31/coverage-matrix.json`。
- B31/B32候选：固定Siril 1.4.4官方命令清单及逐命令assessment sidecar已接入只读HTTP目录；SoftwarePanel显示Scriptable、参数／范围／上下文／I-O／Headless／依赖／风险／定义／registry／CLI状态与原因，unknown保持显式，并可搜索assessment字段。包查询不把Downloads手动副本视为平台安装。验证：software service **9 passed**、node service **9 passed**、架构 **6 passed**、私有UI software测试 **3 files / 5 passed**、UI包typecheck通过、OpenAPI已重导出；assessment sidecar哈希与官方目录逐名覆盖校验通过。早期Node24.22 bundle仅作历史诊断；准确Node26.8.2根构建见B62预检。HTTP TestClient仍因Windows socketpair初始化未获通过证据；独立真实HTTP GET另返回200和199条唯一命令（见下）；真实网页、WebSocket、用户确认／下载安装未验；命令assessment尚未接入B56/B57 MCP。B31整体仍进行中，首操作／序列来源待用户选、图像质量门未过；B32／B33／B42/B43实际依赖仍未验。
- B31 wheel-only assessment smoke：wheel资源核验和repository-external uv --offline --no-config --no-deps --target安装均通过；从外部target导入包并读到199命令及pyscript高风险assessment。报告在`.artifacts/implementation/B31/assessment-wheel-external-20261028.json`。该中间wheel使用11:05旧web bundle，仅代表后端资源smoke；当前界面随B62 v6 package另行验证。
- 真实HTTP smoke：隔离workspace先经项目`upgrade_database`建立schema 0009，再启动实际APF/Uvicorn于127.0.0.1:32785并GET版本绑定命令目录；HTTP 200，返回199条且199个command唯一，`pyscript` assessment存在。API进程随后停止。证据、响应与服务日志在`.artifacts/implementation/B31/http-command-catalog-smoke-migrated-20261028/`；未启动或修改共享ComfyUI。早期未授权sandbox进程停在Windows Proactor socketpair阶段，不能替代本次HTTP结果或据此宣称产品代码故障。
- B31 sample-data preflight：`tests/data/Astro_Dataset`实有29份图像文件（18 FITS、11 XISF）；只读检查主图header确认其为Master Light，不存在可确认的同目标、同滤镜两成员原始序列。XISF附加图层不作为序列成员。逐项字段见`.artifacts/implementation/B31/astro-dataset-preflight-20261028.json`，此前XISF详细盘点见`.artifacts/implementation/B31/dataset-inventory.json`；序列运行仍待另有真实素材。
- B31 denoise命令已由真实CLI观察并从catalog的not_tested更正为partial：sidecar/manifest hash `1ECDE881…`，coverage counts 17 unique CLI / 182 unexecuted / 12 successful / 5 partial / 5 science-scope limits (explicit runtime_test.science_scope_limit fields or runtime status containing scope_limited) / 0 complete semantic or security audits；denoise headless已观察，序列与外部依赖保持unknown；Sol Low两轮审查分别修正node理由和一条不存在的证据路径，后续复核无剩余发现；scope count按coverage-matrix中明确predicate重算为5，五条为convert／denoise／findstar／jsonmetadata／seqstat。SOS1 CLI候选exit0但无SOS阶段日志且主像素与无SOS输出相同，效果／迭代范围未确认。software service定向测试 **9 passed**，日志`.artifacts/implementation/B31/denoise-assessment-service-tests-20261028.log`，逐项证据与counts在`coverage-matrix.json`。
- SOS2 trial: denoise -nocosmetic -sos=2 then Asinh 1000 on a copied mono Ha master. CLI exited 0 and saved/read back a finite file, but logs show SOS enabled with iters=2, then ensurepip failed to create Siril Python venv before iteration 1/2 was logged complete; no second iteration was observed. This is a partial execution, not a complete SOS result or valid image candidate. SOS parameter range remains unknown. Evidence .artifacts/implementation/B31/denoise-sos2-asinh1000-20261028/sos2-trial-comparison.json and process.log.
- GPT-6.1 Sol Low复核SOS1更新后的denoise sidecar/coverage：无具体发现，SHA一致、计数17/182/12/5/5、SOS1像素等同无SOS输出的表述准确，所有denoise evidence paths存在。仅复核文件，未重跑CLI/HTTP/packaging。报告 .artifacts/implementation/B31/image-review/sol-low-denoise-catalog-sos1-review-20261028.md.
- Updated-catalog HTTP smoke after the SOS1 assessment update: isolated schema-0009 APF GET returned 200, 199 unique commands, and the exact no-SOS-stage/pixel-identical denoise reason. Service stopped; no ComfyUI started. Evidence .artifacts/implementation/B31/http-command-catalog-smoke-denoise-20261028/http-smoke-result-sos.json.
- Updated-catalog real HTTP smoke: isolated APF schema-0009 app at 127.0.0.1:32786 returned 200 and 199 unique commands; the corrected denoise partial/headless/node status was present. The service stopped afterward; no ComfyUI runtime started. Evidence .artifacts/implementation/B31/http-command-catalog-smoke-denoise-20261028/http-smoke-result-r2.json. The first harness attempt failed before service startup because it recreated already-migrated directories; logs/failure evidence are retained.
- SOS2-updated catalog HTTP smoke: the corrected isolated schema-0009 APF GET at 127.0.0.1:32786 returned 200 and 199 unique commands; the denoise reason included the SOS=1 no-effect note and the SOS=2 logged-error/iteration ordering. The first assertion harness reached HTTP 200 but failed because it expected the spelling `-sos=1`; a retry hit an unavailable CIM listener query, and an unprivileged loopback retry could not bind/connect. With scoped loopback permission, the corrected harness passed and the API process was stopped. Evidence and retained attempts: `.artifacts/implementation/B31/http-command-catalog-smoke-denoise-20261028/http-smoke-result-sos2-order-r3.json`, `*-r2.json`, and `*-order.json`. No ComfyUI or normal dev workspace was started or modified.
- B32 G03传输候选：engine为当前ComfyUI socket建立page_id并生成连接token，`apf_page` feature flag开启后，原生API通过同一`/ws`发`apf.page`，engine只用实际socket身份转发到Bearer保护的`/internal/native/page`并回同页`apf.page_result`。浏览器不发送page_id/token，也无第二socket。确认等待工作台状态后，服务端在锁外读取当前包及节点计划；共享锁只保护页面token／当前operation复核和启动动作，包token及定义内容仍会由安装／定义替换入口在副作用前重核。workbench与proposal的网络／文件状态读取位于锁外。单元回归在同步提交边界模拟提案被替换，另断言workbench状态读取时锁未持有；这不替代真实协程交错或WebSocket并发验证。GPT-6.1 Sol Low对最新源码独立复核无剩余发现（源审查，未运行测试或真实并发）。前端`api.nativePage.test.ts` **2 passed**、SoftwarePanel **3 passed**、CommandDirectory **1 passed**、SoftwareClient **1 passed**、侧栏注册 **5 passed**、UI包与原生应用类型检查及整页生产构建通过。实际网页／WebSocket／用户点击和下载安装尚未运行。先前runtime预检记录已由`.artifacts/implementation/B32/runtime-preflight-correction.json`更正：在11:14时点，实际用户runtime `ComfyUI/.apf-native-build`存在，marker `ec74c9e9…`与当时旧candidate匹配且Python与ComfyUI主文件存在；此匹配不适用于当前`c6c7a476…`候选。受限进程的`LOCALAPPDATA`指向sandbox包目录。候选engine源已复制到`.artifacts/implementation/B32/runtime-overlay/localappdata`，但创建到已验证用户Python环境的目录联接被拒；不复制1.88GB venv，未初始化W1、未启动服务或修改共享runtime。详细事实见`overlay-preflight.json`。真实G03仍需一个能只读使用既有venv并运行候选engine的隔离环境，还需要用户操作确认，不记通过。
- 2026-10-28当前`demo`候选Python定向验证刷新：`.artifacts/venvs/dev/Scripts/python.exe -m pytest tests/modules/software/test_service.py -q` **9 passed**，`tests/modules/nodes/test_service.py -q` **9 passed**，`tests/architecture/test_import_boundaries.py -q` **6 passed**；每个文件在独立pytest进程运行。完整stdout、命令、退出码及前置启动尝试见`.artifacts/implementation/B31/test-refresh-20261028-1253/`。`uv run`因默认`.venv`失效及sandbox uv缓存写入拒绝未能启动pytest；三文件合并收集时因同名`test_service.py`模块冲突在collection阶段退出，未运行断言；独立直调dev解释器后通过。没有为此写入外部环境或依赖。
- 2026-10-28当前`demo`候选前端定向测试刷新：软件UI包 `tests/modules/software` **3 files, 5 passed**；`src/scripts/api.nativePage.test.ts` **1 file, 2 passed**。采用仓库固定Node 26.8.2直接运行已安装Vitest入口，并将TEMP／TMP／TMPDIR重定向到`.artifacts`，避免sandbox临时目录拒绝；native page测试另注入当前HEAD到`FRONTEND_COMMIT_HASH`以避免Vite内部Git调用。运行日志与失败尝试均保留于`.artifacts/implementation/B31/test-refresh-20261028-1253/`；无依赖安装或源码变更。
- 本轮发现并修复两个已提交的B22语法错误：`contracts/inputs.py` 的字段后缀和`modules/data/content.py` 函数行末都误含字面量`\\n`，令平台服务导入失败。修改只移除误入源码的两个字符序列；其他数据行为不变。
- `tests/interfaces/comfyui/test_proxy.py` 在本受限Windows环境的 `asyncio.run` 初始化阶段因 `socketpair` 等待而无法运行到断言；不记为通过。B31软件测试直接核对了该GET路径已进入固定代理白名单。
- `tests/integration/test_client_operations.py` 的软件命令客户端定向用例 **1 passed**，过滤掉既有异步MCP图像测试后 **12 passed, 1 deselected**。不带过滤参数的整文件运行无输出挂起超过100秒后被中断，未捕获栈；不能记为整文件通过，低层测试结果不覆盖该异步用例。
- B41本地`demo`候选通过，未集成dev：新增 `contracts/nodes.py` 与 `modules/nodes/public.py`，只保存workspace JSON，不发布HTTP／不推断引擎已加载。`tests/modules/nodes/test_service.py` **9 passed**，覆盖创建／读取、操作绑定、损坏文件明确失败、部分写入清理、稳定native type及content token、端口重排与变化断开、参数`0`／`null`默认、更新时token重核、软件包完整token与逐项非原子替换；与架构边界合跑 **15 passed**。GPT-6.1 Sol Low独立审查未发现剩余问题。真实registry加载仍待B42，M4用户Milestone验收待B42／B43同轮完成。
- 序列日志出现 Python 虚拟环境初始化失败，尽管序列统计成功；Siril随包Python环境未通过初始化。官方页面下载曾遇 DNS 失败，后经授权保存至隔离证据目录。正式安装、取消、实际节点加载、真实HTTP请求及MCP发现未完成；发布物没有可核对的上游校验和／签名，故来源未获密码学认证。只读接口及配套定义已实现但未由④加载；原型不代表G02或B31整体通过。

## 2026-10-28 G10 本地embedding资源预检（未选择／未运行）

- 本地依赖只读盘点：dev venv没有`sentence_transformers`、`transformers`、`onnxruntime`、`fastembed`、`tokenizers`或`torch`。已验证用户ComfyUI venv含`transformers 5.20.2`、`tokenizers 0.23.3`、`torch 2.14.1+cpu`、`safetensors 0.8.0`、`sentencepiece 0.2.2`、`huggingface_hub 2.3.0`和`numpy 2.5.2`；没有sentence-transformers／onnxruntime／fastembed。精确状态和未触及的缓存位置见`.artifacts/implementation/G10/model-preflight.json`；没有模型文件、下载或依赖变更。
- 官方模型卡候选只用于形成选择范围：[multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3) 标示94种语言、MIT；其471 MB safetensors文件散列、只读commit和查询/文档前缀要求见artifact。[paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2/tree/e8f8c211226b894fcb81acc59f3b34ba3efd5f42) 标示50种语言、Apache-2.0，384维、128 token；权重散列和commit同样见artifact。两者均未在本机benchmark，亦未选定。
- Sandbox不允许将既有ComfyUI Python环境联接到隔离overlay；复制该环境会违反仓库的固定runtime约定。因此现有CPU依赖虽已核实，G10真实资源加载、双语查询、检索质量和延迟尚未测试。G10保持未通过，待用户选择资源／后端和可运行隔离环境。

- 2026-10-28 13:03 UTC G03 runtime复核：明确将LOCALAPPDATA设为已核验的用户路径仅作只读preflight，发现当前ComfyUI archive与manifest hash `c6c7a476…`一致，但既有runtime `.apf-native-build`是`ec74c9e9…`，因此`--reuse-runtime`的marker前置不满足。正常init可能重写共享ComfyUI源码并调用依赖安装，故未尝试；W1不存在、dev stopped、无相关Python进程或监听器。完整路径、散列和限制见`.artifacts/implementation/B32/runtime-reuse-preflight-20261028-1303.json`。较早marker匹配只对旧候选成立。

- 2026-10-28 13:09 UTC sandbox auto-review拒绝临时替换共享用户runtime的`server.py`及`.apf-native-build` marker，原因是写入workspace外共享runtime且无对该精确改动的可信显式授权。拒绝后只读核对确认原文件／marker未变、dev stopped、无W1或相关进程。拒绝／备份证据见`.artifacts/implementation/B32/runtime-write-auto-review-rejection-20261028-1309.json`。未换通道绕过；G03等待用户对精确维护操作授权或提供匹配的隔离runtime。

- 2026-10-28 16:23 UTC G03当前候选只读复核：repo archive／manifest仍为c6c7a476…，用户runtime marker为ec74c9e9…且runtime server.py hash与archive内candidate不同；用户Python与ComfyUI主文件存在。marker不符时不初始化W1；未启动或修改runtime。逐项SHA见.artifacts/implementation/B32/runtime-marker-current-readonly-20261028-1623.json。

<a id="demo-b62-packaging-preflight"></a>
## 2026-10-28 发行资源包装预检（B62正式卡仍未Ready）

- 新增distribution verifier断言，wheel必须包含③／④模块及Siril 1.4.4命令目录、manifest和配套定义；安装后按manifest动态核catalog条目数量、重复和Scriptable计数，并调用打包后的只读catalog public。原`.artifacts/dist`、旧report和旧sdist重建wheel先复制保留在`.artifacts/implementation/B62/prior-artifacts-20261028/`。
- 首次打包遇到系统setuptools 72.1拒绝当前PEP 639 `project.license`字符串格式；本机PyPI DNS也不可用。依据[setuptools官方迁移说明](https://setuptools.pypa.io/en/stable/userguide/license_migration.html)（v77支持SPDX表达式与license-files），将build-system下限收紧为`setuptools>=77.0.3`；uv.lock中不锁build-system requirements，未改运行依赖。
- 使用已验证ComfyUI Python环境setuptools 78.1（`PYTHONDONTWRITEBYTECODE=1`，不安装／改写环境）和dev环境build 1.6.1工具，将当前源码／已有网页构建产物重建wheel与sdist至`.artifacts/implementation/B62/dist-final-v4-20261028/`。构建使用`--no-isolation`，没有下载build依赖或修改共享venv。
- `.artifacts/implementation/B62/packaging-report-final-v4-20261028.json`记录仓库外wheel安装smoke通过（report中repository_external_install=true）、Siril catalog hash／manifest与Node page identity资源校验通过，以及从sdist解压和重建均在仓库外临时根且PATH无Node时重建wheel（repository_external_sdist_rebuild=true）、安装和同一smoke通过；重建过程用预装setuptools 78.1解释器非隔离构建。该证据验证当前候选sdist可无Node重建，但不验证隔离build依赖自动下载。完整`build_release.py`前端锁定安装脚本未运行；独立Vite生产构建此前已通过。该预检用于提前检查B31/B41资源包装，不绕过M6依赖：B61未通过前，B62正式卡仍不Ready。候选不含未开发的B42白名单节点包，也不代表B62整卡或发行批准通过。
- 2026-10-28准确Node 26.8.2／pnpm 11.13.1根构建：`pnpm build` **exit 0**，Python UI／原生应用类型检查通过，Vite生产构建7111 modules通过，网页资源位于`.artifacts/build/frontend/`；`scripts/build_engine.py`产出的ComfyUI归档hash为`c6c7a476…`且与manifest一致。持久日志`.artifacts/implementation/B62/root-build-node26-20261028.log`。Vite有缺失CSS／图标解析及动态导入告警，但未阻止构建。
- 从该最终网页构建生成wheel/sdist至`.artifacts/implementation/B62/dist-final-v6-node26-20261028/`；wheel SHA-256 `e45d0d99cc98576d6bbf9fedd463d382d684a4525604ca88532e69ddc67cf24b`，sdist SHA-256 `22a6fa2b8dd0fd845649355a11e12b2ea9166f81e10eba5d6d7b5de9cf1eb2d4`。更新后的verify报告`.artifacts/implementation/B62/packaging-report-final-v6-node26-20261028.json`包含源码外wheel安装和sdist／重建wheel散列；wheel smoke通过，sdist解包/重建wheel在Node缺席时完成并重装smoke通过，重建wheel SHA-256 `fd1143847d7a8e058b32b0920e72d1a6d221a78c4d8521b476c27f691d6c9083`。构建使用预装setuptools 78.1、`sdist_build_isolated=false`；没有安装或更新共享Python环境依赖，临时路径都被重定向至授权目录。
- v5第一次verify因Python build helper尝试写入sandbox Windows Temp而失败；随后Temp重定向后v5安装／重建通过，但紧接着的根Node构建更新了4个hashed assets，verify正确拒绝旧wheel与当前frontend不一致。失败尝试分别保存在`.artifacts/implementation/B62/packaging-attempt-v5-temp-failure-20261028.json`及`.artifacts/implementation/B62/packaging-attempt-v5-r3-asset-mismatch-20261028.json`；以最终assets重建的v6整套检查通过。`build_release.py`固定写入原`.artifacts/dist`，为保护既有发行文件本轮保留唯一输出路径、运行等价的根构建和`python -m build`，未覆盖原dist。
- 更新denoise runtime assessment sidecar后，基于现有Node26网页构建重打包v7 wheel/sdist于`.artifacts/implementation/B62/dist-final-v7-denoise-20261028/`；verify报告`.artifacts/implementation/B62/packaging-report-final-v7-denoise-20261028.json`中仓库外安装与Node-free sdist重建／再安装均通过。sidecar及manifest hash为`9B3744F7…`，wheel `a6886932…`，sdist `eb3b8db7…`，rebuilt wheel `d9988776…`。此为B62预检，对B61与正式B62状态没有替代效力。
- 按Sol Low两项denoise目录修正后重建v8 wheel/sdist于`.artifacts/implementation/B62/dist-final-v8-denoise-review-20261028/`；报告`.artifacts/implementation/B62/packaging-report-final-v8-denoise-review-20261028.json`确认仓库外wheel安装与Node-free sdist重建／再安装通过。侧车／manifest SHA为`9B3744F7…`；wheel `8bab31cb…`，sdist `9827a11e…`，rebuilt wheel `7b9d3c79…`。`tests/modules/software/test_service.py`针对修正后DTO **9 passed**；denoise coverage evidence路径均存在且三个sidecar SHA一致。隔离build依赖下载仍未通过验证，v8也只是B62预检。
- 将最新文档与denoise目录修正一并打入v9 wheel/sdist：`.artifacts/implementation/B62/dist-final-v9-current-docs-20261028/`；报告`.artifacts/implementation/B62/packaging-report-final-v9-current-docs-20261028.json`确认仓库外安装与Node-free sdist重建／再安装通过。wheel SHA `aac538e354fe3146a0d9b674aeac6108a4676bcb52bc09736cc0da75636dae0d`，sdist SHA `9d78fd8a6a90d30b657957b0b8c002b2644918ec72b5689ee324918e3bc5fda0`，rebuilt wheel SHA `3684da3547cc224b109084ce4ff834b86628f4c5bf58dba96ca16c608fcb6b32`。隔离build依赖下载仍未通过验证，B61前置仍未完成，B62正式卡未Ready。
- 更新denoise SOS1 partial evidence并完成v10 wheel/sdist验证，产物 .artifacts/implementation/B62/dist-final-v10-sos-status-20261028/，报告 .artifacts/implementation/B62/packaging-report-final-v10-sos-status-20261028.json。sidecar／manifest hash 0C637F1A…；wheel 5eb16fa8…，sdist 39292362…，rebuilt wheel 6df8ff07…；外部安装和无Node sdist重建／重装通过，build仍非隔离，B61前置未过。
- 将SOS1运行限制与最后HTTP-smoke文档打入v11 wheel/sdist：.artifacts/implementation/B62/dist-final-v11-sos-http-docs-20261028/，报告 .artifacts/implementation/B62/packaging-report-final-v11-sos-http-docs-20261028.json。仓库外wheel安装和Node-free sdist重建／再安装均通过；wheel SHA aac538e354fe3146a0d9b674aeac6108a4676bcb52bc09736cc0da75636dae0d，sdist SHA e1b56f174b9bee01205d1f955441fc7966ba1b22b73b7099cdc0a17a5d1c44bc，rebuilt wheel SHA 08fb750c5b96f0a2458eaa8ac283ee22ebc4bd4d13f111bcbf322f2c93b1a2ee。build仍非隔离；B61未通过前不作B62完成声明。
- v12 repackage after the SOS1 no-op record and Sol Low review note: .artifacts/implementation/B62/dist-final-v12-sos-review-docs-20261028/; verification .artifacts/implementation/B62/packaging-report-final-v12-sos-review-docs-20261028.json. External wheel install and Node-free sdist rebuild/reinstall passed. Wheel SHA 6d2be3ad790906095116f95295863766265fda7adc021d1a40699c673f2a6ced; sdist SHA c9c04f27030be7b3a8cf72a5512d27e10a102f199ce27932d8485a49a023d6fd; rebuilt wheel SHA a4a8d7de0235a4cd4355e6ece71d19cf04a543525e3702c75dc2bb6bddca17f5. Build remains non-isolated; B61 still gates formal B62.
- v14 package rebuilt after correcting the SOS2 log-order description: .artifacts/implementation/B62/dist-final-v14-sos2-order-20261028/; report .artifacts/implementation/B62/packaging-report-final-v14-sos2-order-20261028.json. External wheel installation and Node-free sdist rebuild/reinstall passed. Wheel SHA edda320e09f9a3b08a6967f502f5800075a2dd055ee2db0444df9272d236472f; sdist SHA bef79387825b725282b78683f94ba3698f738a12b1bc92937068d002f35089aa; rebuilt wheel SHA 6d1168a57c59b07880a956c1dd1d8a5523912159df1a718799d6c4c69350227a. Build remains non-isolated and does not complete B61/B62.
- Current-docs v15 B62 preflight: the isolated `--installer uv` wheel/sdist build failed before building because DNS could not reach PyPI for `setuptools>=77.0.3` (log `.artifacts/implementation/B62/build-final-v15-sos2-http-docs-20261028.log`). A separately labeled `--no-isolation` package build using Python 3.12.4, preinstalled setuptools 78.1.0 and build 1.6.1 succeeded; repository-external wheel installation and Node-free sdist rebuild/reinstall passed. Report `.artifacts/implementation/B62/packaging-report-final-v15-no-isolation-http-docs-20261028.json`; wheel SHA `1dc1e5f37ed6ce53c8610325fb4cfaaf17baa827922ce2eceab88dce4f8a4a2b`, sdist SHA `39e481cf1390a86bb084f4d5ee4ff71da845b78bcf4403c0887a59605f27ab62`, rebuilt wheel SHA `3945aef3d994bee048ba749dbaf82b820e179d47354065bb62a64ecdff6e9863`. The sdist includes the then-current test-matrix/current-context byte-for-byte. This is a preflight only; isolated build and formal B61/B62 remain incomplete.
- Current-docs v16 B62 preflight: `python -m build --installer uv --wheel --sdist` completed its isolated build with setuptools 84.2.1. The verifier passed repository-external wheel installation and Node-free sdist rebuild/reinstall; the rebuild used the existing native Python/setuptools 78.1 environment without installing dependencies (`sdist_build_isolated=false`). Report `.artifacts/implementation/B62/packaging-report-final-v16-isolated-current-docs-20261028.json`; wheel SHA `034fdae6b917b4075db7d8b327e65c66c6943e62cec8d356de40cf315d308bb2`, sdist SHA `22c44a71ed1cc6cb1f8c4fce57a8e0f7b5b628f2508171c6f76ba0bf153380b2`, rebuilt wheel SHA `20152c5a863f337ca7f5cce3274d360487d70df4f60d856300273e67db818de1`. A read-only `app.openapi()` regeneration is semantically identical to the snapshot and equals it after normalizing CRLF to LF; evidence `.artifacts/implementation/B62/openapi-snapshot-v16-20261028.json`. The current test-matrix/current-context files matched the sdist byte-for-byte at build time; generated egg-info was restored to the saved snapshot. This remains a preflight because B61 is incomplete.
- Current-docs v17b B62 preflight after the GHT SP assessment update: isolated `python -m build --installer uv --wheel --sdist` succeeded with setuptools 84.2.1; the verifier passed repository-external wheel installation and Node-free sdist rebuild/reinstall. Report `.artifacts/implementation/B62/packaging-report-final-v17b-ght-sp-20261028.json`; wheel SHA `87a0d6888a29d6a9e08a8a4745b27ead58a236017a00991ca243bdf6f3bfdf38`, sdist SHA `17ea8aa303a30e0f6f4ddacea84636f1f43e6dc28ece1d2804c2806b05eaf98b`, rebuilt wheel SHA `bcc42ee7a12fff852e3cc53c5f089d67e97ce2d630d04ae81e44a897f48e6ee0`. v17 content verification confirms wheel sidecar equals current source and manifest digest, GHT assessment is present, and sdist docs were byte-identical at build time; source egg-info was restored. Verifier sdist rebuild used existing setuptools 78.1 with Node absent and `sdist_build_isolated=false`; main build was isolated. B61 remains incomplete, so this is a preflight, not formal B62. Evidence `.artifacts/implementation/B62/v17-content-verification-20261028.json`.
- Sol Low independent v17b packaging review: recalculated wheel/sdist/rebuilt-wheel hashes match, sidecar hash/manifest and content are correct, isolated build and non-isolated Node-free rebuild scopes are described accurately, and egg-info snapshot is restored. No findings; review did not rerun packaging/tests/runtime. Report `.artifacts/implementation/B62/sol-low-v17b-packaging-review-20261028.md`; B61 still gates B62.
- Current-docs v18 B62 preflight with final GHT SP/LP assessment: isolated `python -m build --installer uv --wheel --sdist` succeeded using setuptools 84.2.1; external wheel install and Node-free sdist rebuild/reinstall passed. Report `.artifacts/implementation/B62/packaging-report-final-v18-ght-sp-lp-20261028.json`; wheel SHA `1c0532f814098557cf05ab8b1c2f4866e9db6bb27121d6dd18d8785c2503f32a`, sdist SHA `38ed9145fb8a9c35f4d2523b06099502fc5989c58c48b1047b4501d12dfc9af9`, rebuilt wheel SHA `589150f1b3df1c456391c5b4e993fab3e7700fde38a4d4df8fffb7eed0b091fd`. v18 content verification confirms wheel sidecar equals current source and manifest digest, GHT SP/LP review is packaged, sdist docs matched at build time, and source egg-info was restored (`v18-content-verification-r2.json`). Sdist rebuild used existing setuptools 78.1 with Node absent and was non-isolated; main build was isolated. B61 still gates formal B62.
- Sol Low independent v18 packaging review: recalculated all wheel/sdist/rebuilt-wheel hashes and verified current packaged GHT sidecars/manifest digests, LP/SP review reason, isolated main build, external install, non-isolated Node-free rebuild scope, and restored egg-info. No artifact correctness findings; source/read-only review only, no reruns. Sdist/current docs differ only by subsequent v17b/v18 result notes and B62 status update. Report `.artifacts/implementation/B62/sol-low-v18-ght-sp-lp-review-20261028.md`. Formal B62 remains gated by B61.
- Current OpenAPI snapshot check: an in-memory `app.openapi()` generated using the exporter’s `create_app` path matches `docs/api/openapi.json` semantically and byte-for-byte after CRLF→LF normalization; raw bytes differ only by line endings. Report `.artifacts/implementation/B62/openapi-snapshot-v16-20261028.json`. This checks contract snapshot consistency, not external HTTP/client behavior.
- GPT-6.1 Sol Low independently reviewed the v16 build log, report, three artifacts, documentation and source egg-info snapshots; no concrete findings. Recalculated hashes match, isolation and non-isolated sdist rebuild scopes are represented accurately, and packaged docs match after excluding v16 result notes appended after the build. Review did not rerun build/tests/runtime and does not complete B62. Evidence `.artifacts/implementation/B62/sol-low-v16-packaging-review-20261028.md`.
- GPT-6.1 Sol Low独立复核`verify_distribution.py`的新sdist hash字段及v6报告，无具体正确性发现；其独立重算wheel／sdist／重建wheel三份SHA均与报告一致。review是源码／报告核对，未重跑安装、sdist或运行验证，不等于B62整卡独立审查。
- B62相关Python发行资源回归：`tests/packaging/test_layout.py tests/packaging/test_engine_build.py` **3 passed**；引擎写入均在tmp_path，未运行ComfyUI。完整build／外部verify证据单独见v6报告。

2026-10-28最终人工批准：用户在当前聊天确认“通过测试，可以将结果merge到dev，并删除目前这个branch”，授权M1整体交付dev。网页重启UUID校验及回执修复后，定向Python115项、表单6项、类型检查与生产构建通过；真实网页保存并应用导入3／预览6，地址新页跳转、输入／移除按钮36px且纵向偏移0，errors为空。见`.artifacts/implementation/M1/restart-browser.json`、`restart-python-final.xml`、`restart-build-final2.log`和`restart-build-final3.log`。用户要求修复后停止，网页重启最终独立审查中止，未记为通过；未追加业务回归。此前候选状态保留为历史，不替代本次用户批准。

2026-10-28 M1侧栏调整：配置入口改用原生SidebarTabTemplate，位于工作流后。定向配置表单4项及侧栏注册5项通过；私有包及原生应用类型检查、生产构建、定向ESLint通过。真实浏览器5类检查验证保存、冲突、重启生效、错误及收起后画布保留，截图已人工检查。证据见`.artifacts/implementation/M1/sidebar-update.md`及`.artifacts/implementation/B13/browser`。自动验证不代替用户M1批准。

## 2026-10-28 M2 数据与资产实现候选

候选分支：`feature/database_management`，从dev创建，已于`38edd952`快进合入dev。自动验证和独立审查通过，M2用户Milestone批准尚待完成；⑤运行、工作流影响与Agent结果选择仍等待B51／B53／B54／B57联调。

- 后端：`tests/modules/data` **261 passed**，保留一条既有SQLAlchemy互相依赖表排序警告。新增`test_science_inputs.py`覆盖可复现／仅引用、FITS HDU、固定组成员顺序、再次变化时拒绝旧确认、同素材新版本、未变化确认、缺失托管文件、完整结果登记／重复查询、other格式登记、预览失败原因及移除范围只读查询。OpenAPI与原生代理白名单专项 **2 passed**；新增两条素材内容观察／接纳HTTP路径使公共HTTP操作增至84。
- 前端：数据UI全量 **153 passed**，`@astrophotoflow/ui`类型检查通过。表单将一个像元尺寸写入既有x/y字段，并隐藏位深、赤道仪及配件录入；望远镜减焦／增距说明和滤镜可选带宽保留。新增确认请求断连后只读核对测试通过，不重发确认POST。
- 数据库schema保持0009，无新增ORM、迁移或依赖；现有58个数据MCP工具不变。结果登记复用AssetTask；输出登记和科学输入是②内部Python能力，没有新增外部工具或路由。界面与⑤工作流/运行的真实端到端验收尚未进行。

自动验证证据位于`.artifacts/implementation/feature-database-management/M2/`。GPT-6 Luna High未发现具体UI风格或交互缺陷；GPT-6.1 Sol Low复核通过②候选。未运行完整原生应用浏览器验收、生产构建、运行期跨模块保护或真实Agent客户端操作。

<a id="m1-foundation"></a>

## 2026-10-28 M1公共基础实施候选复核

**技术复核通过，待用户人工验收**：此前第三轮发现启动失败清理绕过排空，用户明确确认复用stop及原验收后开启新迭代。现已修复普通失败清理、待登记进程持久化与身份恢复、控制结果写入失败遮盖原错误。新迭代第三轮无剩余阻断，报告`iteration2-round3-review.md`核对了冻结文件及实际测试。旧`review-round3.md`和缺陷probe保留，不将旧轮次失败改写成通过；当前仍不记I(Bxx)或A(M1)。

候选分支`codex/workbench-settings-ui`继承B11与B12中间提交，最新候选和文件指纹登记在`.artifacts/implementation/M1/delivery-report.md`及`iteration2-round3-candidate.json`。本节记录技术验证；独立复核及用户人工批准分别登记，尚未合入dev，不记I(Bxx)或A(M1)。旧B11／规划阶段证据保留原候选范围。

- B11／B12／B13实现：默认workspace、配置保存／冲突及实际采用值；结构化启停／重启、双服务身份和健康、自动端口及安全回写、最近控制结果；导入／预览与原生受理维护屏障；网页配置与同一公共HTTP实现。80项公共HTTP／代理、58项原MCP数据工具；没有新增数据库模型、迁移、依赖、队列或常驻服务。
- 最新全量Python：**336 passed，2 skipped**，149.45秒；两项显式真实进程测试另行执行 **2 passed**，51.57秒。原生用例覆盖W2在线、W1占优先端口自动换址／回写／复用、繁忙拒绝、显式重启采用、两个实例停止，以及/prompt和/api/prompt真实409门禁。新增真实领域子进程测试在导入running时模拟引擎启动失败，核对导入completed、产出资产及进程exit 0后才清记录；最终严格断言另行 **1 passed**。证据：`delivery-python.xml`、`delivery-native.xml`、`real-drain-final.xml`。保留一条既有SQLAlchemy互相引用表排序警告。
- UI完整回归 **148 passed**，类型检查和生产构建通过；依赖边界0 error、9条既有data组件循环warning，未扩改旧组件。此为既有M1构建证据，本次仅修改Python生命周期及测试，前端源码与依赖未变。构建日志在`.artifacts/implementation/B13/build.log`。本轮Figma连接不可用，沿用现有主题；已检查真实截图，不声称通过Figma专项审计。
- 浏览器在真实隔离网页验证保存不重启、采用值不变、双页面409且输入保留、真实CLI重启后生效、无效主机422及画布保留。最终回执／截图在`.artifacts/implementation/B13/browser`；首轮实际发现并修正小地图遮挡入口，另修正测试选择器未限定配置表单的问题，不使用强制点击绕过。
- 独立审查轮次与裁决在`review-round2.md`、`iteration2-round1.md`、`iteration2-round2.md`及`iteration2-round3-review.md`中。已修复中断后无法显式停止、停止后沿用旧地址、部分服务绕排空、维护回执丢失留下准入及原生入队穿过维护；本次进一步关闭启动失败与未登记子进程的清理缺口。控制文件只保留当前／最近结果及必要的待核对启动信息，没有新增历史账本或服务。
- 首次全量Python有一次WinError 5失败；已用打开的读句柄复现，并补有限等待／日志及持续失败保留原文件的回归。保留`python-tests.log`原失败，不把重跑当作原次通过。受限环境的socket／临时目录问题和缺失默认Playwright浏览器单独记录；正常环境复跑使用已安装Chromium，未安装／升级依赖。
- 新迭代中保留了测试数据库初始化影响后续日志捕获、代理用例一次503的失败记录；测试初始化现已隔离日志配置，相关用例与最终完整集均通过。原失败见`new-iteration-affected.xml`、`new-iteration-full.xml`，不将其记为通过。恢复后的原dev经当前HTTP客户端及真实MCP stdio只读验证，58工具保持，证据`delivery-mcp.json`。
- 按维护窗口保留原可运行源码和固定runtime后，停止原dev做真实验证；已用原版本恢复31388／31390，业务表行数、原配置／默认定位／令牌与引擎散列保持。补充实际恢复启动的采用记录，使当前数据客户端可读原dev；旧dev页面不作为M1候选页面。W2验后停止，W1仅为人工验收保留，用户结束后再停止，不以原dev数据测试写入。
- 未执行仓库外wheel／sdist重建（B62）、Linux／WSL或③⑤占用；MCP真实控制在B57。M1技术通过不能代签用户批准、S6维护或首个科学处理闭环。

<a id="b11-implementation"></a>

## 2026-10-27 M1 B11配置基础实现

设计基线dev `9d4c729`已正常同步origin/dev；实现候选为`codex/workbench-config`相对该基线的本次增量，最终提交／文件指纹见`.artifacts/implementation/B11/report.md`。本节只记录B11，不记I(B11)、M1用户批准或B12真实原型通过。

- 配置定位、初始化默认TOML、ConfigValues／ConfigSave／ConfigState、三项配置函数、显式Settings.workspace已实现；复用原有字段校验、filelock和Pydantic，不加依赖、HTTP／MCP入口、配置历史或业务模型。
- Windows／Python 3.12.4既有锁定dev环境：配置／工作台、架构、原生代理、打包资源及卡内9份数据／集成测试合计 **242 passed**，91.36秒；保留1条既有SQLAlchemy互相引用表排序警告。实际命令、JUnit与环境版本分别见`report.md`、`verified-tests.xml`、`environment.json`。
- 受限环境中两组回归卡在Windows asyncio.socketpair；最小FastAPI TestClient用faulthandler确认同一环境故障，原组已终止且未计通过。获准在正常本机环境重跑同范围并通过；没有修改运行库或测试框架来绕过问题。
- 未参与实现者独立审查发现“启动采用值读取错误要求进程非空”，已修复并补测试；复核无剩余阻塞。独立配置／工作台／架构30 passed及原子写失败保留原文件证据见`review.md`；不把受限环境未结束的代理运行当通过。
- 21处直接Settings构造及发行内嵌smoke静态核对通过；发行脚本未执行仓库外重装，完整发行验收归B62。OpenAPI、锁文件、schema0009、MCP／Skill及正常dev配置／令牌均未改，未启停服务。
- A11-1／2的配置行为已验证；A11-3仅提供配置基础，自动端口实际回写由B12/G01验收。B12采用记录写入与客户端连接接入、B13网页配置均未实施，不以模拟采用记录代签真实重启。

## 2026-10-27 第⑤阶段计划联合审查与任务卡

候选为dev `75aab88714095d77f2d576c14712a31c2b987bf6`上的本轮文档增量，非业务实现。[总计划](implementation-plan.md)保留M1～M6、22 Batch／建议分支、79项验收、G01～G10及V01～V18；六份任务卡把需求／数据／接口映射到准确文件、关键函数、实施顺序、测试输入／命令／预期及人工操作。

- 使用Context Researcher、Software Architect、Senior Developer、QA Engineer、Git／DevOps Reviewer并行审查，由Document Editor装配，Independent Verifier另行逐卡复验。审查报告、基线、静态检查和独立结论进入`.artifacts/implementation-plan-review`，最终状态以该候选报告为准。
- 用户确认五项取舍，见[ADR-0061](../../frontend/docs/adr/WORKBENCH-PLAN-0061-executable-batches-and-shared-client.md)。原④契约只补真实调用缺口及冲突，未另建协议体系；计划区分Batch技术集成与用户Milestone批准，不把尚未锁定的首包／模型或未过原型写成Ready。
- 本轮仅执行文档及静态源码检查，没有创建业务源文件／测试实现／实际分支、执行迁移或修改schema0009；未运行构建、原型、业务回归、软件／MCP客户端操作、工作台启停或环境维护，未提交推送。当前OpenAPI、锁文件、MCP／Skill及原有脏改动保持。
- 第④阶段下列散列与结论对应其当时历史候选；本轮补文后的新契约与任务卡由本轮报告独立记录，不能把旧散列冒充当前文档。所有业务验收及M1～M6用户批准仍待实际实施。
- 全仓前端ADR脚本实际返回1：历史ADR两处、既有工作流前端README两处短号引用不合现行命名规则，均与本轮开始时内容／散列相同，按范围保留；未当作检查通过。ADR目录命名与元数据单独执行通过；具体失败和范围证据见`.artifacts/implementation-plan-review/adr-check.json`，不以此扩改历史文档。

## 2026-10-27 第⑤阶段近期实施计划编制

候选为dev当前文档工作区。[近期计划](implementation-plan.md)对接现行接口与文件级详细设计，按M1～M6列出22个建议分支、分项验收及V01～V18责任；M2完成②自身近期范围，跨模块项分别由B53／B54／B55／B57联调，最终在M6验收。

- 本轮只检查计划结构、分支依赖、验收编号、接口断言覆盖、本地链接／锚点和Git增量；报告进入`.artifacts/implementation-plan`。检查结果以报告为准，不把计划中的测试名称视为已经执行。
- 所有建议分支、新增原型和功能验收均未实施；首软件准确版本／操作、实际素材和本地检索模型仍按计划门槛确认。保留第④阶段独立证据及下列历史状态，不将当时“近期计划尚未开展”解释为当前状态。
- 未创建实际分支，未修改代码、OpenAPI、依赖、环境、MCP／Skill或业务数据，未运行构建／业务回归、启停工作台、提交或推送。完整产品S6范围继续保留。

## 2026-10-27 第④阶段接口与文件级详细设计

候选为dev当前文档工作区，非新增功能实现。主文[接口与文件级详细设计](../api/platform-contracts.md)通过Context Researcher、Software Architect、Senior Developer、QA Engineer、Document Editor及Independent Verifier复核；报告与本轮增量在`.artifacts/fourth-stage-design`。独立候选主文SHA-256为`1c59ace39a76603e91e261f655444e2dc6b6a3f474c7f4dc7082354c29815738`，R1–R8/I1–I7已逐项关闭。

- 验证范围：五模块文件职责、公开签名及类型、调用/异常/副作用、数据一致性、原生复用、具体测试文件和FR/NFR/AT追踪；已有/拟新增/待原型/后续目标分开。
- 文档静态检查：Python签名块可解析、类型引用闭合、表格/JSON/本地链接锚点、当前78个HTTP/代理/OpenAPI集合及58数据工具迁移映射、既存ADR和本轮Git范围。具体数量与最终文件散列以报告checks.json为准。
- 本轮没有创建ORM/DDL/迁移/接口/类型/组件/测试实现，没有运行构建或业务回归，未操作正常工作台、软件安装、MCP/Skill/环境/业务数据，未提交或推送。原有未提交内容与历史证据保留，不校验不存在的旧需求冻结清单。
- 通过仅指第④阶段文档设计；首软件准确版本/操作、可靠UI来源、真实装载/目标转换/科学缓存/停止/预览及客户端行为仍需原型。第⑤阶段近期实施计划尚未开展。

自动化回归、真实运行和完整产品验收分别记录。子功能通过不表示对应 FR 或全部 AT 已完成；历史结果不替代当前候选验证。需求及验收条件以[现行产品基线](../requirements/README.md#9-验收场景)为准。

2026-10-27 的五模块概要和数据设计属于文档与静态源码检查；新增软件安装、画布桥接、运行和预览能力尚未因此实现或验收。个人偏好历史的恢复和删除仍需后续验证。

## 2026-10-27 现行文档清理检查

按用户要求删除过时需求包和旧设计正文，保留当前产品规则、验收场景及历史业务测试证据。过时的模块文档目录和决策记录已删除，业务规则统一维护在现行方案中。

检查范围包括相关文档的本地链接与锚点、FR／AT编号、过时模块和需求包引用、ADR格式及Git差异；结果记录在 `.artifacts/document-cleanup/report.json`。本轮没有运行构建、业务回归或服务操作，新增能力仍待实现和验收。

## 2026-10-27 接口契约静态检查

[五模块接口契约](../api/platform-contracts.md)覆盖①本机控制、②科学数据／所选结果、③软件包、④可编辑节点及⑤原生画布／运行／MCP交接；局部改图、保存成功后运行、网页按钮绑定目标已按用户选择同步需求。新增路径和工具名均为未来设计，尚未实现或运行验收。

本轮逐项核对领域路由、OpenAPI和同源代理的78个操作，以及58个MCP工具的迁移覆盖；检查任务增量链接、锚点、ADR格式、Git范围及保留文件散列。报告见[接口设计检查](../../.artifacts/interface-design/report.md)，详细清单见 `.artifacts/interface-design/checks.json` 和 `inventory.json`。未运行构建、业务回归、原型或服务，未修改OpenAPI、当前MCP或Skill。历史需求包在任务开始前已删除，本轮不恢复，也不声称通过不存在的冻结清单校验。

## 当前行为与验证入口

| 需求范围 | 已有行为及边界 | 验证入口 |
|---|---|---|
| FR-01 项目 | 资料、回收站、资产与集合固定引用；项目托管工作流未实现 | `tests/modules/data/test_service.py`；UI Workspace／Settings |
| FR-02 工作流目标 | ⑤复用唯一原生当前图、自动保存、本地草稿和会话撤销，项目关联／另存和在线桥接待实现；无永久逐编辑历史 | 按[⑤概要](../../src/astrophotoflow/modules/workflows/README.md#verification)、AT-06～11验证保存重开、另存、活动目标及断连，不以原生测试代替新增业务 |
| FR-09 运行目标 | ⑤记录当次图／输入／参数及原生任务关联，两类输入保证、真实调用／停止核对和所选结果保存待实现；复用ComfyUI队列 | 按[⑤阶段](../../src/astrophotoflow/modules/workflows/README.md#phases)、AT-14～18／28／29补真实软件及运行证据 |
| FR-03/13 软件包 | ③软件专用副本及配套节点、安装版本位置和可用状态仍待实现；Agent只连接平台MCP | 按[③概要](../../src/astrophotoflow/modules/software/README.md#phases)、AT-02／03／25／33验证安装、许可引导、节点发现及确认更新 |
| FR-04 导入 | 登记与托管分离、并发、Header 分类、预设快照、编辑与排序 | `tests/modules/data/test_import_pipeline.py`、`test_ingestion.py`、`test_library_sort.py`、`tests/integration/test_import_presets.py`；UI 导入／任务测试 |
| FR-04/11 删除 | 确认范围、部分清理、固定身份、共享路径与外部原件保护 | `tests/modules/data/test_service.py`、`test_calibration.py`；UI LibraryTrashDialog |
| FR-05 预览 | 100 px 缩略图、1080 px 大图、单图自动拉伸与 RGB 白平衡；完整比较未实现 | `tests/modules/data/test_auto_stretch.py`、`test_fits_preview.py`、`test_display_previews.py`、`test_video_preview.py`；UI PhotoPreviewDialog |
| 设备与预设 | 接受时冻结快照、删除后恢复／重试、历史名称和草稿保护 | `tests/modules/data/test_equipment_snapshots.py`、`test_setups.py`；UI SettingsOrganization／Workspace |
| 校准引用 | 默认、继承／null／覆盖、跨组隔离、历史清理保护；不执行校准 | `tests/modules/data/test_calibration.py`、`test_domain_foundation.py`；UI CalibrationLibrary |
| FR-07 数据 MCP | 58 工具与 CLI 共用服务；图编辑和软件运行工具未实现 | `tests/integration/test_client_operations.py`、`test_cli_mcp_protocol.py` |
| FR-07 统一检索目标 | ⑤派生目录、Skill直达、按需混合Top10及明确关键词降级待实现，当前58数据工具保持 | 按[⑤阶段](../../src/astrophotoflow/modules/workflows/README.md#phases)、AT-33／34验证精简MCP整体迁移、Skill及真实客户端，不遗漏已有数据业务 |
| FR-08 并发 | 数据revision已有；⑤活动目标核对、简单当前控制、手改接管／明确交回及在线结果返回尚未实现 | 按AT-07～10／24验证旧写拒绝、切图暂停、不抢视图、已有运行继续；A后台完成预览归A，不串B |
| FR-10/11 来源与恢复 | 数据固定版本及既有保护保留；⑤当次运行内容、多次自动图像预览、另存方案、所选完整结果和S6显式固定结果续跑待实现 | 按[⑤概要](../../src/astrophotoflow/modules/workflows/README.md#phases)、AT-06／09／18／20／21补证据；预览不代表完整文件仍在，核对／补登记不重跑 |
| FR-12 本地上下文 | 偏好、项目背景、工作流经验与交接摘要均待实施；个人偏好历史可查看／恢复为当前，删除包括历史正文；不包含完整聊天或模型会话 | 后续按 AT-22、AT-30、AT-31 验证，暂无完成证据 |
| FR-16 节点制作 | ④设计已收敛为workspace可编辑节点库、可选测试、最近测试查询及确认更新，均待实现；Python／复合S6，导出另行规划 | 按[④概要](../../src/astrophotoflow/modules/nodes/README.md#phases)、AT-03／29验证参数重置、变化端口、加载及执行中保护，暂无产品节点测试命令 |
| FR-13/15 交付 | 固定引擎、现有init/start/status/stop、完整网页、源码外安装和无Node重建；MCP启动、端口冲突自动选择及实际地址交接、网页公共配置、CLI／MCP重启、日志轮转与确认清理待补 | `tests/core`、`tests/packaging`、`scripts/verify_distribution.py`；新增验收见[公共概要](../../src/astrophotoflow/core/README.md#verification) |
| FR-14 服务边界 | 认证、代理来源／路径、原件和共享文件保护 | `tests/interfaces/comfyui/test_proxy.py`；数据服务／导入回归 |
| FR-15 契约 | OpenAPI、Pydantic、前端 Zod 与 MCP 结构 | OpenAPI 快照、UI 契约和真实 stdio 测试 |

前端 API JSON fixture 是模拟数据，不是整批真实照片的端到端验收。浏览器写入验收使用隔离服务和合成 PNG，覆盖原生侧栏、未保存保护、画布／视口、保存加载、真实 CPU 执行、上传、自动预览、回收站恢复及刷新。

## 保留的历史证据

| 日期与候选 | 当时验证结果 | 本机证据与范围 |
|---|---|---|
| 2026-10-25，原生侧栏 `c11745a` | UI 144、原生侧栏／画布 21、浏览器 5 组；类型及构建通过 | `.artifacts/redesign/sidebar-frontend.xml`、`sidebar-native-tests.log`、`sidebar-browser.log`；Windows／CPU、合成素材 |
| 2026-10-25，源码迁移阶段 `c11745a` 至 `16025dd` | Python 286 passed／1 skipped，另 1 项引擎构建回归通过；UI 144、原生 21、浏览器 5 组；OpenAPI 与 58 工具结构一致，发行验证通过 | `.artifacts/restructure/python-isolated.xml`、`engine-build-test.log`、`boundaries.log`、`browser-final.log`；218 个数据实现行为 AST 核对保持 |
| 2026-10-26，切换前 `16025dd` 加 URL 调整 | Python 287 passed／1 skipped，UI 144、侧栏 8；构建及发行通过 | `.artifacts/rename/*-before-move.log`、`python-before-move.xml`；仅证明切换前候选 |

旧阶段过程可从 Git 历史查询；本机日志与环境不随源码分发。历史独立复查和运行验收不表述为本轮新做的代码审查。

## 2026-10-26 改名收尾验收

日期：2026-10-26。基线 `16025dd`，候选包含文档清理和仓库 URL 调整。Windows／Python 3.12／CPU、Node 26.8.2、pnpm 11.13.1，依赖锁文件保持。

| 检查 | 本轮结果 | 证据 |
|---|---|---|
| dev 环境与路径 | 锁定重装、包定位、apf／apf-service 和固定工具版本通过；只更新 AstroPhotoFlow 的 MCP 注册内容，其他配置保持 | `.artifacts/docs-update/uv-sync.log`、`path-repair.json` |
| Python 全量 | 288 passed，无 skipped；FFmpeg 首帧用例实际执行通过。保留 1 条 SQLAlchemy 外键环警告 | `.artifacts/docs-update/python.xml` |
| 启动回执修复 | 实际启动仍打印旧 `#/library`；新增回归断言先复现，再将回执修正为 `#/workflows`。修复后工作台 5 项通过 | `start-url-before-fix.log`、`workbench.xml`，均位于 `.artifacts/docs-update` |
| 自研 UI | 19 个文件、144 passed | `.artifacts/docs-update/ui.log` |
| 原生侧栏与画布 | 5 个文件、25 passed；旧上游侧栏预期对齐已确认的节点库／素材库／工作流顺序，保留任务历史开关与菜单断言；定向格式和 ESLint 通过 | `.artifacts/docs-update/native.log`、`test-format.log`、`test-eslint.log` |
| 依赖边界 | Python 5 项通过；前端 0 errors、保留 9 条组件循环依赖警告 | `.artifacts/docs-update/boundaries.log` |
| 类型与生产构建 | 私有 UI 和原生应用类型检查、完整网页构建通过 | `.artifacts/docs-update/build.log` |
| 隔离浏览器 | 32588／32590、合成 PNG、5 组通过，含真实 CPU 执行、保存加载、上传与自动预览、回收站恢复 | `.artifacts/docs-update/browser.log`、`.artifacts/reports/native-web/results.json` |
| 网页／CLI／HTTP／MCP | 同库查询一致，真实注册命令启动 stdio 后发现 58 工具；1149 个网页文件与构建一致且不含领域令牌 | `.artifacts/docs-update/dev-before-restart.json`、`dev-after-restart.json` |
| 停止与重启 | 两套实例端口释放、重启后身份保持；dev 最终 running、隔离实例 stopped，默认 workspace 不变 | `.artifacts/docs-update/lifecycle.json` |
| 数据保持 | 118 个非数据库文件的大小／mtime／SHA-256 保持；SQLite 主文件字节变化，但 17 张表的行级摘要与改名前一致，外键有效；无新增数据库备份 | `.artifacts/docs-update/data-preservation.json` |
| 文档与链接 | 当时的文档整理、本地链接、锚点与删除引用检查通过 | `.artifacts/docs-update/docs-check.json` |
| 发行与安装 | wheel 源码目录外安装、无 Node 的 sdist 重建及再安装通过；完整网页、迁移、入口和源码包范围检查通过 | `.artifacts/docs-update/distribution.log`、`.artifacts/reports/packaging.json` |

上述全量 Python 在启动回执修复前运行；该修复之后运行了对应工作台回归与真实启动／重启。

受限进程首次运行 UI 时出现跨进程临时目录 ENOENT；正常用户环境重跑后全部通过，未为该环境故障修改产品逻辑。早期失败和最终日志均保留在本轮目录。

浏览器脚本在隔离用户配置中显式设置 `Comfy.TutorialCompleted`，沿用上游首次引导；这 5 组检查不代表首次引导已重新设计或单独验收。运行核对使用 HTTP／CLI／MCP；数据库容器变化的诊断沿用维护脚本的只读 SQLite 快照比对，不构成新的业务访问路径。

## 仍需后续验收

- FR-02、FR-03、FR-07～FR-12、FR-16及其他有效FR的未完成部分，按[现行需求](../requirements/README.md)与[当前路线](platform-roadmap.md)推进；使用现行AT及覆盖解释，旧需求包已删除，不对不存在的冻结清单宣称散列校验通过。
- S0 固定性能基准机器、数据规模与测量指标，相关功能可测后补齐数值门槛。标准节点热发布须有单独原型证据，不由现有定义刷新入口推定支持。
- ①的默认／自选目录、待应用配置及旧连接保持、并发控制／繁忙拒绝／重启核对、原生领域状态桥接、日志轮转／确认清理和完整升级恢复，按公共概要及其阶段表补实际证据；不能以本次文档覆盖代替功能通过。
- ②的固定科学输入、用户选择结果保存、比较、标签／文件治理及本地记忆，按数据概要DATA-F01～F08和阶段出口补实际证据；完整中间文件不作为长期保存内容，现有58个数据工具和数据回收站测试不代替新增闭环验收。
- ③软件包安装、配套节点发现、未就绪提示、确认更新、科学交接及卸载按现行③概要验收；⑤联合全部业务工具的混合检索、最多10候选、定义按需读和模型故障显式降级须有AT-34及真实MCP证据。具体模型与桥接均待原型，不把外部项目源码当作本平台支持。
- ④按NODE-F01～F08补workspace节点保存及跨项目使用、可选真实测试及最近结果、修改后旧测试提示、影响确认、参数默认值、端口增删改及重排、加载失败和执行中保护的证据。S6 Python及复合局部副本分别验证；不恢复项目草稿、测试门禁或旧版并存要求，导出安装仍后续规划。
- ⑤编排与在线交互按⑤概要验收：项目关联及唯一原生当前图、自动保存／另存／重开、本地草稿和会话撤销、缺依赖JSON、目标与控制检查；手动接管／明确交回、切图暂停、断连核对和真实MCP。取消永久逐编辑修订、服务端草稿、独立转换及永久画布回执要求，原生基础不代替新增桥接证据。
- ⑤执行与结果按⑤概要验收：可选真实测试及整图／受支持目标、两类输入保证、实际提交核对、运行内容／缓存、取消与实际停止、完整重跑及S6已保存固定结果续跑。各实际执行图像节点自动预览，保留多次并按任务归原图；只有用户选择完整结果才交②保存，未请求保存不构成登记失败。
- ⑤业务场景继续覆盖整夜／叠加起点、Skill直达／按需分型检索、精简MCP整体迁移、外部Agent调参及更换客户端接续；原生按钮、快捷键、自动队列和MCP托管运行统一提交且保留实际事实。未来Judge仅概念边界，数据工具、元数据字段和Skill不作完整场景通过证据。
- Linux 尚无本轮运行证据。视频用例在 FFmpeg 不可用的平台仍需单列为 skipped，不能计作通过。
- 用户最终业务体验验收与自动化回归分开。设置、设备快照和校准引用等有效场景见功能文档；旧页面、旧照片数量和退役入口不再作为条件。


<a id="equipment-management-optimization"></a>
## 设备管理优化候选（2026-10-28）

候选为 `codex/m2-ui-acceptance` 未提交内容。仅设备管理呈现及直接删除交接变化，不移除项目数据或公开项目能力；不代签M2用户验收。

- 数据UI：22文件／166测试通过，涵盖五类设备就地登记、跨组合复用、取消保留设备、失败输入与草稿保护、旧组合内设备编辑、批量预设选择、删除取消及冲突后显式刷新。
- Python定向检查：67通过／60未选，涵盖设备直接删除、组合／预设清理、过期依赖拒绝、原件与素材版本快照、排队上传／本地导入快照、架构边界、代理、客户端及OpenAPI。额外客户端回归中的软件命令目录测试因缺少assessment失败，任务开始时的测试副本也可复现；定向检查明确排除此既存失败，日志和基线记录均保留。
- 原生类型检查及生产构建通过；依赖检查0错误／9个既有循环警告。demo-preview已更新并就绪于32688／32690。浏览器实测五类设备登记、两套组合复用同一相机、Gain 0预设、删除影响及取消；确认删除与冲突执行由隔离HTTP测试覆盖。截图及公共接口回执在同目录最终交付报告中。旧项目组件回归通过组件公开入口检查，不恢复设备管理中的项目导航；M2用户批准仍待完成。


<a id="equipment-compact"></a>
## 设备管理紧凑布局候选（2026-10-28）

当前分支codex/m2-ui-acceptance未提交改动。设备管理使用限宽原生Dialog、五行搜索多选及同窗设备表单；业务保存、删除和历史快照规则保持。

- 测试代码：更新既有设备管理／组合用例，新增同窗草稿返回、多选保留顺序、旧组合内设备像元尺寸保留，以及宿主弹窗焦点／Escape与保存期间关闭保护用例。新增用例未执行，按用户最新要求不再运行测试。
- 编译交付：前端build包含原生类型编译；最终编译结果及隔离网页资源更新记录进入 `.artifacts/implementation/equipment-compact-20261028/`。
- 浏览器预览及最终验收交由用户自行完成；本轮早期截图和166项测试记录仅属于较早候选，不作为最终候选通过证明。不再由Agent操作浏览器、补充截图或执行验收场景。
- 待用户查看：1280×720常见组合能看到五类选择及保存按钮；长名称、多选和窄窗口不撑宽；设备参数较长时仅正文滚动；返回草稿、Gain 0、逐项保存及删除确认保持原有行为。
