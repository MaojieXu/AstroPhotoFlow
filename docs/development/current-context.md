# 当前开发上下文

## 2026-10-29 AstroPhotoFlow 设置精简本地候选

`codex/comfyui-ui-cleanup`按用户批准方案收敛本地设置：工作台置顶并默认打开，Comfy／LiteGraph改为常规／画布，隐藏遮罩、扩展及无关设置，快捷键过滤对应入口。Nodes 2.0在原生设置注册时将旧关闭值归一为启用，右侧属性面板不再提供开关；上游通知关闭。已保存图默认延迟自动保存，明确关闭值保留；未更改浮点舍入逻辑，高级精度与性能设置以及工作台目录／端口折叠展示。新增AstroPhotoFlow关于页，版本来自构建时读取pyproject.toml，组件和诊断折叠，系统信息支持长路径换行。

最终相关原生测试7文件136项、UI包工作台12项通过；定向Oxlint、前端类型检查及生产构建通过。已定向停止／同步／启动35388／35390独立实例。证据位于`.artifacts/verification/settings-cleanup-20261029/`。本轮浏览器控制接口报不可用；原页面有未保存工作流，刷新被自动审批拒绝，保留原页并已排队打开独立查看页。新版设置的实际视觉尚未验证，不将构建和测试写成视觉验收。未提交、推送或合入dev。

## 2026-10-29 主菜单精简本地候选

`codex/comfyui-ui-cleanup` 基于 `origin/dev` 的 `366a311`，按用户页面标注隐藏本地主菜单的 Nodes 2.0 开关、浏览模板、管理扩展功能和帮助，原四项功能区只保留设置。新建／文件／编辑／视图／主题及底层功能保持；Nodes 2.0 对未显式设置的本地安装默认启用，覆盖安装版本默认值解析，保留已有明确设置。云版／桌面版维持原菜单和默认策略。

菜单和设置 Store 两个文件共61项回归通过，参数化写法按仓库规范调整后设置Store的55项复跑通过；四个受影响文件的Oxlint及前端类型检查／生产构建通过。已定向更新独立workspace并启动35388／35390，浏览器刷新后主菜单只显示新建／文件／编辑／视图／主题／设置；设置窗口能打开且Nodes 2.0显示启用，当前工作流graph标识保留。日志和截图位于 `.artifacts/verification/menu-cleanup-20261029/`，详见验证矩阵。本条为当前分支本地候选，不表示已提交、推送或合入dev。

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

## 2026-10-29 Siril Bundle 候选

工作分支 codex/siril-bundle，基线 dev 366a3112，主项目未提交/合并。独立私有仓库 https://github.com/MaojieXu/AstroPhotoFlow-Siril 已发布 v0.1.0，commit d6be7dd341772d3be5a47849db92f2825ea1e92f；普通 Git 携带完整便携程序，软件版本1.4.4。独立本地 checkout 为 .artifacts/bundles/AstroPhotoFlow-Siril，不纳入主项目版本控制。

已接入固定 Git 安装、参数目录、通用 V3 类、通用预览元数据、CLI/MCP 四个目录/画布工具；节点 UUID/native_type 保持。安装完成后受控空闲重启，真实程序和原生加载观察通过才绿色。原有199命令资料为只读缓存，只有 Auto Stretch 是可执行节点。旧 Siril 预览 HTTP 保留适配。

隔离 bundle-smoke 已实际从私有 Git clone，检查程序版本、加载节点、生成实时PNG并经原生队列处理合成FITS；源哈希不变，输出96×64。真实CLI/stdio MCP返回相同目录，MCP共66工具含新增4项。后端56项（含新增说明变更门用例）、Bundle适配器4项、宿主14项、软件页面12项通过；UI包类型、原生类型和生产构建通过。真实Git卸载保留4个受保护文件的哈希。类型/构建与回归结果见验证矩阵。浏览器实际安装确认、Agent在用户画布操作及视觉效果未代签；定义变化的完整B55升级仍不在首版验收范围。

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

2026-10-29 Siril安装失败修复：真实用户动作 ed77bbcd-99fa-4ca1-a826-e06ad488d94a 已失败。日志证明下载、解压及版本检查通过，失败发生在临时程序目录 os.replace 到正式app目录，Windows返回WinError5；未断言具体占用者或ACL原因。随后 model_copy 向 last_error 放入未校验dict，触发StrictModel嵌套序列化错误，导致state.json仍为running/installing。改为安全检查归档后直接解压到独占新建的正式app目录，并在该位置验证版本；只有验证通过才标ready。错误统一用ErrorDetail，失败保留实际路径和终态；已知失败的部分目录可确认卸载后重装，不冒充已有准确版本。当前隔离实例在确认动作failed、无正式目录／暂存目录后仅恢复失败状态，不自动重新安装。测试补齐不运行，编译及隔离更新证据见 `.artifacts/implementation/siril-install-fix-20261029/`。


2026-10-29 Auto Stretch 实时预览候选：修复执行节点复用 PromptServer 跨事件循环 aiohttp 会话导致的 Timeout context manager should be used inside a task；会话改为每次原生执行内创建、复用和关闭。新增非序列化 ComponentWidget，直接连接素材库数据节点时，参数停止变化350ms后请求当前成员低分辨率预览；固定组只切换当前预览成员，不改正式输入范围。后台复用预览执行器及4GiB派生缓存，保存最长边不超过1024px的原始线性 FITS 样本；使用相同 Siril 1.4.4 命令与参数生成预览，不把库中已拉伸JPEG作为输入。样本仅用于显示，其统计与完整原件可能不同。预览请求、参数过期、断线和关闭均取消本次专用进程，迟到图不覆盖当前图；无自动运行整图、无新工作流编辑或Agent接管。预览需先完成平台Siril安装；未安装时展示原因及安装入口。正式运行仍处理完整原件；Siril结果的预览按输出数值直接映射，不再次自动拉伸。新预览记录沿现有Preview表及缓存清理／繁忙拒绝，不新增表或依赖。测试全部仅编写，编译／构建及隔离更新以 `.artifacts/implementation/siril-live-preview-20261029/` 为准；无测试执行、性能实验、软件安装／执行或自行预览，不提交／推送／合并。


2026-10-29 M3 空白页修复候选：用户反馈刷新后只剩画布背景。只读读取实际 `/object_info/APF_169de0837f814cdea3295541ecacf463` 得到 `python_module: null`；原生 V3 基类默认该字段为空，手动注册未像原生加载器一样提供模块身份，前端 NodeDefStore 对它调用 split 会中断节点初始化。首个 Siril V3 类补齐 `RELATIVE_PYTHON_MODULE = custom_nodes.astrophotoflow`，不改变执行、科学引用或软件包行为。真实 native schema 用例增加 object_info 模块身份断言，仅编写不运行；Python语法、类型／构建和隔离维护更新证据见 `.artifacts/implementation/m3-blank-page-20261029/`。不自行预览，实际恢复由用户验收。


## 2026-10-29 M3 本地实现候选（未执行测试、未获用户验收）

本条覆盖下文历史记录中 B31 首操作未选、B33 未开工及软件包页面命令目录的对应现状；不覆盖 M4/M5 的其余任务。

- B31：用户授权选择首个 CLI 工具，本轮锁定 Siril 1.4.4 Auto Stretch。单件／固定有序 FITS 组由一次脚本按顺序 load → autostretch → save，原件不作输出；完整文件、数值 0、缺失文件和不支持的指定 HDU 明确处理。199 条命令仍为资料目录，不批量生成可运行节点。
- B32：沿用同一原生 WebSocket 的计划／真实按钮确认，修复 NativePageEvent 联合类型解析。页面只常驻软件名、红绿就绪点和安装／卸载按钮，计划进入原生 Dialog；红点原因可悬停／聚焦查看。新增程序副本卸载接口，确认后只删除 workspace/software/siril/app，保留素材、定义及画布。包状态／节点 token 变化拒绝旧计划，调用及维护繁忙时拒绝。
- B33：software.public 提供 invoke_operation／inspect_operation／cancel_operation／get_usage，保存真实阶段、日志、退出及候选文件。定向终止当前调用的专用进程，发送与实际退出分别返回；未知句柄不猜已停。启动前观察失败不运行，运行后观察失败不自动重算；服务恢复核对已有 PID／创建时间，未知占用继续阻止维护。
- 首节点：interfaces/siril_node.py 注册 V3 的 Siril Auto Stretch（APF_169de0837f814cdea3295541ecacf463），使用 APF_SCIENCE；控件从既有 JSON 定义读取，默认绑定变更明确拒绝。原生队列、停止及输出预览复用，不引入第二执行队列。软件未安装时节点可见，运行明确拒绝；安装后无需为首节点重启。
- 科学交接：data.public.resolve_canvas_inputs 验证固定成员顺序、完整内容哈希及当前资料／设备／校准快照；workflows/software_calls.py 接收仅原生内部调用，固定运行目录、保存必要调用事实并检查输出，输出保持引用，不自动登记为素材。普通网页代理、CLI 和 MCP 不开放直接 Siril 执行路由。
- 边界：当前仅首个固定节点接入；完整 M4 动态节点库／编辑器、M5 项目图关联／SQLite 运行权威及更新影响、Agent 软件入口仍按后续任务实施。提前交付的卸载不改写任何图，不冒充 B55 完整维护影响闭环。必要调用 JSON 与日志位于本次原生 prompt 的 runs/<prompt_id>/，后续完整运行记录接入仍待实现。

编写用例但不运行；已完成 UI 类型检查、原生类型检查及前端生产构建，Python 语法／OpenAPI 导出及隔离 demo-preview 更新证据统一存于 `.artifacts/implementation/m3-software-20261029/`。真实安装、下载、原生图执行／定向停止与视觉质量均待用户验收；不操作浏览器、不开展性能实验，不提交、推送或合并。


2026-10-29 缩小错位修复候选：概览底图不再始终object-contain铺满容器；复用OpenSeadragon当前图像边界和当前视口坐标，在open、缩放动画、平移和resize时同步CSS像素位置／尺寸，取消图片默认max-width限制。首次加载尚无视口时仍适应窗口；切成员清空旧边界并拒绝迟到回调。新增坐标与组件回归用例，仅编写未运行；原生类型检查和生产构建通过；已更新隔离demo-preview网页资源，入口SHA256一致，无后端修改或重启；日志与部署记录见.artifacts/implementation/media-alignment-20261029/，视觉效果仍待用户验收。

2026-10-29 预览加载修复候选：已针对用户持续加载问题修改FITS读取、渐进占位、phase与共享取消，回归测试已补齐但未运行。Python源文件／测试语法编译、UI包类型检查及原生类型检查／生产构建通过；已通过维护机制重启并更新隔离demo-preview（operation 6db11aaf-1d61-4b09-b4e9-0c2ef7442ee2，32688／32690，blockers为空），静态入口散列一致；证据目录.artifacts/implementation/media-loading-20261029/。不宣称速度或视觉通过，不提交／推送／合并。

2026-10-29 统一媒体查看候选：在`codex/m2-ui-acceptance`保留既有工作区改动，节点／素材库／固定组成员共用原生MediaViewer与OpenSeadragon6.1.1。当前成员2048px概览、可见区域512px瓦片、DPI100%／缩放／平移、同尺寸成员保持视口及跳转已形成实现；不对千张图批量解码。FITS／SER／NPY局部读取，其余格式只解码当前图像／数组并复用显示底图；NumPy选择轴／切片，视频Range播放、按需H.264代理和实际PTS到源帧映射用于暂停原件帧放大。缓存预算128MiB浏览器瓦片、256MiB后端编码瓦片、4GiB派生磁盘，沿用Preview所有权、清理保护、预览执行器和维护繁忙拒绝；不新增表／迁移，不改变科学输入或Agent控制。测试文件已补齐但按用户要求未运行，无性能实验或自行浏览器预览。16份Python源码／测试仅语法编译，OpenAPI生成、UI包及原生类型检查和生产构建通过（最终Vite49.11s）；隔离维护重启fd6f461e-55f4-4ef7-be55-0b0cace38ee0已completed，网页／服务仍为32688／32690，静态资源复制及hash回执以`.artifacts/implementation/media-viewer-20261029/deployment.json`为准。视觉／性能及功能验收仍由用户进行。旧display接口和现有导入任务事实保留，未提交、推送或合并。

2026-10-28 Object／分类预览修订候选：按用户最新意见，图像组内相同Object且同来源目录／兼容数值颜色布局的subframe只测固定顺序首张有效帧，其余复用现有MTF／背景白平衡数值；masterframe逐张独立，Object缺失独立，未知分类和非图像组来源保留旧规则。用户否决256×256固定网格，现改为原图分层随机取样，固定种子、最多262144个空间样本；FITS按抽中行连续读取，RGB保留通道对应，Bayer按2×2色彩单元统计，XISF仍可能全帧解码。preview_recipes.py集中组键、保存数值、重试和回填，配方随各版本保存，报告间隙可从已发布首帧缩略图恢复。大图直接复用已有MTF，不重新测量；已有缓存不批量重建，不改原件、科学参数、成员顺序或快照，无接口／迁移／依赖新增。测试已补齐但不运行，无性能实验或自行预览；语法、类型／构建及仅隔离demo-preview维护重启／资源更新的实际证据见 .artifacts/implementation/object-subframe-stretch-20261028/。此前逐图独立／256×256候选为历史，以上最新规则覆盖；显示质量、精度及速度均待用户验收，不提交、推送或合并。

2026-10-28 逐图快速预览候选：按用户最新选择取消同条件组共用拉伸基准及参考图等待，导入／失败重试／缺失缩略图回填从各自像素估算1%／99%范围；不再新增或沿重试传递任务级preview_stretch_groups。统计采用最长边256的确定性空间采样，打开大图的自动MTF／RGB背景白平衡同样限制统计规模。XISF和高位深常规图像先按请求尺寸采样到预览规模再8位映射，公开输出预览和大图仍遵守请求尺寸；XISF底层全帧解码限制保留。已有可用缓存、历史保存数值、原件、快照、成员顺序、分阶段进度及通知规则保持，不批量重算历史图片。测试补齐但不运行，无性能实验或自行预览；Python语法、前端类型／构建及仅隔离demo-preview更新／必要维护重启的实际证据见 .artifacts/implementation/independent-preview-stretch-20261028/，不宣称实测提速或视觉验收通过。未提交、推送或合并。

2026-10-28 本机导入选择器焦点及取消修复候选：文件／文件夹统一绑定当前桌面宿主，首次显示临时置前，关闭后返回焦点；服务内单窗口限制，重复请求409。UI显式取消、关闭及卸载中止请求，代理关闭上游连接，后端关闭并回收本次选择器，避免仅关网页弹层留下后台窗口。导入、托管、数据库及工作台设置目录选择接口不变。相关原生生命周期、HTTP、代理取消、前端中止／迟到响应测试已补齐但不运行，不自行预览。Python／PowerShell语法、原生C#辅助类型编译、前端类型／构建及仅隔离demo-preview更新／必要维护重启以 .artifacts/implementation/native-picker-focus-20261028/ 实际日志和回执为准；真实窗口层级及焦点由用户验收，未提交、推送或合并。

2026-10-28 工作台设置隐藏授权导入目录：只移除WorkbenchSettings中该区域的标题、增删、ID／路径输入及路径提示；ConfigValues.import_roots、翻译定义、配置读取／保存和旧来源接口保留。保存其他字段继续提交完整配置，重新读取采用服务端最新隐藏值，不清空现有目录。组件和原生宿主用例已补齐但未运行，不自行预览；类型／生产构建及仅隔离demo-preview静态资源更新见 `.artifacts/implementation/hide-import-roots-20261028/`。无后端变更、无需重启服务，未提交、推送或合并。

2026-10-28 用户取消预设导入目录限制：网页导入直接通过imports/select-local打开本机系统文件／文件夹选择器，再进入原有资料确认，不查询授权根或跳转设置。imports支持省略root_id的绝对path托管来源，任务内保存绝对路径及受理观察，文件夹只取当前层，沿用登记／复制散列／预览及恢复重试，不改已托管身份、设备快照或已保存配置。已有root_id来源与上传／CLI／MCP保留，MCP import_local描述同步。本条覆盖此前“必须先配置授权根目录”的产品及实现说明；新测试仅编写不运行，未实际打开系统选择器或自行预览。类型编译／构建、OpenAPI和隔离demo-preview更新证据见 `.artifacts/implementation/direct-local-selection-20261028/`。正常dev不动，无迁移或新依赖，不提交、推送或合并。

2026-10-28 Nodes 2.0 素材展示候选：素材库加入操作收至行右侧图标，固定节点隐藏reference文字输入，新增非序列化ComponentWidgetImpl显示当前成员图片、核心参数及只读详情；原生WidgetDOM增加ComponentWidget挂载，ImagePreview增加默认关闭的displayOnly选项，原有预览操作默认保持。只读canvas-data/inspect按固定引用查询数据库资料；尺寸来自固定HDU，当前拍摄参数来自Asset，不读大原件、不将缩略图视作科学输入。组按需逐张加载，迟到／取消响应隔离，URL及计时器随节点卸载释放；浏览不写reference或graph。新建、MCP／CLI、重开和复制恢复共用原生生命周期。测试文件补齐但未运行，不自行预览；类型／构建与仅隔离demo-preview更新证据见 `.artifacts/implementation/nodes2-data-display-20261028/`。无迁移、新依赖或ComfyUI升级，未提交、推送或合并，用户验收仍待完成。

2026-10-28 素材入画布候选：在codex/m2-ui-acceptance增加共享素材／固定有序组的“加入画布”及原生拖放，组内可单件加入；使用APF_DATA_REFERENCE及既有InputReference，不复制原件或主动运行。MCP／CLI直接加入已授权活动画布：网页更多菜单交回加数据控制，手动改图、切图／子图及断连撤销；精确页面／根图／当前图／内容及控制标记检查，当前引擎按operation_id返回实际应用／未知回执，未知不自动重发。②通过公开prepare_canvas_data供⑤消费，UI包无原生依赖；新增HTTP、CLI、MCP及OpenAPI同步，现有入口保留。仅此窄范围形成代码，不把B51／B52整卡或完整运行闭环标完成。测试已补齐但不运行，无性能实验或自行预览；编译、构建及仅隔离demo-preview的资源／重启结果见 `.artifacts/implementation/library-canvas-20261028/`，用户验收待完成，不提交、推送或合并。

2026-10-28 本机托管导入及一次性通知候选：网页授权目录内选单／多文件或当前层文件夹，不再使用浏览器File上传；空授权目录引导原生工作台设置。任务受理冻结范围和来源观察，登记／有界复制衔接，复制时BLAKE3同步校验，原件与预览分阶段报告；新私有import_progress.py合并进度，preview_executor.py共享调度主动／可见和后台预览，保留固定配方及阶段重试。原生Toast统一成功／部分失败／整体失败／晚到预览异常，workspace＋taskID＋类别去重，历史不重放，详情仅从本次通知打开，无常驻汇总或历史页；本条覆盖此前导入汇总和关闭按钮候选。测试已补齐但按用户要求不运行，不做性能／并发对比或101张样本压测，不自行预览；编译与仅隔离demo-preview的更新／重启回执见 `.artifacts/implementation/local-managed-import-20261028/`。无迁移和新依赖，原上传／CLI／MCP保留，未提交、推送或合并；M2人工验收仍待完成。

2026-10-28 导入失败通知关闭修订候选：失败通知增加关闭按钮，按稳定任务ID保存浏览器当前站点的localStorage关闭偏好，轮询、刷新及重新进入后不再显示已关闭任务通知；同名新任务独立显示，不删除任务、素材、异常资料或发送写请求。素材行异常和活动进度保持。已补齐组件及素材行隔离用例但未运行，不自行预览；编译／demo-preview资源更新回执见 `.artifacts/implementation/import-notice-dismiss-20261028/`。本条覆盖前一候选“失败持续显示且不能关闭”的呈现，M2人工验收仍待完成，未提交、推送或合并。

2026-10-28 素材库最小精简候选：原生更多菜单承接刷新、批量管理、回收站、显示方式及每页数量，保留导入／设备管理与分类／搜索／筛选两行结构；批量状态、单页翻页隐藏及文字排序表头已调整。导入不再显示独立结果汇总，活动进度移出表格；成功事件经宿主Toast短暂通知并去重，历史成功不通知，行内解析／预览异常及未入库失败原因继续可查。没有新增后端接口、配置、迁移或依赖，设备管理保持。测试文件已补齐但未运行，未自行预览；编译及隔离demo-preview资源更新结果见 `.artifacts/implementation/library-compact-20261028/`，本条覆盖较早候选“保留完成汇总”的界面描述，不覆盖历史证据。M2人工验收待完成，未提交、推送或合并。

2026-10-28 设备管理原生控件与显式批量模式候选：设备／组合默认隐藏复选框及选择列，通过原生Menu进入批量管理；模式与数量分开，零勾选不退出，完成、搜索／分页／排序／切换按约定清空。原生Checkbox／Tabs／Menu由宿主注入，Lucide类别图标替换圆圈，列表主题色收敛到原生语义。共用编辑表单及删除接口保持。测试文件已生成／同步但不运行，不自行预览；编译更新demo-preview，证据见 `.artifacts/implementation/equipment-native-management-20261028/`。未提交、推送或合并。

2026-10-28 我的设备简洁列表候选：普通行去除灰色卡片底及边框，悬停／选中／键盘焦点分别强调；预留行内编辑位置，名称及类别保留，省略重复或空型号。选择、勾选删除、共用表单及组合表格保持。测试文件已补齐但不运行，不自行预览，仅编译更新demo-preview；日志与资源回执见 `.artifacts/implementation/equipment-simple-list-20261028/`，未提交、推送或合并。

2026-10-28 我的设备行内编辑候选：单击选中后仅在该行右侧显示“编辑”，移除列表下方按钮，继续复用新建设备表单；切换目标后按钮移动，保存成功保留选中，勾选删除与行选中分开。相关测试文件已同步但不运行，不自行预览，仅编译更新隔离demo-preview；日志及回执见 `.artifacts/implementation/equipment-row-edit-20261028/`。未提交、推送或合并。

2026-10-28 我的设备选中编辑候选：单击选中后在列表下方显示“编辑信息”按钮，点击打开新建／编辑共用表单；移除行双击及键盘直接打开，使用原生按钮选择和操作。测试文件同步显式入口、无选中隐藏、双击不打开、切换目标预填及勾选隔离；不运行测试或自行预览，仅编译更新demo-preview。回执见 `.artifacts/implementation/equipment-selected-edit-20261028/`，未提交、推送或合并。

2026-10-28 设备新建／编辑共用表单候选：编辑直接复用新建EquipmentFields及原生控件，预填数据、固定类型，标题为编辑设备，底部取消／保存；保存统一PATCH改动字段，保留revision、失败输入、未保存确认及未触碰规格。已同步测试文件但不运行，不自行预览；编译更新隔离demo-preview，日志与回执见 `.artifacts/implementation/equipment-unified-form-20261028/`。未提交、推送或合并。

2026-10-28 我的设备编辑入口候选：单击选中、双击或Enter／空格直接打开已有编辑弹窗，移除下方重复详情；保留逐字段保存及revision、错误和勾选删除规则。测试文件已同步但未运行，不自行预览；编译更新demo-preview，日志及资源回执见 `.artifacts/implementation/equipment-doubleclick-edit-20261028/`。未提交、推送或合并。

2026-10-28 组合编辑入口候选：选中组合后在新建拍摄预设旁加入“编辑设备组合”，复用现有组合表单；移除更多菜单中的重复编辑入口，删除仍留在更多。单件设备规格编辑保持在我的设备。组件用例同步相邻入口、唯一入口、预填／取消及保存期间禁用；不运行测试或自行预览，仅编译更新demo-preview。日志与资源回执见 `.artifacts/implementation/equipment-edit-action-20261028/`，未提交、推送或合并。

2026-10-28 预设滤镜／Offset及参数命名候选：沿用组合滤镜多选，预设可选所属组合的一片注册滤镜，增益模式增加Offset；预设名称由可选前缀及滤镜／曝光／温度／ISO或Gain／Offset后缀组成，保存前显示完整名称，再次编辑更新后缀。旧隐藏字段、稀疏null／0和导入快照规则保持，不新增HTTP、数据库字段或依赖。相关组件测试文件已补齐但不运行，不操作浏览器；仅编译更新隔离demo-preview，交付日志见 `.artifacts/implementation/equipment-preset-filter-offset-20261028/`。用户自行预览，未提交、推送或合并。

2026-10-28 组合预设最小精简候选：选中组合后移除重复详情，仅保留新建拍摄预设及已有预设；组合编辑／删除收进已有更多菜单。设备管理页签、表格及组合表单移除ⓘ，完整名称直接悬停文字查看。预设表单只展示名称、温度、曝光及ISO／增益，已有隐藏字段保留，不改HTTP或数据结构。测试文件已补齐但不运行，编译与demo-preview更新回执见 `.artifacts/implementation/equipment-preset-minimal-20261028/`；用户自行预览，未提交、推送或合并。

2026-10-28 设备组合横向表格候选：固定名称／相机／望远镜／赤道仪／滤镜／光学附件六列及勾选，兼容注册、组合内及历史成像系统；空列为 `—`，多件摘要用ⓘ查看完整名单。组合列表新增专用设备列排序参数，服务端先过滤排序再分页，空值最后、同值按组合名称／ID稳定排序；切换排序清空勾选并回第一页，脏草稿及保存期间禁止。我的设备和素材库布局不变，无数据库迁移或依赖新增。组件／接口测试文件已补齐但按用户要求未运行，不进行浏览器预览；编译及隔离demo-preview更新回执见 `.artifacts/implementation/equipment-setup-table-20261028/`，M2人工验收仍待完成，未提交、推送或合并。

2026-10-28 设备管理工具栏精简候选：设备组合与我的设备统一搜索／单个新建操作、更多中的刷新、勾选后出现的删除操作和多页时才出现的固定50条分页；组合重复标题及筛选按钮移除，我的设备直接按类别筛选，素材库分页偏好保留。补齐／调整组件测试文件但按用户要求未执行；本轮仅编译更新demo-preview，不操作浏览器，不提交、推送或合并。构建结果及更新回执见 `.artifacts/implementation/equipment-toolbar-20261028/`；用户自行预览与M2验收仍待完成。

2026-10-28 设备管理紧凑布局候选：原生限宽Dialog、五行搜索多选、同窗设备编辑、48px列表及32px控件已实现，范围仅设备管理，业务接口、素材库和工作台设置不变。用户最新要求：只实现并编写测试用例，不自动运行测试；新实现仍编译构建并更新demo-preview网页资源，浏览器预览及人工验收由用户自行执行。新增用例保持未执行，不把较早候选的检查结果算作最终验收。证据位于 `.artifacts/implementation/equipment-compact-20261028/`。

2026-10-28 设备管理优化候选：在 codex/m2-ui-acceptance 实现组合优先、我的设备、五类就地登记复用及设备／组合／预设直接删除；项目页面移出该模块，项目数据及接口保留。删除清理组合关联和预设默认值，历史素材、固定版本及已受理任务快照保留。自动验证与实际预览证据见 `.artifacts/implementation/equipment-management-20261028/` 及验证矩阵；用户M2验收仍待批准，不提交、推送或合并。

2026-10-28 M2 UI优化候选已在`codex/m2-ui-acceptance`实施评审F01～F04、U01～U12共16项。三个P1已修复：内容观察接受正常纳秒时间戳，项目添加图像组使用dataset字段／保存路由，处理异常导入保留完成汇总且默认条目显示解析失败。原生FormItem／Button／Input由宿主注入，说明和完整标识用ⓘ，简约侧栏、键盘编辑、模式草稿与零值表达已调整。数据前端156项、科学输入／内容接纳及架构13项通过，UI和原生类型检查／生产构建通过，依赖边界0错误／9条既有循环警告。真实demo-preview复核了托管文件观察、切换结果隔离、图像组备注保存后恢复、预设空值／模式零值、500／700px侧栏、长文件名提示和原生输入Gain=0真实上传。新增合成素材M2_ui_controls，原件hash与原固定组v1不变；正常dev和共享runtime未动。证据及完整验收步骤在`.artifacts/implementation/m2-ui-optimization-20261028/report.md`。当前仅为候选，M2用户Milestone批准仍待完成；本轮未提交、推送或合并。

以下为此前评审／集成的历史记录，其中“未实施”等状态以本段和验证矩阵最新候选为准。

2026-10-28 M2素材库产品／风格评审：在`codex/m2-ui-acceptance`上仅审查，未修改产品代码、未提交／推送／合并。两份Luna high审查及主代理Computer Use复核形成16项清单，见`.artifacts/acceptance/m2-ui-review-20261028/review.md`；请求的GPT-6.1 Luna不被接口支持，已说明实际使用GPT-6 Luna high。真实观察到内容检查因纳秒时间戳超出前端Zod安全整数范围而失败；项目添加图像组的详情误用项目字段，源码保存路由也错误；无效FITS任务completed_with_errors后默认列表不直接显示解析失败。其余为状态隔离、术语、入口、键盘、窄栏、预设及说明ⓘ等优化，均未实施。demo-preview保留两张正常合成FITS、一张故意无效样本、组合／项目与固定组引用，原合成文件哈希不变；没有执行删除或触碰正常dev数据。M2用户Milestone批准和未走查能力继续待验，不能用本次设计评审代替。

2026-10-28按用户最新授权完成本地Git整理：已确认的M1设置修订及两处M2语法修复提交在demo，随后快进合入dev（`be0422e5`）；本地`feature/database_management`已删除，当前分支为`codex/m2-ui-acceptance`，用于M2 UI／操作优化与功能验收。M2 Milestone尚未获用户批准。其余B31／B32／B41等未提交内容已完整保留到当前工作区，未纳入dev；没有推送，main保持不变。此前不提交／不合并约束已被本次明确授权覆盖，仅限上述交付。

集成前在移除其余未提交业务改动的干净候选上复核：Python配置／客户端／代理／架构／数据服务110项通过（保留既有SQLAlchemy表排序警告），配置组件10项、原生设置／侧栏64项通过，UI包及原生应用类型检查通过。发现并补齐了重启测试mock缺失的selectDirectory方法；OpenAPI重新生成，85项公共操作与候选语义一致。原生产构建与浏览器证据继续使用上列已验收候选，本次Git集成未重新启停实例或触碰正常dev数据。

2026-10-28用户明确确认“设置这部分可以了”：demo原生设置入口、展开section、目录选择与绝对路径展示、说明／路径悬停呈现按当前已展示候选的设置范围记为用户接受。用户要求继续M2数据与资产管理验收，尚不表示M2通过；本次Git整理按上述最新明确授权执行。M2隔离验收使用demo-preview和`.artifacts/acceptance/m2-user-20261028/`，首轮仅准备两份合成FITS，尚未导入。

2026-10-28 demo工作台提示候选：长说明与完整路径改为字段／标题／重启操作旁的原生ⓘ悬停提示，保留section、字段输入、目录选择、运行地址和关键状态。提示区分已保存绝对路径与当前输入，不更改路径解析或后端接口；保存状态只因实际编辑失效。定向组件11项及生产构建通过，浏览器证据见`.artifacts/implementation/demo-settings-tooltips/`；该设置范围已由用户确认并按上述最新授权集成。

2026-10-28用户验收调整：工作台中的“工作区、端口和目录”及“运行信息”改为直接显示的section，不再使用折叠控件；配置行为保持。

2026-10-28 demo设置入口候选：工作台配置已迁入原生设置窗口的“工作台”页面，移除独立侧栏；通过宿主传入原生FormItem／Button／Input，整组保存、冲突和显式重启保持。APF本地设置按明确清单隐藏3D、生成预览、提示权重、API价格、模型库展示及云账户相关面板，导航／搜索／直接定位同一规则，不重置设置值。真实隔离浏览器7类检查通过，类型检查／生产构建和依赖边界通过，证据见`.artifacts/implementation/demo-settings/`。该设置范围已由用户确认并按上述最新授权集成。

2026-10-28：本地 `demo` 从 `dev` 的 `741f6f1d` 创建，按用户要求不提交、推送或合并。B31进行中：已核实Siril CLI 1.4.4与对应本机便携archive的内容一致；发布页未提供可核对的校验和／签名。单图autostretch有默认baseline及三轮真实参数变化并回读FITS；同散列隔离副本的实际autostretch运行时曾以操作系统强制终止进程，stdout显示在计算中，进程退出且未生成输出；这不证明优雅取消或产品取消API。无效autostretch选项的真实脚本记录参数错误、退出码1且未输出，见`.artifacts/implementation/B31/parameter-error-probe-20261028/`。当前18个本地FITS没有重复目标+滤镜的多帧组合，无法支持有依据的科学序列验证；详见`.artifacts/implementation/B31/dataset-inventory.json`，官方样例下载／用户提供序列／暂记缺口问题待答。新增版本绑定的199条只读HTTP命令目录与SoftwarePanel搜索界面，展示官方语法、说明、链接和Scriptable标记；逐项状态在`.artifacts/implementation/B31/coverage-matrix.json`，尚未接入B56/B57 MCP，不能代表逐条结构化理解、节点生成、加载或运行。固定包查询、state.json读取和配套定义已实现。B41本地候选通过：JSON定义契约及六项public已实现，9项定向测试和6项架构测试通过，GPT-6.1 Sol Low独立审查无剩余发现；未进入dev，M4用户验收待B42／B43同轮完成。B32已接安装计划／准备HTTP候选、SoftwarePanel及同socket页面事件候选（G03），软件服务9项、SoftwarePanel3项、CommandDirectory1项、SoftwareClient1项、节点9项、架构6项通过；Python AssetClient命令目录定向测试1项通过，UI包与原生类型检查及整页生产构建通过。确认等待工作台状态后会重核页面token、计划ID及节点计划，阻止已替换计划被启动，安装前复核包token。GPT-6.1 Sol Low对B32最新锁范围源码复核无剩余发现。较早只读预检的marker匹配只针对旧candidate；当前repo engine archive hash `c6c7a476…`与manifest一致，但真实用户runtime marker仍为`ec74c9e9…`且`server.py`与candidate不同，因此`--reuse-runtime`当前会失败。受限进程的`LOCALAPPDATA`被重定向到sandbox包路径，W1未初始化或启动。候选engine源码overlay已复制到`.artifacts/implementation/B32/runtime-overlay`，但环境拒绝将隔离runtime链接到已验证的1.88GB Python venv；没有复制venv、初始化W1或启动服务，完整证据见同目录`overlay-preflight.json`。11:14 UTC只读`apf status --workspace .artifacts/workspaces/dev`返回stopped、processes=[]，端口31388／31390及隔离端口32588／32590均无监听；没有启停或修改workspace。共享runtime未修改；真实网页／用户按钮验收、确认后的实际下载安装仍未完成。B31首个操作待用户确认，当前采用已验证的Auto Stretch候选；B31有效序列、参数／依赖／风险逐项复核、节点加载及真实MCP链路仍未验。B22两处提交的字面量反斜杠n语法错误已修复。证据见[验证矩阵](test-matrix.md#demo-b31-probe)与`.artifacts/agent-checkpoints/2026-10-28-demo-B31-command-directory.md`。M2 Milestone用户批准仍待核对；B31～B62整体交付未完成。

2026-10-28 B31自有图像分析补充：准确Siril1.4.4 `findstar`对baseline及三轮Ha拉伸输出各找到maxstars=500；FWHM、axis-ratio及Sat标记汇总见`.artifacts/implementation/B31/psf-rounds-20261028/star-metrics.json`与round3测量文件。这些是拉伸后单张master-light的自评统计，不代表原始seeing／光学PSF或科学准确性。

2026-10-28 B31第三轮真实调参：在同散列输入副本上仅将Siril 1.4.4 `autostretch -linked` 的target background调为0.12；CLI及重读／`bg`／`bgnoise`／`findstar`均退出码0，生成4144×2822、单通道32-bit有限像素FITS，SHA-256 `adfa772283c44e7fecb9f526f1c7cc819fc4e9a22babf55b8e70ea55a83a5889`。运行后重新hash原始数据集文件，原件与输入副本均为`79734c29dcd9af8218a81bc3d709143b87984c701798130ef8e5034458d7ef5e`。背景噪声0.004581；500星封顶样本的FWHM轴比中位数0.9498、`Sat`标记21.2%、Gaussian RMSE 0.01357。GPT-6.1 Sol Low已独立复评四版：Round 2是其偏好折中；所有版本光晕处理均为3/5，低于全项≥4质量门槛，星形状／表观锐度均4/5，用户接受也未取得。Round 3日志还记录sandbox内Pictures目录和Siril配置写入权限错误，但脚本执行、产物保存及回读均成功。分项见`.artifacts/implementation/B31/image-review/sol-low-2026-10-28.md`；Round 3完整命令、日志、输出、hash和同尺度预览均在`.artifacts/implementation/B31/round3-targetbg-20261028/`。

2026-10-28 G10只读资源预检：dev venv未安装embedding后端；真实用户ComfyUI venv已有Transformers 5.20.2／Torch 2.14.1 CPU，但未发现sentence-transformers／onnxruntime／fastembed。主机Windows 11 x64，16核／32逻辑CPU，约50.6GB RAM、当时29.0GB可用。两个双语候选的固定版本、许可和权重哈希见`.artifacts/implementation/G10/model-preflight.json`，恢复摘要见`.artifacts/agent-checkpoints/2026-10-28-demo-G10-model-preflight.md`；尚无模型选定或下载，未改依赖／共享venv。等待用户确认资源取舍后才能benchmark；这不是G10通过证据。


2026-10-28发行资源预检：对当前候选重建wheel／sdist，`verify_distribution.py`已证实wheel仓库外安装smoke、catalog清单/Schema、ComfyUI archive哈希/manifest及page identity资源校验、无Node时从sdist重建并再次安装smoke通过。打包时使用已存在setuptools 78.1且`PYTHONDONTWRITEBYTECODE`的ComfyUI Python环境非隔离构建；PyPI DNS不可用，因此隔离setuptools下载未验证。最终候选和报告为`.artifacts/implementation/B62/dist-final-v4-20261028/`与`packaging-report-final-v4-20261028.json`；旧`.artifacts/dist`及旧报告已保留于`prior-artifacts-20261028/`，恢复摘要见`.artifacts/agent-checkpoints/2026-10-28-demo-B62-resource-preflight.md`。这只是B62发行资源预检，B61前置及完整`build_release.py`／B62/用户批准仍未通过。

更新时间：2026-10-28。集成分支为 **dev**，M1历史候选分支为 **codex/workbench-settings-ui**，继承B11 `6b10657`和B12中间提交`c23e10d`；M1已获用户人工验收通过及合入dev、删除当前功能分支授权。设计基线`9d4c729`已同步远端。原生网页及平台源码基线为 `16025dd89f2c3c2b25bae58bcc241e5202863c87`，已从原 dev `b6759ab` 快进合入；main 不属于本轮交付范围。

仓库为 [MaojieXu/AstroPhotoFlow](https://github.com/MaojieXu/AstroPhotoFlow)，本地目录为 `C:/Users/Administrator/Desktop/WorkSpace/AstroPhotoFlow`。本文维护当前实现、运行基线和有效待办；产品范围见[现行需求](../requirements/README.md)，历史测试证据见[验证矩阵](test-matrix.md)。

## 当前设计状态

验收反馈已修复UUID字符串请求、重启受理回执及未保存配置误用；实际网页已验证导入3／预览6保存并重启生效，地址可点击，原生风格输入及移除按钮对齐。证据为`.artifacts/implementation/M1/restart-browser.json`、`restart-python-final.xml`（115通过）、`restart-build-final2.log`和`restart-build-final3.log`。用户要求修复后停止追加测试，已遵从；网页重启第三轮独立审查因此中止，不宣称该轮完成。跨端口自动重连仍按界面提示及CLI核对。

M1历史界面（已由上述demo设置候选替代）按用户验收反馈调整为左侧“工作台配置”，位于工作流之后；复用原生侧栏和主题，取消顶部按钮及弹窗。侧栏注册5项、配置表单4项测试、类型检查和生产构建通过，真实浏览器5类检查通过；本次界面调整已由用户验证通过，随M1整体集成。证据见`.artifacts/implementation/M1/sidebar-update.md`。

**M1用户验收通过，交付合入dev**：用户确认修订后，启动失败已统一复用stop排空；待登记进程提前留痕，身份暂不可读时保留核对依据，控制结果写入失败不遮盖启动及清理错误。新迭代第三轮独立审查无剩余阻断。全量Python为336 passed、2项显式真实测试另行通过；浏览器五类检查通过。真实在途导入在模拟引擎启动失败后完整完成并正常退出。最新报告为`.artifacts/implementation/M1/delivery-report.md`及`iteration2-round3-review.md`；旧轮次失败证据保留。原dev已恢复31388／31390，隔离候选实际网页为32592；用户已于2026-10-28在当前聊天确认“通过测试，可以将结果merge到dev，并删除目前这个branch”；B11～B13及本轮修复整体交付dev。

五模块概要、数据设计及[接口契约与文件级详细设计](../api/platform-contracts.md)已成文，第④阶段已通过多Agent独立复核。[第⑤阶段近期实施计划](implementation-plan.md)按六个里程碑细化22个Batch：M1三卡已集成dev并获用户批准；M2的B21～B24已快进合入dev，M2用户Milestone验收尚待完成；B31／B32进行中、B41本地候选通过；B62仅发行资源预检，B33、B42、B43及B51～B61共11卡未开工。五模块分别由①公共基础、②素材和项目资料、③外部软件、④节点定义、⑤工作流／运行／Agent交互负责。M1后为82项公共HTTP操作，M2增加内容观察／确认两项，B31增加软件包列表／版本命令目录两项，B32增加详情／安装计划／准备三项，目前OpenAPI共89项；58个数据MCP工具及注册保持。第④阶段独立证据保留于`.artifacts/fourth-stage-design`，计划检查进入`.artifacts/implementation-plan`。

第⑤阶段计划联合审查补充六份按M分组的22张任务卡，细化文件N／M／R、关键签名、调用顺序、测试和人工验收；原契约补齐必要的编辑期只读数据校验、Python具名客户端和固定业务ID。用户确认22 Batch内部小步、M3／M4交叉同轮分别批准、共用HTTP归core、维护窗口恢复原dev、普通移除与MCP在B57一次切换；历史证据进入`.artifacts/implementation-plan-review`。后续卡Ready仍须实际前置，首包和模型继续在各自任务前选择。

B11实现：新增ConfigValues／ConfigSave／ConfigState及get_configuration／save_configuration／load_running_settings；用户TOML的workspace.default取代旧active-workspace读取，Settings.workspace显式且必填。保存采用文件锁、配置token与完整文件替换，只保存最新值；运行采用值独立读取，无默认时清楚失败。初始化激活写默认TOML。B12已实现结构化启停／重启、自动端口及安全回写、实际采用值和导入／预览／原生准入屏障，B13已提供原生页面配置表单。全部实现与真实验证见[矩阵](test-matrix.md#m1-foundation)及`.artifacts/implementation/M1`，最终独立复核结果在同一证据目录登记，用户已批准A(M1)，B11～B13随本次Git集成记I(B11)／I(B12)／I(B13)。正常dev用保留的原版本恢复31388／31390，补齐实际恢复启动的运行元数据以保持当前数据客户端可读；配置、默认指针、令牌、业务表行数与引擎散列不变。M1页面使用隔离工作区，实际地址见候选回执；不要把旧dev页面当作M1页面。

⑤复用原生当前图、会话撤销、转换和队列；重要方案另存，每次运行保存实际图与参数。首版Agent针对明确活动画布操作，手动改图即接管，用户明确交回后继续；切图暂停后续编辑或新提交，已受理运行继续。实际执行的图像节点产生多次轻量预览，用户选择完整结果后才交②保存。相关桥接、运行记录及预览仍待实现或验证。

2026-10-27确认：Agent日常局部改图，整图JSON用于导入或明确替换；运行先保存当前画布，失败不提交；用户在目标网页点击“交给Agent”绑定页面。未来精简MCP的三个入口设计及58业务迁移清单见契约文档，均尚未实施。原生连接命令／响应、可靠UI确认、软件装配及科学执行须原型，当前没有画布MCP能力。

默认运行保证为可复现，可明确选择仅引用；固定素材组范围、新运行使用纠正资料、节点更新规则及原件保护保持。个人偏好可查看和恢复历史，删除包括历史正文；该能力仍待实现。

第④阶段确认：④定义JSON、⑤记录SQLite，原生连接的有限中继及一个白名单平台节点包；外部变化确认后同Asset新增内容记录，仅显式引用更新，旧组／旧运行不改；软件安装／更新由网页确认准确计划后执行。文件落位、公开签名、原生最终写与入队检查、实际取消／停止、无网页事件及具体测试归属均进入详设。软件首包／操作、可靠页面交回、装载、目标转换、科学缓存与实际缩图仍需原型；详设不是这些能力已通过的证据。

2026-10-28文档对齐：以demo当前未提交代码核对文件、公开函数及消费者；导航与详设已纠正M2科学交接、B32软件计划／页面事件及B41定义存储状态。静态检查和范围见[矩阵](test-matrix.md#demo-docs-code-alignment)，不作为新增运行验收或Batch完成证据。

## 当前实现

- 固定 ComfyUI 0.42.0 和前端 1.57.1 的原生网页平台。画布始终挂载，节点库下依次为素材库、工作流；启动打开素材库，设备管理位于导入旁。
- Python 已按 core、contracts、modules/data、interfaces 归位；自研 UI 与原生桥接分开。③已有固定软件包／命令目录、安装计划／准备及页面确认候选，④已有JSON定义及六个public操作；⑤业务目录仍仅文档。contracts/workflows.py和workflowBridge.ts已用于B32组合DTO及软件确认，不表示⑤工作流／运行／控制已实现。文件与公开函数见[源码映射](../architecture/module-map.md#31-当前文件与公开函数映射)。
- 已有资产与集合版本、项目固定引用、导入、设备快照、校准关联、预览和回收站。schema 为 `0009_remove_legacy_capture_profiles`，数据 MCP 为 58 个工具。
- 单图自动拉伸从原件计算 RGB 背景白平衡和 MTF 配方，同步大图与缩略图；不修改原件、科学参数、版本身份和其他成员。

当前边界见[架构概览](../architecture/overview.md)、[模块导航](../architecture/module-map.md)和[素材行为](../architecture/assets.md)。

## 当前运行基线

- 开发 Python：`.artifacts/venvs/dev`，使用根 `uv.lock`；Node 26.8.2、pnpm 11.13.1，前端锁文件为 `frontend/pnpm-lock.yaml`。
- 正常 dev workspace：`.artifacts/workspaces/dev`，网页 31388、领域服务 31390；根 `.env` 与默认指针仍选择同一 workspace。
- 固定 CPU runtime：真实用户 LocalAppData 下的 `AstroPhotoFlow/runtime/native-web-0.1.0`，与旧 0.1.0 runtime 分离。
- 产品输出：`.artifacts/build/frontend`、`.artifacts/build/python`、`.artifacts/dist`。完整网页由 workspace/web 提供，不依赖 custom node 或扩展加载业务界面。
- 改名收尾隔离验收：`.artifacts/workspaces/docs-update`，网页 32588、领域服务 32590，不激活为默认 workspace。

目录改名后已按锁文件重新安装 dev，修复 editable 安装和命令入口；AstroPhotoFlow MCP、默认指针、编辑器和项目工具脚本中的有效旧路径已修正，其他 MCP 配置保持。本机固定工具入口为 `.artifacts/redesign/bin` 与其 Node 26 目录，不使用系统中版本不同的 Node/pnpm。

受限执行环境会将 LOCALAPPDATA 重定向到沙箱目录；本机维护使用正常用户环境访问已有 runtime，不修改产品路径解析，不新建另一套 CPU runtime。

2026-10-26 改名收尾已验证 dev 网页、HTTP、CLI 和真实 MCP 访问同一库，112 条存量资产在重启前后保持；这里的数量是当时观察值，不是后续固定验收条件。当时正常 dev 保持运行，隔离实例已停止，32588／32590 已释放。启动回执已修正为 `#/workflows`；需求归并未重新启停或核对实时服务状态。

原件、令牌、配置与锁文件保持；SQLite 主文件字节在启停后变化，但 17 张逻辑表与改名前快照的行级摘要一致，外键检查通过。运行与发行证据统一记录于[验证矩阵](test-matrix.md)。

wheel 源码目录外安装、无 Node 的 sdist 重建与重装已在改名收尾通过；需求归并未重新构建发行物。运行证据仍只覆盖 Windows／CPU，首次引导体验与 Linux 验收没有因此标为完成。

## 已取消的旧任务

不重建历史 restructure 验收环境，不恢复 redesign 实例或 `branch/redesign`，也不重新执行目录切换任务。

## 后续有效待办

- ②[器材型号搜索与未知型号手动录入](../requirements/README.md#equipment-model-search-enhancement)：待排期、未实现，不纳入当前 M2 验收。已确认范围、手填值优先、来源标记呈现、仅复用现有字段及本地 JSON 资料位置统一记录在需求入口；当前停止进一步设计和实现。
- M1已由用户确认通过并集成dev。M2的B21～B24已集成dev；自动回归、UI审计和独立功能验收通过，但M2用户Milestone批准及跨⑤真实运行联调仍待完成。B31进行中，Siril 1.4.4只读目录及单图拉伸原型已形成，仍缺有效同类序列处理、取消和完整验收；B41本地定义存储候选通过。B32计划／确认候选和SoftwarePanel已实现并通过定向自动检查，真实网页WebSocket与用户点击仍未验证；sandbox的`LOCALAPPDATA`重定向阻止访问真实用户runtime。其余12个Batch尚未开工，B56模型候选尚待实测锁定；不创建空适配或空路由，S0仍未整体验收。
- ①M1已补齐默认workspace、保存／采用值、自动端口／实际地址、真实启停／重启、最近控制结果及网页配置；②B21～B24已提供固定输入解析、文件变化确认、内部输出登记及只读移除范围。⑤活动运行输入保护、工作流影响提示、运行界面结果选择、记忆与完整比较仍待各自批次；原件／校准保护继续保留。
- ③锁定首个软件包、来源、准确版本和操作并真实验证安装／就绪；④推进共享可编辑定义、可选测试、更新影响确认、全参数新默认及变化端口重映射。
- ⑤按[统一阶段](../../src/astrophotoflow/modules/workflows/README.md#phases)形成原生当前图项目关联、自动保存／另存、活动网页MCP、当前控制、真实运行记录和逐图像节点自动预览任务；切图后拒绝迟到写，后台结果归原图，无网页只查询。
- 验证两类输入保证、实际目标范围、原生缓存机制、③调用及实际停止、运行持久保存和所选完整结果交②登记；未知先查询不重跑，不建额外图调度／转换／恢复框架。
- 精简MCP整体迁移58工具及Skill／参考／配置／真实客户端测试，Skill已知能力直达、需要时分型混合Top10和显式关键词降级；现有业务不遗漏，不留旧入口。
- S6保留跨软件、完整查看比较、固定结果显式续跑、本地偏好及Python／复合节点；节点导出安装和Judge实际接入另行规划，不前移首个闭环，不预建空接口。
- 后续实现须真实业务与客户端验收，历史FFmpeg跳过、Linux未验证和未完成业务项继续保留，不能把本轮文档检查或现有58工具当成产品闭环已交付。

第④阶段补充确认：新画布先选项目并原生保存，再交给Agent；同图控制按当前允许/撤销状态跨客户端共享，不区分客户端身份。由用户主动指定页面，已接管仍要明确交回，不新增临时图控制或客户端会话体系。

## 2026-10-28 12:34 UTC运行状态复核

只读`apf status --workspace .artifacts/workspaces/dev`返回stopped、ready=false、processes=[]。31388／31390及32588／32590／32592／32688／32690均无监听；Siril CLI已退出。`.artifacts/workspaces`中尚无G03隔离W1。既有B32 runtime overlay预检指出sandbox无法将隔离LOCALAPPDATA连到已核验的1.88GB用户Python venv；未复制、未链接、未初始化或启动运行时，也未改共享dev。

2026-10-28 B31数据目录重核：只读解析`tests/data/Astro_Dataset`全部29个文件（18 FITS、11 XISF）的主图元数据；没有解码或改写像素。记录了格式、尺寸／通道、位深／样本格式及存在的Object／Filter／曝光／设备／时间字段；主图类型均标为Master Light，目录没有两个可证实为同一目标、同一滤镜的原始观测帧，不能构造真实两成员序列。多图XISF中的额外layer不当作有序观测。旧逐项盘点见`.artifacts/implementation/B31/dataset-inventory.json`；本次全目录报告见`.artifacts/implementation/B31/astro-dataset-preflight-20261028.json`。

2026-10-28 12:40 UTC B31 XISF读取原型：Siril 1.4.4在隔离副本成功读取James Glucksman NGC2070 Ha XISF的单个integration layer，3854×3129；`bg`为0.003898，`bgnoise`为0.00007191，退出码0。只作读取／测量，无转换和输出。原件与副本处理后SHA-256同为`207c487ec7333e488717a99f9d770497a2f1b0585ced016acc900dcafb2894d2`。Object元数据缺失；文件名不作为目标确认依据。日志仍记录sandbox拒绝默认Pictures目录及Siril配置写入；图像读操作成功。证据在`.artifacts/implementation/B31/xisf-load-20261028-1240/`；此结果不证明序列支持或选定首操作。

2026-10-28 12:40 UTC运行状态复核：`apf status --workspace .artifacts/workspaces/dev`仍为stopped／ready=false／processes=[]，相关dev和隔离端口无监听，Siril CLI已退出；`.artifacts/workspaces`没有G03 W1。真实网页操作仍无可用候选运行页，未做安装或用户确认点击。

2026-10-28 B31命令覆盖矩阵更新：核对实际Siril CLI脚本后，将11条已观察命令的headless状态标为“CLI脚本中观察”，并补齐load、convert、seqstat及统计／控制命令的已知参数、输入输出和限制；完整语义、安全风险及依赖仍未完成。矩阵计数为199条官方目录、11条CLI观察、11条部分语义、0条完整语义、0条已确认registry加载、188条未执行。序列脚本仅转换Andrew M Weeks的B/G两滤镜文件并写两行stats.csv，`sample.seq`初次读取失败后Siril转写并使用`sample_.seq`，同时有bundled Python环境初始化错误；这不是同滤镜科学序列或叠加。证据仍是`.artifacts/implementation/B31/probe/sequence.log`、`output/sample_conversion.txt`和`output/stats.csv`。

2026-10-28 当前demo候选定向测试刷新：软件服务9 passed、节点定义9 passed、架构导入边界6 passed。为绕开sandbox下`uv`无法读写 interpreter cache 的问题，使用已存在`.artifacts/venvs/dev/Scripts/python.exe`，每个测试文件独立进程；三份日志和退出码见`.artifacts/implementation/B31/test-refresh-20261028-1253/`。合并同名`test_service.py`时只发生pytest collection冲突、未执行断言；未更改依赖或外部Python环境。

2026-10-28 B31参考目录复核：`reference/Siril_1.4.4`仅有`export.py`、README和requirements，没有预生成输出或科学数据。脚本`main()`会抓取可变`stable`页面并写入新的reference/output；dev venv未安装README要求的BeautifulSoup，因此未运行导出器、未改reference目录。已缓存并日期记录的官方HTML与当前vendor catalog继续作为本轮来源。

2026-10-28 当前demo候选前端定向验证刷新：软件UI包3个test file共5 passed，native page事件1个文件2 passed。使用repo固定Node 26.8.2和已安装Vitest直接入口，临时目录位于`.artifacts`；注入当前HEAD避免Vite对Git的子进程safe.directory报错。pnpm包装器隐式install遇SQLite拒绝、默认Temp导入失败及native首次运行Git提示均已保留在`.artifacts/implementation/B31/test-refresh-20261028-1253/`，不作为产品回归；无依赖安装／代码修改。

2026-10-28 13:03 UTC G03最新runtime preflight：只读访问用户LOCALAPPDATA可见完整固定CPU runtime及Python，但其marker `ec74c9e9…`与当前repo archive／manifest hash `c6c7a476…`不符。此前marker匹配只适用于B62同步archive前的旧候选。`--reuse-runtime`将失败；普通init会覆盖/重解压共享engine及尝试依赖安装，因此不执行。dev仍stopped，W1不存在，未启动或修改任何runtime。证据`.artifacts/implementation/B32/runtime-reuse-preflight-20261028-1303.json`。

2026-10-28 12:59 UTC运行复核：dev仍为stopped／ready=false／processes=[]，31388／31390及所查QA端口均无监听；隔离`implementation-qa-W1`不存在。Python与Vitest测试进程均已退出。未启动、安装或修改共享runtime。

2026-10-28 13:09 UTC sandbox auto-review拒绝对共享用户runtime的两文件临时切换（`ComfyUI/server.py`及`.apf-native-build`），理由是该动作写入workspace外共享runtime，且缺少针对精确操作的可信显式授权。拒绝后重新hash确认原件未变，dev仍stopped、无Python进程／相关监听、W1仍不存在；未走其他通道重试。备份、候选tree对比和拒绝原因见`.artifacts/implementation/B32/runtime-maintenance-backup-20261028-1305/`与`runtime-write-auto-review-rejection-20261028-1309.json`。G03待用户明确授权该可恢复维护操作，或提供匹配当前candidate的隔离runtime。

2026-10-28 B31输出端点诊断：直接读取原始FITS副本和baseline／三轮Auto Stretch输出。五份数组均无0值，且均恰有1个值等于1.0；`>=0.999`像素分别为1／77／59／62／47（输入／baseline／round1／round2／round3），每幅11,694,368像素。该结果没有显示拉伸新增的大面积全量程端点堆积，但不证明传感器未饱和，也不能解释可见光晕。完整分位数、hash和方法见`.artifacts/implementation/B31/pixel-clipping-diagnostics-20261028.json`；图像门槛仍因独立评审光晕3/5未通过。

2026-10-28 B31端点统计独立解读：GPT-6.1 Sol Low核对后认为每份输入/输出均恰有1个1.0值，近顶端像素占0.0000086%／0.000658%／0.000505%／0.000530%／0.000402%（输入／baseline／round1／round2／round3）；≥0.999不自动等于剪裁，且无空间分布不能解释光晕。其主观评分不变，光晕仍3/5。审查补充见`.artifacts/implementation/B31/image-review/sol-low-2026-10-28.md`；此数据不能证明原始传感器或校准科学性。

2026-10-28 13:18 UTC B31单图`stat`命令原型：准确Siril 1.4.4在隔离Ha FITS副本上执行默认`stat`及`stat main`，两组统计在stdout输出，脚本退出码0；日志在Python validation/embedded venv初始化报错后仍输出值，依赖影响未知，因此coverage记录为partial。原件与副本SHA-256相同；无变换、无输出文件。证据`.artifacts/implementation/B31/stat-probe-20261028-1320/`。Siril CLI矩阵现为12条已观察、12条部分语义、187条未执行；complete语义及registry load仍为0。

2026-10-28 B31 `stat`复测：相同hash输入副本、相同Siril 1.4.4脚本重跑后，默认和main两组统计值一致，未重复出现首次Python初始化错误；配置文件写入sandbox LocalAppData仍被拒。即使进程返回0，也将该命令维持partial，Python依赖影响未知。试图将进程LOCALAPPDATA改至artifact后，Siril仍走平台sandbox config路径，未改变用户设置；无用户路径写入。证据`.artifacts/implementation/B31/stat-localappdata-20261028-1320/`。

2026-10-28 B31端点坐标补充：Sol Low核对后确认唯一精确1.0值在输入与四个输出中均位于[y=2418,x=41]。输入中心邻域中位数0.676，拉伸后3×3邻域中位数0.9969–0.9987，说明该最大选取区域被压至接近上限但未新增精确上限点。它只描述左边缘的一个局部最大，不能判定该源为星、PSF或光晕，也不改变任何主观评分。完整剖面和独立解释见`.artifacts/implementation/B31/pixel-ceiling-profile-20261028.json`及image-review。

2026-10-28 B31静态参数补充：基于本地保存的1.4.4标记官方命令说明，结构化复核asinh、autoghs、binxy、ccm、crop的文档所载必填／可选参数、显式默认与范围；缺失的类型/范围仍标unknown。这五条未运行CLI、未生成Node，风险/依赖仍未个别审查。coverage现有17条部分语义、0条完整语义、12条实际CLI观察、187条未执行；准确逐项记录在`coverage-matrix.json`。

2026-10-28 B31科学序列命令静态复核：从已捕获的Siril1.4.4官方说明记录calibrate、calibrate_single、register、stack的显式默认值、参数及输入输出限制；特别标记校准帧、前序注册数据、sequence和输出副作用，未知类型／范围保持unknown。四项未在本地缺少同滤镜帧的素材上运行、未生成Node、依赖/安全仍未个别实测。coverage矩阵现21项partial semantics、0项complete；完整行在`.artifacts/implementation/B31/coverage-matrix.json`。

2026-10-28 B31静态参数审计增补：依据捕获的1.4.4官方命令说明，继续部分复核denoise、epf、fixbanding、fmedian、limit的明确参数/default/range。EPF文档中guided只用`-sc`与语法/其它段落的`-si`/`-ss`之间存在不一致，未猜测修正；五项均未执行CLI、未生成Node，风险和runtime依赖仍未知。coverage现26项partial、0 complete、12项实际CLI观察、187项未执行，具体未知项见coverage-matrix.json。

2026-10-28 B31目录静态复核续：按捕获的1.4.4官方说明补充conesearch、findcompstars、ght、linstretch、modasinh、mtf的已写明默认/范围/上下文；catalog查找命令潜在在线目录依赖未执行，风险和运行行为仍unknown。覆盖矩阵现32项partial semantic、0 complete、12项CLI观察、187项未执行；这些新增均为documentation-only，不是Headless/registry/runtime验证。

2026-10-28 B31 `jsonmetadata`实际CLI探针：在Ha FITS隔离副本运行`load`+`jsonmetadata -stats_from_loaded -out=metadata.json`，退出码0并生成118,686字节JSON，包含完整FITS headers与统计。Python validation错误在写文件前出现但数据仍输出；源/副本hash保持一致。报告含天体名、日期及潜在站点字段，保留在本地、不上传；安全风险尚未完整审计，未生成节点。逐字段摘要及hash见`.artifacts/implementation/B31/jsonmetadata-probe-20261028-1330/jsonmetadata-measurements.json`，全量JSON仅留在隔离artifact。

2026-10-28 B31 `jsonmetadata`输出核实：单Ha FITS副本成功生成118,686字节JSON，结构包含完整FITS headers和统计；全量文件保持本机隔离artifact，因headers含观测地点字段不上传。原件/副本SHA-256一致。Python validation错误先行记录，但JSON已写且CLI exit0；安全审查仅部分完成，不开放为节点。coverage矩阵现13 CLI observations、33 partial semantics、186 unexecuted，0 complete，count checks通过。

2026-10-28 B31命令目录静态风险补充：新增partial文档复核pyscript、pm、profile、find_hot、extract_HaOIII、pcc。pyscript按官方描述属于任意Python脚本执行，通用Node不生成；pcc/catalog可能访问远程目录，未运行；各类输出路径和风险未全面测试。Coverage共39条partial semantic、0 complete、13条CLI观察、186条未执行；runtime/registry状态仍独立标记。

2026-10-28 B31 PSF/platesolve目录复核：基于捕获的官方说明静态整理makepsf的模式、文件格式要求、Airy默认值及图像元数据依赖；platesolve的order/radius/limitmag/catalog和默认flip/crop行为。两者未运行、未生成节点，依赖及副作用风险仍部分unknown。coverage 41 partial semantics、0 complete、13 CLI observations、186 unexecuted。

2026-10-28 B31 sequence/CFA/PSF命令静态复核：基于捕获的1.4.4官方说明更新cosme、linear_match、parse、split_cfa、seqapplyreg、unsharp、wavelet的语法参数和文件/序列语义；读写副作用、范围及前置行为不清处继续标unknown，七项都未执行CLI/生成Node。Coverage矩阵现48项partial semantics、0 complete、13 CLI observations、186未执行，计数校验通过。

2026-10-28 B31 resampling/composition/export静态复核：基于捕获官方说明更新resample、rotate、rgbcomp、savejpg、savejxl、seqfindstar的参数/输出语义；质量范围、文件名/覆盖、插值默认等未说明之处保持unknown，六项未运行CLI/生成Node。Coverage矩阵现54项partial semantic、0 complete、13项CLI观察、186未执行；检查通过。

2026-10-28 B31去噪/重建/色彩命令静态复核：基于捕获官方说明补充rl、sb、rmgreen、satu、rgradient、seqpsf的已说明参数、默认与上下文。PSF状态、颜色适用、序列注册数据、headless坐标要求中未核实部分仍unknown；未运行或生成Node。Coverage矩阵60项partial semantic、0 complete、13项实际CLI、186项未执行，count/duplicate校验通过。

2026-10-28 13:52 UTC B31命令静态复核续：依据已保存的Siril 1.4.4官方说明补充seqght、seqmerge_cfa、seqmodasinh、setfindstar、setmem、setcpu、setcompress、setphot的文档参数及输入／状态语义；Bayer序列成员数、几何、位深、通道顺序等限制保留，输出覆盖行为、未写明默认及运行依赖保持unknown。八项均未运行CLI、未生成Node、未加载registry。coverage矩阵现68项partial semantic、0 complete、13项实际CLI、186项未执行；完整安全风险审查仍为0。13:52 UTC复查官方Commands页仍明确列出1.4.4，尽管当前官方下载页已发布1.4.5；stable路径不单独视为版本锁。页面获取时间、版本说明和SHA记录在coverage-matrix.json与test-matrix.md。

2026-10-28 13:55 UTC B31 Non-scriptable命令静态审计：按1.4.4官方目录逐项补充18个Non-scriptable命令的语法／参数、图像或序列上下文、文件与GUI结果、平台限制及可见依赖；new的可选filename持久化含义、倾斜测量前置及多数数值范围仍保留unknown。全部仅source review，未运行CLI、未生成Node、未加载registry，安全风险未评估。coverage矩阵现86项partial semantic、0 complete、13项实际CLI、186项未执行；18条官方限制单独列在test-matrix.md。

2026-10-28 13:58 UTC B31控制／序列命令静态审计：依据捕获的1.4.4官方目录部分复核capabilities、get、getref、help、pwd、select、seqclean、seqheader、set、set16bits、set32bits、setext、setref、unselect。明确选择区间端点、序列引用编号、seqclean默认全清、seqheader可写CSV、INI设置导入及位深／扩展名状态；持久化范围、路径覆盖及参数无效行为仍unknown。14项均未运行CLI、未生成Node、未加载registry。coverage矩阵现100项partial semantic、0 complete、13项实际CLI、186项未执行；安全风险完整审查仍为0。

2026-10-28 13:59 UTC B31图像导出命令静态审计：按Siril 1.4.4官方说明部分复核savebmp、savepng、savepnm、savetif、savetif32、savetif8的参数、像素位深、扩展名和压缩选项；覆盖、路径、通道转换细节及失败行为未知。仅source review，未运行CLI或生成Node。Coverage现106项partial semantic、0 complete、13项CLI观察、186项未执行；输出风险未完整审查。

2026-10-28 13:59 UTC B31文件输入与FITS元数据静态审计：按官方1.4.4说明复核convertraw、link、merge、merge_cfa、dumpheader、split、update_key、sequpdate_key的输入筛选、顺序、输出与FITS关键字行为；其中update_key不验证值、sequence更新不支持SER，split语法和正文对-lab拼写不完全一致，文件覆盖及持久化保持unknown。八项均未运行CLI或生成Node。coverage现114项partial semantic、0 complete、13项CLI观察、186项未执行，安全审查仍未完成。

2026-10-28 14:00 UTC B31 CFA校正与提取命令静态审计：按1.4.4官方目录复核cosme_cfa、find_cosme、find_cosme_cfa、fix_xtrans、grey_flat、extract、extract_Green、extract_Ha的参数、CFA条件、修改行为与派生输出。Green/Ha输出前缀及尺寸已记录；输出目录、覆盖、未说明范围和小波平面文件语义仍unknown。八项均未运行CLI、未生成Node。coverage现122项partial semantic、0 complete、13项CLI观察、186项未执行。

2026-10-28 14:01 UTC B31算术与图像状态命令静态审计：按官方1.4.4目录部分复核fdiv、fmul、iadd、idiv、imul、isub、neg、nozero、offset，记录像素公式、ADU、明示16／32位截断与偏好依赖；维度兼容、标量边界和除数为零仍unknown。九项均未运行CLI或生成Node。coverage现131项partial semantic、0 complete、13项CLI观察、186项未执行，安全评估未完成。

2026-10-28 14:01 UTC B31图像分析与方向变换静态审计：按捕获的1.4.4官方说明复核cdg、clahe、entropy、gauss、log、mirrorx、mirrorx_single、mirrory、rotatePi、threshlo、threshhi、thresh。记录统计前置、公式、轴向及阈值影响；mirrorx_single的条件原地覆盖是明确写入风险，threshhi语法拼写及thresh双参数说明不一致均保持未解。12项仅source review，未运行或生成Node。coverage现143项partial semantic、0 complete、13项CLI观察、186项未执行。

2026-10-28 14:02 UTC B31目录检索与色彩配置静态审计：按Siril 1.4.4命令说明部分复核catsearch、offline、online、icc_assign、icc_convert_to、icc_remove、spcc、spcc_list。记录SIMBAD/IMCCE远程回退及图像header时空字段、在线模式、profile路径、SPCC Gaia DR3选择及显式默认。未运行查询或颜色校正，风险、网络具体请求、catalog可用性及配置持久性仍未验证。coverage现151项partial semantic、0 complete、13项CLI观察、186项未执行。

2026-10-28 14:03 UTC B31复原与星点操作静态审计：依据官方说明部分复核invght、invmodasinh、invmtf、starnet、subsky、synthstar、unclipstars、unpurple、wiener、wrecons。starnet需外部程序，PSF/小波等上下文依赖、输出路径和位深行为未运行验证；unpurple语法未列正文使用的-mod=，保持歧义。十项仅source review，未运行CLI、未生成Node。coverage现161项partial semantic、0 complete、13项CLI观察、186项未执行，完整安全评估仍为0。

2026-10-28 14:04 UTC B31序列CFA与校正包装命令静态审计：按1.4.4官方说明部分复核seqccm、seqcosme、seqcosme_cfa、seqcrop、seqextract_Green、seqextract_Ha、seqextract_HaOIII、seqfind_cosme、seqfind_cosme_cfa、seqfixbanding，记录选中成员、前缀、CFA/Bayer信息及明确尺寸／参数。没有可用的同滤镜序列；输出覆盖、帧级失败和有效科学范围未运行验证。十项仅source review，未生成Node。coverage现171项partial semantic、0 complete、13项CLI观察、186项未执行。

2026-10-28 14:05 UTC B31序列变换、校正与测量命令静态审计：按1.4.4官方目录部分复核seqinvght、seqinvmodasinh、seqlinstretch、seqmtf、seqprofile、seqplatesolve、seqresample、seqrl、seqsb、seqsplit_cfa。记录序列输出、注册/头部副作用、默认及适用条件；seqresample syntax未列正文中的-maxdim=，保持歧义。无可用同滤镜序列，十项均未运行或生成Node。coverage现181项partial semantic、0 complete、13项CLI观察、186项未执行。

2026-10-28 14:05 UTC B31剩余命令目录静态审计：部分复核boxselect、exit、ffill、fftd、ffti、fill、histo、light_curve、livestack、psf、seqstarnet、seqsubsky、seqtilt、seqwiener、stackall、start_ls、stop_ls、trixel，补全选择、文件副作用、运行前置和状态限制。所有199个目录行现有至少partial source/runtime语义记录；仍是0 complete semantic review、13 CLI observations、186 commands unexecuted、0 fully assessed security risks。`seqwiener`的syntax/heading mismatch仍开放；未运行LiveStack、StackAll或StarNet。

2026-10-28 14:11 UTC B31 unclipstars真实单图实验：以copy的Round 2 FITS运行Siril 1.4.4 unclipstars并另进程回读，CLI显示179颗星去饱和、保存和回读均exit0；输出主HDU的11,694,368个像素与输入完全相同，500星上限样本的median FWHM、轴比、RMSE和Sat比例全部与Round 2相同。仅DATE更新且新增ICCProfile HDU；因此没有可测图像改善。PNG导出日志报告无法创建Python venv但仍写出unclipstars-preview.png.png；Siril预览方向与既有fixed-0–1预览相反，改用同尺度FITS数组生成比较预览，像素差最多1级量化。具体命令、日志、hash和测量见`.artifacts/implementation/B31/unclipstars-20261028/`。

2026-10-28 14:15 UTC B31 GHT高光保护试验：真实Siril 1.4.4对复制的线性IC 1805 Ha master-light执行`ght -D=4 -HP=0.8`，保存并二次CLI回读/bg/bgnoise/findstar成功；输入散列保持固定，输出尺寸/位深和有限像素已核对。500星截断样本FWHM变化不能解释为光学PSF改善；Sat标记由Round 2 35.4%升至59.2%，且固定0–1预览更暗。独立Sol Low视觉复审已发起，结果待回；在评审前不采用、不宣称改善。close阶段仍报sandbox config rename错误但CLI退出0。完整证据在`.artifacts/implementation/B31/ght-hp08-20261028/`。

2026-10-28 14:18 UTC B31 GHT独立图像复评：GPT-6.1 Sol Low独立查看Round 2、GHT D4/HP0.8与D6/HP0.8固定范围预览，Round 2优先；overall分别4/5、2/5、3/5。D6弱结构可见度5/5，但star core/halo2、background2，未通过质量门。D6 exact 1.0像素2260、≥0.999像素5758（输入均1）；这仅证明输出端点堆积，不能定位具体星体或证明传感器饱和。报告在`.artifacts/implementation/B31/image-review/sol-low-ght-20261028.md`。

2026-10-28 14:22 UTC B31 GHT D5及HP参数复评：Sol Low对D5/HP0.8评overall4、halo/core3、background4、faint structure4，仍略偏Round 2；D5 stored endpoints为773 exact 1.0、2047≥0.999（输入各1）。同D5仅改HP 0.8→0.6的运行产生逐像素完全相同主HDU，记录为无效参数变化，不视作新效果。GHT各候选仍未达到全部关键项≥4，Round 2 halo也仅3/5；质量门未过。独立报告`.artifacts/implementation/B31/image-review/sol-low-ght-d5-20261028.md`，试验均在各自隔离目录。

2026-10-28 14:28 UTC B31 asinh单图试验：在同一线性Ha master副本上运行Siril 1.4.4 asinh stretch100/500/1000、offset0，保存并分进程readback/bgbgnoise/findstar；输出均finite 32-bit。背景值从0.0252升到0.1450，噪声0.000738升到0.002973，exact-1均1，≥0.999为2/3/4。固定0–1预览均较Round 2暗，尚待Sol Low独立评分；stretch100有Python venv初始化/验证错误，但CLI后续统计退出0。无序列、无彩色结果，质量门尚未过。证据在`.artifacts/implementation/B31/asinh-*-20261028/`。

2026-10-28 14:29 UTC B31 Asinh独立图像复评：Sol Low独立查看Round 2及Asinh100/500/1000固定范围实际预览，overall分别4/1/2/3，Round 2优先；Asinh1000较好地缓解darkness但弱结构仅3/5，未通过全部≥4门槛。星点/halo对1000为4/5；mono color不可评。端点exact1均1、≥0.999为2/3/4，不能证明无高光压缩。评审与限制`.artifacts/implementation/B31/image-review/sol-low-asinh-20261028.md`。

2026-10-28 14:34 UTC B31官方样例来源预检：官方[Free-Astro Siril样例页](https://free-astro.org/download/colmic/)列出Lights `Brutes_180s.zip`（528 MB）以及H-Alpha + O-III双带Lights `Brutes_HOO_180s.zip`（546 MB），并称与Astrosurf文件相同。页面未列单帧目标／滤镜／成员数／校验散列；未下载或检验内容，不能据此宣称为兼容同滤镜序列。用户的数据来源选择仍待答。

2026-10-28 14:35 UTC B31剩余网络/元数据风险静态核对：按官方说明细化offline的cached data保留、seqpsf的用户导出坐标／光度数据、show的CSV名称／坐标展示及spcc的Gaia数据来源不确定性。均为source-only，不评为安全通过；完整安全风险审查计数仍为0，另外大量本地路径／文件及科学数据副作用仍未实测。

2026-10-28 14:36 UTC B31序列操作安全副作用静态审计：根据官方描述为28个此前security_risk未逐项核对的序列命令补充source-based副作用说明，涵盖派生文件／多输出、caller-named CSV/header数据、目录全组处理以及选择/注册/photometry状态改变。覆盖/覆写/逐帧失败、路径边界、privacy和状态持久性仍未实测；完整security评估计数仍为0，未将静态备注冒充安全验收。详细逐行记在`.artifacts/implementation/B31/coverage-matrix.json`。

2026-10-28 14:37 UTC B31内存变换与状态设置风险静态核对：按命令说明细化30条内存图像变换、选择/测量状态、ICC配置及位深/扩展名设置的潜在数据完整性／后续作用说明。边界均为source-only：保存覆盖、设置持久性、文件路径/profile读取和外部影响仍未逐项验证，完整安全评估数仍为0。逐项内容在coverage-matrix.json。

2026-10-28 14:40 UTC B31单图读取与内存变换风险静态审计：对25项读文件、改内存图像、临时选择、统计或退出命令补充基于官方描述的路径／覆盖／数据完整性副作用；`findstar` caller CSV及ICC profile path单独标注。无外部运行或文件路径探针；完整安全评估数仍为0，持久化/无效输入/竞态行为继续unknown。

2026-10-28 14:42 UTC B31剩余GUI和图像状态风险静态审计：基于官方说明补充36项剩余的current-image、sequence context、GUI display及photometry state操作风险，包括文件读取、local console输出、session结束、profile/sequence依赖和pixel integrity。均为source-level notes；invalid inputs, output persistence, path containment and runtime behavior remain untested, so full security assessment count remains 0.

2026-10-28 14:42 UTC B31命令目录风险备注覆盖完成：Coverage matrix现199/199条`security_risk`均不再使用generic not_individually_reviewed占位；静态说明覆盖文档可见的文件/网络/外部进程/状态/像素风险及未验证点。`security_risks_individually_assessed`仍0，因为没有完成逐项实现边界、运行/路径/权限审查；不能据此开放任一高风险节点或宣称安全验收。

2026-10-28 15:11 UTC B31逐命令评估可见性接入：新增哈希绑定的Siril 1.4.4 assessment sidecar并将`SirilCommand.assessment`加入HTTP/OpenAPI DTO；SoftwarePanel可展开参数、默认范围、上下文、I/O、headless、依赖、风险、节点/registry/runtime状态，搜索覆盖这些字段。`pyscript`风险可见，通用未验证状态保持明显。Python software 9 passed、architecture 6 passed、私有UI目录/客户端2 passed、UI包typecheck通过，OpenAPI已生成。Vite bundle候选在实际Node24.22下7111 modules通过并存于`.artifacts/implementation/B31/assessment-build-node24-rerun-20261028/`；项目要求Node≥26.8.2，当前可用Node未满足，完整B62/目标版本build和打包验收未通过。

2026-10-28 15:25 UTC B31外部wheel assessment smoke：使用现有wheel构建工具后，wheel-resource verifier检查sidecar通过；uv pip install --offline --no-config --no-deps --target装入repository-external授权临时目录，dev-Python依赖环境下从该target导入，读到199条命令和pyscript高风险assessment。报告在.artifacts/implementation/B31/assessment-wheel-external-20261028.json。这是无依赖隔离的backend resource smoke；wheel使用旧web assets，仅代表中间包候选；当前界面后来随B62 v6 package重新验证。

2026-10-28 15:48 UTC B31真实HTTP命令目录smoke通过：在隔离`.artifacts` workspace先用项目`upgrade_database`建立schema 0009，再以临时Bearer token启动真实APF FastAPI/Uvicorn于127.0.0.1:32785；GET `/api/v1/software/packages/siril/versions/1.4.4/commands` 返回200、199条、199个唯一command，且`pyscript` assessment存在。请求完成后API进程停止；普通dev APF仍stopped、无ComfyUI进程。响应、stdout／stderr及请求结果见`.artifacts/implementation/B31/http-command-catalog-smoke-migrated-20261028/`。早期sandbox启动停在Windows Proactor `socketpair`，未经确认不再归因；全量B31与网页／节点／Siril闭环仍未通过。

2026-10-28 16:05 UTC B62发行资源预检更新：确认固定Node 26.8.2及pnpm 11.13.1可用，根`pnpm build`通过（7111 modules、Python UI／原生应用类型检查通过），日志`.artifacts/implementation/B62/root-build-node26-20261028.log`；engine归档hash与manifest匹配。最终网页构建之后重新打包v6 wheel/sdist，updated verifier仓库外安装wheel通过；Node从PATH移除时，外部sdist解包、wheel重建及再安装smoke均通过。完整报告`.artifacts/implementation/B62/packaging-report-final-v6-node26-20261028.json`，记录wheel/sdist/重建wheel SHA及外部路径。无隔离build依赖下载（setuptools 78.1预装解释器，`sdist_build_isolated=false`），未安装或更新共享Python环境依赖，完整release wrapper、B61、B62 Ready条件和M6用户验收未完成。v5曾因Temp权限及旧bundle与最终asset不一致失败，失败记录已保存；v6最终检查通过。共享ComfyUI runtime及dev workspace未启动／改写；整体目标仍未完成。

2026-10-28 16:15 UTC Sol Low独立源码／报告复核`verify_distribution.py`新sdist hash字段及v6报告：无具体正确性发现，独立重算wheel、sdist和rebuilt wheel SHA均匹配。`tests/packaging/test_layout.py tests/packaging/test_engine_build.py`另 **3 passed**（写入限于tmp_path）。review未重跑外部安装或Node-free构建；这些结果不替代B62整卡或完整用户验收。

2026-10-28 16:16 UTC B31 Auto Stretch Round 4：准确Siril 1.4.4在隔离副本运行`autostretch -linked -3.0 0.18`，仅将Round 2 target background 0.22改为已试过的0.18；处理与readback退出0，原件和副本hash一致，4144×2822单通道32-bit有限输出hash `03f7e5213607325d807fa6693a5d0cd470f4cb3bae2ac990b98b74a08bfdfcf3`。背景／噪声为0.1801／0.005939，500星样本FWHM 4.944625。Sol Low独立评分：背景4、弱结构3、core/halo3、噪声3、星形/锐度4、整体4；略偏Round 2，质量门仍未过。预览、日志和评审见`.artifacts/implementation/B31/round4-targetbg018-20261028/`与`image-review/sol-low-round4-targetbg018-20261028.md`。不代表首操作获用户选择。

2026-10-28 16:20 UTC B31 Asinh clipmode复测：同一线性Ha副本真实运行`asinh 1000 0 -clipmode=globalrescale`并单独回读，均退出0；与默认clipmode的asinh1000主HDU形状／位深和像素值逐个相同，0个不同像素，最大绝对差0，仅DATE header不同。该命令模式在单通道素材上没有新图像效果，不作为独立质量轮次。比较散列见`.artifacts/implementation/B31/asinh-globalrescale-20261028/pixel-comparison.json`。
2026-10-28 16:23 UTC G03共享runtime只读复核：current repo archive／manifest SHA均为c6c7a47611f87867a0a45aca1f42ea6b4fd37cbd086067135de9484e38f7e224；用户runtime marker仍为ec74c9e959ac26a9ef35c77ce9a128e6a197b615635feab5ea8d5cfc20d03a3f，旧marker不匹配。runtime server SHA 5f6a8d8905281f17588c8313f6f9531ee7648f78fe3383c7e24c1d4bdfe9dcff与candidate server 04ff7a0d6d9e8f313697d4dea58945c41be770d2b752a1eefef78b58ac6bea18不同；Python与ComfyUI主文件存在。未初始化W1、启动或修改runtime。证据见 .artifacts/implementation/B32/runtime-marker-current-readonly-20261028-1623.json。

2026-10-28 16:26 UTC B31 Auto Stretch Round 5：在同一Ha master-light隔离副本运行`autostretch -linked -3.0 0.20`，相对Round 2只将target background 0.22调至已测0.18／0.22之间的0.20；CLI和readback退出0，原件hash维持`79734c29…`，输出有限4144×2822单通道32-bit，hash `cba7b6d4955b65d6495b93b722c1d099f67d4521aaba8b5f4cc69039e33edf9e`。背景／噪声0.2001／0.006430，FWHM 5.080234，exact-1为1、≥0.999为59。Sol Low评分：背景4、弱结构4、core/halo3、噪声3、星形/锐度4、整体4；仅轻微差异，仍未通过质量门。证据和固定范围预览见`.artifacts/implementation/B31/round5-targetbg020-20261028/`，评审见`image-review/sol-low-round5-targetbg020-20261028.md`。

2026-10-28 16:31 UTC B31真实降噪实验：在隔离线性Ha副本用Siril 1.4.4 `denoise -nocosmetic`后沿用Round 2 stretch作比较。NL-Bayes记录bgnoise从输入0.00003994降为0.00001397；原件hash未变，有限32-bit输出，CLI/readback及stretch均exit0。默认及`-nocosmetic`日志都有Python validation failed／no suitable data in src fits，尽管NL-Bayes完成并保存；必须保留为运行限制。Sol Low独立评分去噪版noise与faint各4，halo/core与background各3，overall4；整体略偏去噪版但质量门仍未过，运行健康也未验证。证据、预览及评审见`.artifacts/implementation/B31/denoise-nlbayes-default-20261028/`、`denoise-nocosmetic-20261028/`、`image-review/sol-low-denoise-nocosmetic-20261028.md`。

2026-10-28 16:32 UTC B31去噪与Asinh组合候选：真实CLI在隔离副本串行执行`denoise -nocosmetic`及`asinh 1000 0`；处理、写入、单独尺寸／位深／有限值回读均exit0，原件hash未变，背景／噪声0.1447／0.0008056。Sol Low评分为halo4、背景4、噪声4、弱结构3、星形/锐度4、整体4；较安静背景仍压低弱上/左发射，质量门未过。denoise日志的Python validation／no-suitable-data错误及缺少组合星点profile仍是实际限制。证据与评审见`.artifacts/implementation/B31/denoise-asinh1000-20261028/`、`image-review/sol-low-denoise-asinh1000-20261028.md`。

2026-10-28 16:37 UTC B31去噪调制中点候选：使用Siril 1.4.4文档参数`denoise -nocosmetic -mod=0.5`串行接`asinh 1000 0`；CLI/readback exit0，原件hash未变，有限32-bit输出，背景／噪声0.1448／0.001770，exact-1为1、≥0.999为4。无findstar数值以避免再次触发Python venv健康错误；denoise仍报告no-suitable-data。Sol Low比较完整denoise后Asinh与m=0.5 Asinh，认为m=0.5未可信恢复弱结构、noise回升，Round 2仍较易读。质量门仍未过，评审见`.artifacts/implementation/B31/image-review/sol-low-denoise-mod050-asinh1000-20261028.md`。

2026-10-28 16:39 UTC B31 DA3D detail-stage候选：Siril 1.4.4真实运行`denoise -nocosmetic -da3d`后接`asinh 1000 0`，日志报告DA3D完成；输出/readback exit0、原件hash未变、有限32-bit FITS，background／noise 0.1447／0.0007404。no-suitable-data错误仍在日志内；未运行findstar。Sol Low评分：core/halo、background、noise各4，faint structure3、stars/sharpness4、overall4；Round 2仍更易读，质量门未过。评审见`.artifacts/implementation/B31/image-review/sol-low-denoise-da3d-asinh1000-20261028.md`。
2026-10-28 16:50 UTC B31 denoise目录状态更正：Siril 1.4.4 default、-nocosmetic、-mod=0.5及DA3D CLI输出均单图保存／readback，但记录Python validation／no suitable data错误；assessments sidecar改为partial_cli_output_verified_logged_errors，headless标为脚本观察，manifest SHA B5AA3071…，coverage现17命令CLI观察／182未执行／12 successful／5 partial，完整语义／安全评估仍0。software service tests 9 passed，日志.artifacts/implementation/B31/denoise-assessment-service-tests-20261028.log。B62 v7已用新sidecar重建并仓库外验证通过；报告和限制见test-matrix.md的B62预检。

2026-10-28 17:01 UTC Sol Low指出并修正denoise sidecar两处事实错误：coverage证据路径原指向不存在的default目录，现在转向确实存在的no-cosmetic比较报告；node definition/generation reason改为承认partial CLI证据、同时解释单图序列边界和日志错误为何仍不足以定义安全通用节点。sidecar／manifest／coverage SHA重核一致为9B3744F7…，denoise证据路径全存在；修正后software service **9 passed**。更新后重建v8 wheel/sdist并verify仓库外安装及Node-free重建通过，报告`.artifacts/implementation/B62/packaging-report-final-v8-denoise-review-20261028.json`；隔离build依赖和B61/B62正式门仍未通过。
2026-10-28 17:01 UTC B31 denoise assessment review fixes：coverage evidence path was corrected to the existing no-cosmetic comparison; node-generation reasons now distinguish partial single-image evidence from sufficient safe contract. Current sidecar/manifest/coverage SHA is 9B3744F773344DAEA4ECE229BE6608327422945DC338D2C999B6560DB88B0794; 17 CLI-observed, 182 unexecuted, 12 success, 5 partial, 5 science-scope limits by the declared explicit-field/status rule. Post-fix software service test 9 passed; v8 wheel/sdist verification passed. Sol Low recheck of the corrected scope count is pending.
2026-10-28 17:05 UTC Sol Low二次复核denoise catalog修复：无剩余问题；coverage中的science-scope计数按明确predicate计算为5（convert, denoise, findstar, jsonmetadata, seqstat），所有denoise evidence paths存在，sidecar／manifest／matrix hash一致。审查结果见.artifacts/implementation/B31/denoise-catalog-review-resolution-20261028.json。
2026-10-28 17:11 UTC B31更新后的真实HTTP GET：隔离APF app先迁移schema 0009，再在127.0.0.1:32786查询命令目录，返回200／199唯一命令，denoise partial_cli_output_verified_logged_errors、headless observed及node not_generated状态均正确。该API进程随后停止；dev与ComfyUI仍stopped。报告 .artifacts/implementation/B31/http-command-catalog-smoke-denoise-20261028/http-smoke-result-r2.json；首次因测试harness重复mkdir失败已保存并纠正。
2026-10-28 17:18 UTC B62当前文档／catalog发行包v9：采用准确Node26生产前端资源和denoise sidecar hash 9B3744F7…；wheel仓库外安装与Node-free sdist重建／再安装均通过，完整散列及限制在.artifacts/implementation/B62/packaging-report-final-v9-current-docs-20261028.json。构建非隔离（setuptools 78.1预装），B61未通过，因此仍是B62部分预检，不是B62完成。
2026-10-28 17:21 UTC B31 SOS参数观察：denoise -nocosmetic -sos=1串行接Asinh1000在Siril 1.4.4 CLI exit0并保存/readback；日志未记录SOS阶段，主像素与无SOS denoise→Asinh输出完全一致。此值没有证明SOS生效，迭代范围仍unknown。证据.artifacts/implementation/B31/denoise-sos1-asinh1000-20261028/sos1-null-result.json。
2026-10-28 17:30 UTC B31 SOS1试验状态纳入sidecar后：SOS1试运行exit0但无SOS stage日志，像素与无SOS组合完全相同；sidecar／manifest／coverage SHA为0C637F1A…，scope count按显式规则为5。service test 9 passed，package v10外部／Node-free验证通过。已更新catalog的真实HTTP smoke于127.0.0.1:32786，GET 200／199唯一并返回SOS1无效果说明；API进程已停，未启ComfyUI。当前证据和限制见test-matrix.md。
2026-10-28 17:35 UTC B62 current-docs v11 package: after the SOS1 null-result and HTTP-smoke docs, rebuilt wheel/sdist in .artifacts/implementation/B62/dist-final-v11-sos-http-docs-20261028/; external wheel install and Node-free sdist rebuild/reinstall passed. Report .artifacts/implementation/B62/packaging-report-final-v11-sos-http-docs-20261028.json. Build remains non-isolated; B61 has not passed so B62 is still partial.
2026-10-28 17:37 UTC Sol Low复核SOS1更新后的denoise sidecar/coverage：无剩余发现；sidecar、manifest、matrix SHA一致，计数17 CLI观察／182未执行／12成功／5 partial／5 science-scope，所有denoise证据路径存在；review未重跑CLI、HTTP或package。报告见.artifacts/implementation/B31/image-review/sol-low-denoise-catalog-sos1-review-20261028.md。
2026-10-28 17:40 UTC B62 v12 preflight：在SOS1 null-result与Sol Low review文档之后重建当前wheel/sdist，仓库外wheel安装与Node-free sdist重建／再安装均通过。报告.artifacts/implementation/B62/packaging-report-final-v12-sos-review-docs-20261028.json；非隔离setuptools78.1构建，B61未通过故B62仍partial。

2026-10-28 17:46 UTC B31 SOS2审查顺序修正后重建v14 wheel/sdist；仓库外安装和Node-free重建／再安装通过，报告.artifacts/implementation/B62/packaging-report-final-v14-sos2-order-20261028.json。构建仍非隔离，B61未通过，B62不完整。
2026-10-28 17:46 UTC B31 SOS2部分试验：denoise -nocosmetic -sos=2后接Asinh1000在Siril 1.4.4退出0、输出有限并readback成功，但ensurepip创建内部Python venv失败先于第1/2轮完成日志，且未见第2轮日志；不把部分结果作为完整SOS或质量候选。范围仍unknown。证据.artifacts/implementation/B31/denoise-sos2-asinh1000-20261028/sos2-trial-comparison.json。sidecar已反映partial状态，新的service test9项通过。

2026-10-28 18:03 UTC B31 SOS2更新后真实HTTP smoke：隔离schema-0009 APF应用在127.0.0.1:32786返回200、199条唯一命令，denoise说明同时包含SOS=1无效果及SOS=2错误先于第1/2轮日志的顺序，自动断言通过。为完成loopback GET使用了本地权限提升；服务随后退出，普通dev与ComfyUI未启动或修改。初始断言字面错误、CIM查询受限及未提权socket失败均保留在该目录的独立证据中；成功报告为.artifacts/implementation/B31/http-command-catalog-smoke-denoise-20261028/http-smoke-result-sos2-order-r3.json。该HTTP结果只验证当前assessment目录响应，不证明SOS完整运行、节点生成/加载或图像质量门通过。

2026-10-28 18:14 UTC B62 current-docs v15本地预检：isolated `--installer uv`构建在获取setuptools 77.0.3时因PyPI DNS失败、尚未开始package build；另用Python 3.12.4、现有setuptools 78.1.0与build 1.6.1执行no-isolation构建成功。仓库外wheel安装及移除Node PATH后的sdist重建／再安装通过，report为.artifacts/implementation/B62/packaging-report-final-v15-no-isolation-http-docs-20261028.json；wheel／sdist／rebuilt wheel SHA见test-matrix B62记录。sdist内当时current-context与test-matrix均与工作文件字节一致。构建临时改写的src/astrophotoflow.egg-info/SOURCES.txt已从原snapshot恢复，所有六个egg-info文件hash一致。该预检不等于隔离构建成功，B61未通过故B62仍非Ready。

2026-10-28 18:21 UTC B62 current-docs v16 packaging preflight：隔离`python -m build --installer uv --wheel --sdist`成功，临时环境安装setuptools 84.2.1；随后仓库外wheel安装及Node-free sdist重建／再安装通过。报告.artifacts/implementation/B62/packaging-report-final-v16-isolated-current-docs-20261028.json；wheel／sdist／rebuilt wheel SHA见test-matrix。Verifier中的sdist rebuild使用现有native Python和setuptools 78.1，`sdist_build_isolated=false`，未安装共享依赖；当前matrix/context在构建时与sdist字节一致。构建改写的egg-info SOURCES.txt已从原snapshot恢复，六文件hash重新一致。B61未完成，B62仍未Ready。

2026-10-28 18:24 UTC B62 OpenAPI snapshot核对：用与`scripts/export_openapi.py`相同的隔离`create_app().openapi()`生成方式，当前docs/api/openapi.json经CRLF→LF标准化后与live JSON字节一致，解析对象也一致；未重写追踪文件。报告.artifacts/implementation/B62/openapi-snapshot-v16-20261028.json。

2026-10-28 18:25 UTC B62 OpenAPI与独立评审：只读`app.openapi()`生成与docs/api/openapi.json解析对象一致，CRLF→LF标准化后字节一致；报告.artifacts/implementation/B62/openapi-snapshot-v16-20261028.json。GPT-6.1 Sol Low独立复算v16 wheel、sdist、rebuilt wheel三散列并审阅build log、资源/文档及egg-info恢复，无具体发现；审查未重跑build、测试或runtime，不等于B62完成。审查记录.artifacts/implementation/B62/sol-low-v16-packaging-review-20261028.md。

2026-10-28 18:39 UTC B31 GHT SP扫参与目录联调：沿用同一线性Ha副本、固定D5/HP0.8，SP=0.1/0.01/0.005/0.001各自Siril 1.4.4处理及readback exit 0、输出有限、原件SHA保持。SP0.1/.01/.005压低暗弱星云；SP0.001接近SP0但halo无可信改善。Sol Low同尺度评审确认无候选全项>=4，Round 2略优；详见 `.artifacts/implementation/B31/image-review/sol-low-ght-d5-sp01-20261028.md`。第一个SP0.1文本采集GBK解码失败，产物已回读；新隔离重跑exit0且primary pixels完全相同，首次exit仍unknown。侧车assessment更新SHA C02BF2237552EA77EEDD726D503597588B108A50C1B08EDF33AB44FFD40EE015，service 9 passed。当前目录GET 200/199唯一，GHT+SOS事实检查由保存的HTTP响应复核通过；两次harness误报原因和报告在ght-sp目录，服务已停。B31/G02仍未Ready，首次操作及双帧输入仍待用户决定。

2026-10-28 18:46 UTC B62 v17b当前文档/sidecar preflight：v17隔离build前一轮因PyPI DNS失败，保留`.artifacts/implementation/B62/build-final-v17-ght-sp-20261028.log`；v17b经scoped network以setuptools 84.2.1隔离构建成功。仓库外wheel及无Node sdist重建／再安装通过，report `.artifacts/implementation/B62/packaging-report-final-v17b-ght-sp-20261028.json`。内容检查确认wheel assessment bytes与当前源码相同、manifest hash匹配，sdist中构建时matrix/context逐字节一致；`src/astrophotoflow.egg-info`六文件已恢复。Sol Low v17b审查待回；B61未通过，B62仍未Ready。

2026-10-28 18:50 UTC B31 GHT SP/LP证据收敛：Sol Low SP sweep review与LP supplement均完成，SP0.1/0.01/0.005抑制暗弱星云，SP0.001接近baseline但halo无可信提升；LP0.01改善LP0.005但仍低于所有≥4门槛，Round2略优。侧车 runtime reason、coverage evidence、manifest SHA及test matrix已同步，assessment SHA BA166E63CDD21958AA81C632EC1249C1CC63BFC5E4D3D9514E93DD34B6139C8C，service 9 passed。真实API GET在隔离schema0009 workspace返回200/199唯一；首个服务启动失败于未准备data目录，第二请求成功但harness文本断言不匹配，修正后对保存响应离线检查通过，PID64788已停。证据 .artifacts/implementation/B31/ght-sp-response-20261028.json、ght-sp01-lp-response-20261028.json、image-review/sol-low-ght-d5-sp01-20261028.md、image-review/sol-low-ght-d5-sp01-lp-supplement-20261028.md 及http-command-catalog-smoke-ght-sp目录。所有图像仍未达到quality gate。

2026-10-28 18:58 UTC B62 v18 current-docs/assessment preflight：GHT SP/LP侧车BA166E63…已进入wheel/sdist；隔离`python -m build --installer uv`使用setuptools84.2.1成功，仓库外wheel及Node-free sdist rebuild/reinstall通过。Report `.artifacts/implementation/B62/packaging-report-final-v18-ght-sp-lp-20261028.json`，hash见test-matrix。`v18-content-verification-r2.json`确认包内sidecar与源码及manifest digest匹配、构建时docs逐字节一致、egg-info snapshot已恢复；OpenAPI snapshot语义匹配。首次v18内容脚本断言因SP shorthand过窄失败，修正后通过，未重建/重跑包。v17b Sol Low复核无发现；v18 package review pending。B61未完成，B62未Ready。

2026-10-28 19:00 UTC B62 v18独立复核：GPT-6.1 Sol Low重新计算wheel/sdist/rebuilt wheel hash，确认包内当前BA166E63…SP/LP sidecar与manifest hash、GHT review reason、隔离主构建及Node-free非隔离sdist rebuild报告一致；六个egg-info文件与snapshot一致。无artifact正确性发现，未重跑构建/测试/runtime。review `.artifacts/implementation/B62/sol-low-v18-ght-sp-lp-review-20261028.md`。B61未完成，B62仍未Ready。

2026-10-28 19:02 UTC B31 GHT B-parameter discrepancy: official captured docs list B=-5..15, but real Siril1.4.4 `ght -D=5 -B=-1 -HP=0.8` exited1 with `B must be >= 0.0 and <= 15.0`, no output/readback; copy/source SHA stays unchanged; B=0 works in D5 baseline; positive bounds not swept. Sidecar/coverage now show both statements and parameter_error_probe=invalid_range_rejected. Current sidecar SHA 4605C6AC18767B01526C12147DAF675DCB3E1052F021A60620B53C41D4CB9866; manifest ref matches; parameter-error count2; service9 passed. Fresh isolated GET returned200/199 unique with GHT error/SP/LP and denoise SOS notes; harness text predicate was corrected against saved response, no repeat GET; process stopped. See `.artifacts/implementation/B31/ght-d5-bneg1-hp08-20261028/parameter-error-outcome.json` and `.artifacts/implementation/B31/http-command-catalog-smoke-ght-sp-20261028/http-smoke-result-r4-corrected.json`. The documentation/runtime conflict remains unresolved; do not advertise negative B as supported.

2026-10-28 19:10 UTC B31 GHT B-range/user-facing evidence: sidecar now says partial_official_and_cli_observed, preserves official B=-5..15 versus actual B=-1 rejection, records no node-definition safety conclusion, and correctly distinguishes process-shutdown settings error from close. Assessment SHA CFD986C7E321E254709457F69AB562F0CCBA9DD66CEDEE991A801FCA18FECC75; manifest/coverage match, parameter-error count2, service9 passed. Real isolated HTTP GET r5 returned200/199 and served GHT fields identical to local sidecar; PID78132 stopped. Sol Low first review confirms range conflict, follow-up on corrected wording pending. Current B62 v18 package predates this sidecar wording update; rebuild v19 is required.

2026-10-28 19:11 UTC GHT sidecar node/error wording correction verified: sidecar SHA 0EBBD74E5F907CC9BDA91804C8D83F3312830BA90891A65EBA0E956916979B2E matches manifest/coverage; partial_official_and_cli_observed, no node generated, B=-1 probe invalid_range_rejected. Service9 passed. Final isolated catalog GET r6 returned200/199 and GHT fields exactly equal to local sidecar; denoise SOS notes preserved; PID78132 stopped. B62 v18 predates this final correction; v19 staged before wording fix is stale, so a fresh package is required.
