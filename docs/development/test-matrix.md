# 需求、实现与验证矩阵

<a id="file-ownership-map"></a>

### 文件归属与读写关系核对（2026-11-01）

- 按用户限定，只核对平台、前端、MCP／CLI、Bundle的源码、受跟踪生成文件、构建产物、安装副本、workspace和缓存；结论统一维护在[文件归属与读写关系](../architecture/repository-layout.md)，开发入口仅链接，不另建重复清单。
- 静态核对构建／打包、workspace网页复制、runtime解压和启动参数、配置选择、MCP生命周期与CLI传输、Bundle生成／导出／安装／开发绑定、节点同步、版本缓存、素材／预览缓存与原生浏览器草稿。开发Python实际导入路径为本Worktree的src，editable关联一致。
- 本轮仅修改上述文档和开发入口链接；此前Siril清理的未提交实现及隔离Bundle保持原样。未启停服务、修改绑定／安装／全局注册、清理缓存或读取令牌；未执行构建、生成或测试套件。相对文件链接、代码依据和文档差异检查结果在`.artifacts/reports/file-ownership`。
- 本记录证明文件归属说明已按当前代码核对，不证明此前实现已集成、发布，或当前进程／外部MCP已加载最新版本。

<a id="siril-bundle-ownership-cleanup"></a>

### 平台与 Siril Bundle 归属清理（2026-11-02）

- 平台基点`f8c613633148e365839bcc0c1c627a7c42e266ca`，分支`codex/equipment-management-final`；用户已授权整理本地待审提交和回传Brief，准确冻结SHA见最终Brief。不合并、推送或发布。
- 独立Bundle从干净dev克隆到本Feature的`.artifacts/bundles/AstroPhotoFlow-Siril`，分支`codex/siril-decoupling`，基点`570504cd593d923726ac76b9775a812e371fdc03`。manifest仍为Siril1.4.4／Bundle0.2.0-dev.2，基点没有精确tag；修改为未发布待审内容，准确冻结SHA见最终Brief，不代表现有v0.2.0-dev.2。原Bundle仓库与安装副本未改。
- 删除平台三个旧Siril参考JSON及旧读取函数。核对确认命令资料与Bundle语义一致；评估资料覆盖同一组199个命令、保留全部评估字段，Bundle版本另有更新后的状态与历史证据。Siril内容验证归Bundle，平台发行检查只核对通用Bundle资源与契约。
- 命令查询按有效Bundle软件版本读取，公共模型改为SoftwareCommand及通用assessment字典；预览按声明读取端口，Bundle十个live操作及生成器增加output声明。旧不可变目录未重写；未声明output时只允许唯一FITS图像输出，歧义明确失败。
- 平台样本、缓存及宿主显示改用Bundle命名；输入与输出颜色布局取操作声明，采样缓存身份覆盖操作与参数。旧缓存不复用、不转换；按受管manifest目录保留其清理归属和启动恢复。平台单元测试用独立合成目录；新增非Siril包名／版本／端口、缺失资料、版本冲突、输出缺失、范围保护、取消、原件变化及缓存归属用例。新增／调整的测试均未执行。
- 已完成：OpenAPI／前端六份契约与97项MCP离线目录生成、UI包类型检查、宿主类型检查及前端构建、Python语法与Bundle声明检查、产品修改及新增测试的Ruff检查。CLI脚本无参数变化，生成后内容不变。MCP生成初次受沙箱asyncio socketpair阻塞，沙箱外同脚本生成成功；未连接业务服务。
- 未执行：测试套件、独立打包安装、真实Siril处理、浏览器验收、跨版本升级。已有测试文件保留的历史lint不作为本轮通过项。当前服务未重启，运行界面不代表本轮修改已加载。证据、构建日志及两仓库差异见`.artifacts/reports/siril-decoupling`。

<a id="modernization-g7-browser-closure"></a>

### G7旧浏览器入口收尾及G1—G7重新复核（2026-11-01）

前次标记完成遗漏旧手动浏览器入口；逐项复核又发现CI仍固定uv0.11.29，与bootstrap0.13.5不一致。本轮补齐两个遗漏，撤回旧审计可独立证明全部收尾的结论。以下为最新证据，旧记录和失败日志保留。代码尚未提交、推送、合并或发布。

- `native-web.mjs`、`platform-workflows.mjs`、`m2-layout.mjs`的有效断言已迁移为3个Playwright Test spec及共享fixture，旧执行路径删除。根默认`pnpm test:browser`切换Playwright配置，现代化／原生专项有明确独立入口；去向见[浏览器迁移清单](browser-test-migration.md)，不恢复旧上传控件或已隐藏DevMode。
- `default-browser-isolated-report.log`：默认入口8项全部通过，1.8分钟；独立报告`browser-entry-final/results.json`为expected=8、unexpected=0、skipped=0、flaky=0。包含双宽度布局、侧栏／代理、真实项目创建及草稿、真实上传／完整查看／回收站恢复及源文件字节、原生图存取与LoadImage→SaveImage队列、原生设置搜索／loopback、实际409及重启／恢复。不是用--list的skip报告代替执行。
- 补回旧脚本的画布x>=64位置断言后，`browser-closure-graph-layout.log`项目／草稿／图和视口场景追加1项通过，7.9秒；未重复未改变的重启场景。
- 配置恢复附件与`browser-closure-results.json`明确记录saved/effective初值2、真实采用1、最后恢复2且无待采用配置。fixture在任何写入前核对实际health／config／数据目录，拒绝dev／default；`default-browser-protected-workspace.log`为保护校验的预期失败，不计业务测试通过。
- `default-browser-offline-discovery.log`：没有URL／workspace／业务服务也可发现8项；CI增加独立“Discover browser tests (no services)”步骤，uv改为0.13.5，YAML／实际入口验证见`browser-entry-audit.json`。没有推送，未宣称远端Windows/Linux CI已执行。
- `browser-closure-science-fixture.log`：共享上传fixture变更后的真实原生Siril闭环1项通过，15.4秒；`browser-closure-boundaries.log`15项架构回归通过；`browser-closure-ruff.log`自研Python／脚本通过。未修改产品Python或Bundle，`browser-closure-product-comparison.json`确认与已验证wheel产品模块逐字节一致，所以复用前轮964／521／120／56等未受影响范围证据，不声称本轮全部重跑。
- [G1—G7逐项核对](modernization-audit.md)列出58项要求、实现和验证依据；实际源码清单新增CI与编译器helper覆盖，原始728项基线处置保留。路径、符号、散列、未解释删除和本地链接以本轮核对报告为准，不能仅凭manifest“无缺路径”认定需求实现。
- 报告目录支持工作树.artifacts/reports内独立子目录，防止--list与实际运行覆盖彼此报告；不允许指向其他目录。失败trace按Playwright策略保留，最初迁移失败副本在本机default-browser-before-final中保留，不属于产品源码。

G1—G7本地候选的本轮遗漏已收尾；未执行用户真实素材、全部160操作科学验收、Linux/WSL、长期热加载或跨版本升级，也没有提交／集成／发布。两笔历史unknown保留不重发；10万复杂查询秒级、seqprofile窄场景限制继续保留。最终工作区与预览状态见本轮交接报告。

<a id="modernization-g7-complete"></a>

### G7最终候选交付（2026-11-01）

G0—G7本地实现与本轮授权验证完成。G7发现并修复的G5职责缺口、调用竞态、错误契约、包收录和目录来源问题已纳入候选；不是仅搬文件或以窄测试代替整体验证。未提交、推送、合入dev或发布。所有以下报告位于`.artifacts/reports/modernization/g7/`，历史失败及unknown事实保留。

| 完成检查 | 当前证据 |
|---|---|
| 完整平台回归 | `platform-final-candidate-tests.log`：964通过、16跳过，720.85秒；跳过的环境型场景不记通过，所需Siril／原生／重载场景另有显式证据 |
| 自研UI | `workspace-capability-final-ui-tests.log`：80文件521项通过；`workspace-capability-browser-current.log`：13项真实Chromium通过，1.4分钟 |
| 当前宿主桥接 | `native-current-final-tests.log`：25文件120项通过，20.20秒；比早前117项多包含nativePage接口测试，不混加重复计数 |
| 独立Bundle | `bundle-current-final-tests-from-root.log`：56项通过，2.69秒；从Bundle根目录运行；`bundle-ruff-final.log`零诊断 |
| 类型与源代码质量 | `distribution-build.log`包含UI／宿主类型和真实前端构建成功；后续只清理无用事件／格式，当前UI／宿主行为复验通过；`ruff-final.log`全src/scripts通过；`workspace-capability-eslint-final.log`定向无错误；两仓库diff检查按CRLF规则通过，未批量格式化上游 |
| 生成一致性 | `platform-generation-consistency.json`22份产物重生成无变化；CLI按名称和锁定Ruff布局固定生成，97工具、无业务HTTP；两进程一致见`cli-generation-repeatability.json`；Bundle操作／节点／双语322文件字节不变 |
| 代码／文件去向 | `source-inventory-verification.json`：1150文件／7378函数、728基线，散列不符、目标缺失、未解释删除、目标符号缺失均0；版本化JSON保留候选修订及明确删除；Python遍历包含循环／异常分支中的嵌套定义 |
| 独立安装与交付 | `distribution-final-build.log`成功生成wheel／sdist；`distribution-final-verification.log`确认仓库外按锁文件安装、Node不可用时隔离重建sdist、重新安装／smoke均通过；`final-wheel-source-comparison.json`确认全部当前产品Python字节与wheel一致 |
| 文档及资料 | `current-document-links.json`当前文档本地链接／锚点有效，准确数量见报告；`official-reference-integrity.json`原254份官方资料的大小和SHA均一致。原文档包保持原始抓取时状态，不表示当前未安装；新增Siril正文见独立补充目录 |
| 最终预览 | `final-preview-receipt.json`：2274fea7a5c1495bb7cf001c106f55c4 ready，24.909秒；`final-preview-health.json`网页代理健康200、原生队列运行／等待均0；http://127.0.0.1:32588，服务32590 |

全量回归的3条warning中，旧SDK图片属性断言已改为SDK v2的mime_type，`sdk2-image-content-tests.log`定向1项通过、无该warning；其余分别为单测直接调用Cyclopts入口提示、刻意截断FITS负向样本。没有屏蔽warning来声称通过。

真实闭环／科学验证见下方G7记录：Data→Siril→Data→查看→选择保存／导出、固定版本和顺序、原件哈希、校准、配准／叠加、多输出、单帧分析、压缩、缺依赖、取消、原生保存／撤销、画布过期／切图／关闭／未知回执和MCP官方重载。新增独立3份合成FITS的原生科学复验15.4秒通过（完整runner16.2秒）。科学程序真实执行，输入为合成素材，不宣称用户真实天文素材或160操作逐项科学验收。

准确仓库状态见`final-repository-state.json`：平台codex/equipment-image-mcp，HEAD bbb6f4a9f872fc1b79defa6dddf849247b5099d6；Bundle codex/modernization，HEAD f4f11b34587f989fb026607b483b740ee3b74cac；均dirty，app二进制差异0。发布目录使用既有SDK v2 tag v0.2.0-dev.2／5d16fb6fc10b4ee57de428d6eba522c918b1b441；开发适配器仍以本地源码／指纹为准，不冒充已发布提交。

固定新增版本：FastMCP4.1.4、Cyclopts5.3.2、Hey API0.99.0、Vue Query5.105.0、watchfiles1.3.0、Ruff0.17.3、pytest-asyncio1.4.1；实际核查见`adopted-versions.json`及锁文件。开发Python3.12.4，原生runtime Python3.12.15，均明确记录，不混写为同一环境。生成入口为export_openapi.py、前端openapi-ts配置、generate_cli.py、export_source_inventory.py及独立Bundle tools.build_catalog／tools.build_locales。

限制：两个早期unknown调用保留原事实，不从日志猜测退出码且未重发；10万素材复杂查询仍是秒级，原G2报告记录上限和SQL计划，不宣称毫秒SLA；seqprofile仅所测128×128单帧窄场景通过；未执行用户真实素材、全部160节点科学验收、长期热加载／跨发布升级或Linux／WSL验收。正常dev、默认workspace、全局MCP和真实素材未操作。下一步仅为用户评审；集成须按仓库流程获准后进行独立审查，不自动开新任务。

<a id="modernization-g7-progress"></a>

<a id="modernization-g7-capability-audit"></a>

### G7追加：独立交付与测试隔离（2026-11-01，收尾中）

- 第一次当前平台全量结果`platform-current-full-tests.log`：963通过、1失败、16跳过，714.78秒。唯一失败是MCP集成测试仍查找旧`request_id=`字符串；改为正式ErrorEnvelope及UUID请求标识，`mcp-business-domains-fixed.log`1项通过，51.42秒。更新后完整候选回归仍在运行，不能把定向修复写成单次全量已绿。
- 首次wheel完整性验证发现6个拆分目录缺少显式包标识；namespaces=false使29个模块遗漏。补齐native/bundles、data/exports／formats／science、software/execution／packages的包标识；分发验证现检查所有实际产品Python模块，不能只检查少数代表路径。
- 独立安装发现list_siril_commands与带版本查询使用两份不同能力评估；现统一固定Bundle发布快照，移除旧参考回退。官方原始目录／散列资料仍保留来源身份；能力评估来自实际选定Bundle。`catalog-authority-tests-final.log`软件服务与架构36项通过，20.71秒；pyscript评估与实际发布节点对应，并保留未科学验收及高风险说明。
- `distribution-verification-current.log`：仓库外临时虚拟环境从锁文件安装wheel成功；Node不可用条件下隔离重建sdist并重新安装／smoke成功。CLI最终生成入口收尾后仍需刷新最终产物。
- 浏览器首次9通过／4失败：旧独立素材被先前科学场景加入集合，已不再是独立条目。测试改为各自通过真实上传接口创建专属合成FITS；UI场景结束仅归档自己素材、保留文件。随后12通过／1失败；剩余草稿用例在搜索提交前开始编辑，现先等待查询、先监听再触发外部修改，`workspace-draft-browser-fixed.log`1项通过，16.8秒。不删除原有草稿、revision冲突与图不变断言。
- `native-science-owned-fixtures-browser.log`：改用本场景独立3份新合成FITS后，真实原生Data→Siril→Data／所选保存导出再次通过，16.2秒，未再挪用其他测试样本。
- 独立Bundle在本仓库根目录运行`python -m pytest tests --import-mode=importlib`：`bundle-current-final-tests-from-root.log`56项通过，2.69秒；平台根目录直接按路径收集时缺adapter路径的失败记录保留，不用顺序依赖的sys.path副作用修补。Bundle Ruff零诊断，操作／节点／双语322文件重生成逐字节无变化，见`bundle-generation-consistency.json`。
- CLI首次一致性检查仅发现框架生成布局与事后Ruff排序不同。已将名称排序及锁定Ruff布局纳入固定生成入口；两个新进程生成一致，见`cli-generation-repeatability.json`。受限生成校验取消的精确进程记录保留，未停止业务进程；最终全链生成复核继续。

整体G7仍未完成；最终平台回归、当前产物、当前文件清单及文档核对继续，未提交、推送、合并或发布。

### G7：职责审计纠偏与最终候选（2026-11-01，进行中）

G7源码审计发现原G5的行为验证通过不能证明文件职责拆分完成：大部分Workspace逻辑曾集中转入WorkspacePage。先前“文件重构完成”判断过早。本轮继续提取真实能力，不以改名或行数减少作为完成标准。

- 字段写入分别归`assets/useAssetEditor.ts`、`equipment/useEquipmentEditor.ts`；`library/useRecordFieldEditing.ts`协调当前记录类型和过期回执，`useInlineSaveState.ts`只维护保存中／失败／等待状态。
- 项目固定引用写入归`projects/useProjectReferenceActions.ts`；素材批量身份选择归`library/useLibrarySelection.ts`；有限清单、revision和删除确认归`trash/useLibraryRemoval.ts`。
- 固定集合导航／外层筛选和分页恢复归`datasets/useDatasetView.ts`，读取继续使用`useDatasetMembersView.ts`；纯资料显示归`library/metadataPresentation.ts`，列字段绑定归`library/tableRows.ts`。页面装配不再拥有这些能力的实现。
- 首次拆分回归508通过／13失败，日志`workspace-modules-ui-tests.log`保留。根因是把摘要误作完整AssetOut、以及测试依赖组件私有函数。写入缩小为生成AssetOut的id／revision，集合校验改为实际UI编辑断言；`workspace-field-editor-regressions.log`4文件65项通过。后续最新`workspace-capability-final-ui-tests.log`全80文件521项通过，19.05秒；`workspace-row-presentation-typecheck.log`类型通过。
- `frontend-dependency-boundaries.log`289模块、1213依赖无违规；平台`ruff-current-audit.json`为零诊断。完整平台回归、Bundle收尾检查、最终生成／打包与新候选浏览器验证仍在推进；旧预览不能证明本轮源码已部署。

前序G7真实验证现已取得证据（均位于`.artifacts/reports/modernization/g7/`）：

| 场景 | 证据与范围 |
|---|---|
| 网页固定Data→真实Siril→Data→查看→只保存／导出所选完整成员 | `native-science-flow-browser-atomic.log`1项通过，20.0秒；JSON记录原件／导出哈希及固定成员，不依赖后来新增成员 |
| 自动结果、实际查看器及切图后的旧执行通知 | `native-automatic-result-browser-final.log`1项通过，19.6秒 |
| 画布目标／内容过期、页面关闭、延迟回执查询、不重放及原生撤销 | `native-canvas-guards-receipt-final.log`1项通过，18.6秒 |
| 原生草稿另存 | `native-workflow-save-browser.log`1项通过，6.1秒；使用ComfyUI文件管理 |
| 原生interrupt与实际Siril停止 | `native-siril-cancel-final-tests.log`1项通过，12.42秒；拥有者进程身份、终态和原件哈希检查 |
| 校准数值、配准／叠加、多输出、单帧分析、压缩 | `siril-real-science-cases.log`4项通过，32.28秒 |
| 实际取消、缺StarNet依赖、seqstat与seqprofile分析行 | `siril-real-cancel-analysis-final.log`4项通过／3项筛除，25.51秒；seqprofile仅证明所测单帧128×128窄场景，不宣称历史Windows限制全面消失 |
| 官方FastMCP开发重载、拥有者退出与重新连接 | `mcp-real-reload-final-tests.log`1项通过，11.53秒；未修改全局MCP |

真实科学程序使用合成输入，不等于全部160节点或用户真实天文素材验收。两个早期unknown调用保留原事实，不从日志推断成功，也不重发原prompt。G7／整体Goal尚未完成，未提交、推送、合并或发布。

### G7：整体验证、有效来源及调用观察竞态（2026-11-01，进行中）

进入真实科学与原生闭环验证，尚未完成G7／整体Goal。仅操作私有modernization workspace/runtime和合成素材，无提交、推送、合并或发布。

证据位于`.artifacts/reports/modernization/g7/`：

- `platform-full-tests.log`首次全平台结果：955通过、1失败、7按显式环境门控跳过，771.36秒；CLI/MCP真实协议段通过。唯一失败为新增错误未统一经过文案目录，不能写成全库通过。
- 已补72处ApiError文案键和中英文本，动态诊断保留fields；HTTP统一调用localized_error，客户端只维护一份ErrorDetail，MCP转发上游原消息／字段／请求ID，不把带HTTP前缀的异常展示串再当原消息。导入报告统一经过文案构造，持久化ErrorDetail按契约读取，旧science_inputs路径豁免删除。`error-localization-coverage-final.log`6项通过；`errors-data-full-tests.log`693项Data／接口／边界通过，355.16秒，1条刻意截断FITS负向warning。
- `ruff-final.log`、`ruff-after-errors.log`：自研src及scripts检查通过。导入排序、明确subprocess.check及原有字典构造已整理；Annotated查询变更后OpenAPI SHA-256仍为`d4b75ab8ef263fd9080203545b6d15540aa69b4282f98054b6122abaa5c1a1dd`，未改生成接口结构。
- `ui-full-tests.log`521项通过；原生首次116通过／1失败，widget的999/1毫秒边界断言改为控制未完成状态请求，直接检验缩略图保持、完整图替换、固定科学引用及释放，`native-full-tests-final.log`117项通过，11.97秒。
- `siril-real-autostretch.log`：独立临时Bundle中的真实Siril1.4.4双成员Auto Stretch通过，12.82秒；输出尺寸／有限像素、成员顺序、原文件与IMAGE固定化文件SHA-256、最终active=false断言通过。它不替代网页原生链路。
- 真实安装发现两个有效来源错误：①开发节点已加载但错误检查未生效发布副本的availability；②节点计划使用发布声明、实际加载开发声明，名称／分类不一致导致160项内容校验失败。现按effective_availability检查并按有效开发声明规划节点，固定发布文件仍取批准tag；没有跳过content token校验。`install-effective-readiness-tests.log`27项、`effective-node-plan-tests.log`36项通过。`native-software-node-plan-final.log`真实网页确认／固定tag安装／160节点刷新通过，36.8秒；原失败操作和trace保留于对应failed文件。
- 真实Data→Siril→Data首次执行发现状态观察竞态：线程读取旧运行中快照后，后台已完成并从active移除，查询错误判为孤儿并覆盖终态。observe_software_call现先确认拥有者，完成跨越读操作时重读终态，活跃任务事实仅由拥有者写入。两种旧快照确定性回归及全部software相关检查见`call-read-completion-race-tests.log`126项通过，139.21秒。原调用`0be38ced-2768-4416-b26f-079f7d60e178 / d49be92e-dc27-5180-966e-66c70aec830a`维持unknown：已查询进程active=false和真实日志，但退出码事实被旧竞态覆盖，不能据日志推断成功，未重放原prompt。原报告／日志／trace保留于native-science-first相关文件，新的科学验证待更新私有预览后另建prompt。

官方资料核对发现原Siril Commands RST仅有include索引，正文缺失；原254文件及清单保留，新补[1.4.4官方命令正文与清单](../references/modernization-addenda/siril/1.4.4/README.md)。不是重新选择软件版本。

剩余：真实原生科学闭环、其他约定科学／取消／画布场景、MCP开发重载、完整生成／依赖／打包检查、文件附录非同名／删除映射和最终交接；已通过项不无故重复，发生新修改／失败时定向复验。

<a id="modernization-g6-complete"></a>

### G6阶段收尾：统一调用契约与真实未保存草稿（2026-11-01）

G6主要实现与阶段完成条件已交付。软件调用摘要统一为contracts/software.py的SoftwareCallResult，无RunCallResult兼容别名；Python软件调用列表、详情与分析查询归SoftwareOperations，画布客户端只承担原生图操作。HTTP字段和原生prompt身份不变。Pydantic→OpenAPI→Hey API SDK／Zod／Query以及FastMCP CLI同步生成，全部97工具仍来自同一完整目录。

证据在`.artifacts/reports/modernization/g6/`：

- `software-call-contract-tests.log`：44项类型化客户端、原生回复、软件调用、MCP／stdio和递归边界通过，21.12秒；`software-call-cli-generate.log`生成97工具；`software-call-contract-generate.log`生成6份SDK文件。
- `software-call-ui-typecheck.log`、`software-call-native-typecheck.log`：UI和宿主类型检查通过；UI一处遗漏的旧类型测试已同步。宿主使用锁定工具链直接执行typecheck:app对应入口，未全局安装pnpm。`software-call-ui-tests.log`2项查询测试通过。
- `media-lease-transaction-tests.log`：新增申请事务回滚时释放缓存租约断言，29项媒体／视频／断连测试通过，16.57秒。
- `software-contract-preview-receipt.json`：私有预览`bf3dd67de7b347b79ee7ed80fc72509f` ready，84.07秒；运行中的OpenAPI已核对存在SoftwareCallResult且无旧类型。`software-contract-native-queue-tests.log`1项真实原生Data提交／结果读取通过，0.87秒。
- `native-unpersisted-draft.json`、`browser-native.xml/json`：浏览器调用原生loadGraphData得到isPersisted=false的临时工作流，经网页自身queuePrompt和真实`/api/prompt`完成固定Data输入，输出completed；1项通过，5.7秒。未保存平台工程或完整图副本。
- 首次浏览器任务实际已成功，但测试误监听`/prompt`而超时；按trace唯一client_id查询原任务已success后才修正测试。初次trace、观察失败日志和终态查询分别保留为`native-draft-initial-trace.zip`、`native-unpersisted-draft-browser-initial.log`和`native-draft-first-submission-terminal.json`，没有重放未知任务。

结合前述调用／结果归属、Siril类型化和模块失效、watchfiles、core/native、格式／科学文件、导入、媒体和清理记录，G6阶段实现完成；进入G7继续真实Siril科学闭环、最终全库lint／生成／依赖／文件清单核对及交接。历史附录候选函数名不作为当前API权威，最终非同名／删除映射随G7文档清理；没有把文件存在或阶段定向验证当作全产品验收，仍未提交、推送、合并或发布。

<a id="modernization-g6-media-cleanup"></a>

### G6：瓦片／租约与永久清理阶段拆分（2026-11-01，清单核对继续）

MediaViews的瓦片生成、共享任务与取消归media/tiles.py；目录持有、stamp／结果路径核对及读取计数归media/leases.py。HTTP调用方同步；重复释放幂等、准备异常不泄漏缓存持有。永久清理的预检／指纹归trash/scope.py，文件效果归files.py，内部CleanupPlan／FileCleanupResult归types.py，DB收尾为cleanup.finalize_cleanup。仍先提交确认意图、逐素材重验后删除，失败保留已删除文件事实与恢复限制；未引入统一文件／DB事务。

证据位于`.artifacts/reports/modernization/g6/`：

- `media-split-tests.log`：28项媒体、视频、共享瓦片／取消及流式响应通过；新增重复释放、准备失败及同stamp外来结果断言。
- `trash-split-tests.log`：29项清理／删除通过，35项筛除；新增有限路径、部分文件失败及拒绝DB收尾断言。
- `media-trash-full-data.log`：600项Data、递归边界、软件调用及媒体流通过，326.35秒。1条warning为刻意截断FITS负向样本。随后仅把预检函数归入scope，`trash-scope-final-tests.log`45项通过、34项筛除，29.45秒；没有把前一次全量结果冒充重跑后的结果。
- `unnamed-draft-native-execution.json`：私有原生队列一次接受并完成无workflow／完整图快照的Data prompt，`workflow_id=null`，结果登记可查询，合成原件SHA-256未变。仅证明执行层没有先保存工程门槛，不替代浏览器未命名草稿交互或Siril科学闭环。
- `file-plan-reconciled-symbols.json`：115行原函数到实际拆分目标已与当前定义核对并修订。`g6-symbol-target-audit.json`是修订前的候选名差异，不代表276项能力缺失，也不据此宣称全部清单完成；剩余目标须继续按实际归属核对。

全自研Python／脚本Ruff审计仍有69项诊断，主要为导入排序，详见`ruff-current-audit.json`；本次新媒体和清理文件Ruff通过。未把定向检查写成全库lint通过。G6最终清单与G7完整科学／原生验收继续进行，未提交、推送、合并或发布。


<a id="modernization-g6-import-pipeline"></a>

### G6：导入任务快照、阶段、runner收尾与媒体归属（2026-11-01，完成审计前）

ingestion.py与import_progress.py删除。ImportTaskContext.from_task固定本次来源、参数、默认快照、目标集合和上传／输出资料；阶段使用明确字段，不设dict兼容代理。枚举只接收实际使用的sources与upload_manifest；metadata／stages／completion／progress／workers分属既有能力。pipeline编排登记／内容／预览／任务完成，runner负责批次finally和启动恢复；tasks只修改任务事实，不反向引用批次。Source stamp与来源登记函数使用无歧义名称，避免本地变量遮蔽函数。

媒体缓存、共享executor、recipe、预览回填、显示像素及Siril样本分别归media/cache、executor、recipes、import_previews、rendering、samples。样本租约类提取时遗漏，已依据现存代码缓存核对原字段／close行为后补回，异常仍释放guard；没有改变科学原件或新建调度。PixelSource.read_fits_region是实际共享读取能力，旧私有跨文件引用删除。导出服务归exports/service，所有调用方同步；错误增加诊断日志，不伪造完成。common只保留真实使用的公共UUID／UTC／修订更新能力，未使用的旧通用抽象删除。

证据位于`.artifacts/reports/modernization/g6/`：

- `import-pipeline-full-final.log`：574项Data通过（310.46秒），1条来自刻意截断FITS的负向warning。首次全量8项失败记录保留于`import-pipeline-full.log`；原断言保留，修正旧入口／fixture／mock位置。
- `import-pipeline-final.log`62项、`import-pipeline-boundaries.log`52项、`import-pipeline-caller-regressions.log`82项通过；范围交叠不相加。`data-export-service-final.log`81项导出／边界通过，新增失败日志不改变处理行为。
- `import-pipeline-architecture.log`19项通过（10.14秒）；imports相关19模块依赖无环，pipeline／stage不依赖runner或batch的静态断言已加入。294模块依赖审计按实际child module解析后无环，父包装配边另行保留，不将包路径误当业务循环。
- `import-pipeline-self-ruff.log`及`data-export-service-ruff-final.log`对应范围通过；`import-pipeline-contract-check.json`公开OpenAPI哈希不变。打包资源检查同步新0001_baseline与实际自研路径，没有恢复历史迁移链。
- `import-pipeline-browser.xml/json`：导入／媒体候选2dd3cafdd5874d2691a9b45fafc7b507的13项Chromium通过，零失败／错误／跳过；52份合成FITS哈希由`import-pipeline-originals.json`确认不变。网页／目录真实，软件结果挂载仍为明确mock，不代替科学运行。

随后exports/service归属和失败日志采用最终预览429304202b124eab90a3e8ec4c9a3a7c，固定入口21.9秒，见`import-layout-preview-receipt.json`；其启动健康通过，导出81项定向通过，不将先前浏览器结果冒充同一部署回执。

阶段源码及精确去向见`import-pipeline-map.json`；当前归属与明确路径修订见文件计划。元数据读取保留软件共同底层、本机选择保留三个调用方共享边界，已记录原因。G6仍须完成完整文件／依赖／约束清单核验与原生草稿执行门槛；G7真实科学及完整闭环未完成。没有提交、推送、合并、发布或操作共享dev／默认workspace／全局MCP／真实素材。



<a id="modernization-g6-data-codecs"></a>

### G6：独立格式层与科学文件／内容归属（2026-11-01，阶段进行中）

fits_preview／auto_stretch／image_formats／media_sources／media_video／video_preview旧模块删除，能力分别归formats的fits、layout、pixels、raster、xisf、raw、numpy、ser、source、video，科学转换归science/conversion，播放代理归media/playback。格式解码不再从ingestion取私有函数；PixelSource不反向依赖科学转换。SER完整容器事实使用SerInfo；端序、实际位深、时间戳、首帧显示与完整容器可用性分别保留。科学NumPy转换不再沿用显示的四通道裁剪，明确拒绝静默丢通道，显示行为不改。

science_inputs旧模块删除；固定输入解析归science/inputs，文件哈希／范围／复制归science/files，素材内容观察与确认归assets/content，存储定位归assets/storage，输出检查／呈现／显式登记归science/outputs。共同参数键和分类规则归assets/metadata，不再反向读取导入流水线。文件流使用既有ApiError码，取消／错误本地化及0／null／成员顺序保持。文件操作和数据库事务没有被宣称为统一事务。

证据在`.artifacts/reports/modernization/g6/`：

- `data-codecs-science-final.log`：全部574项Data通过（319.80秒），1条warning来自刻意截断FITS的负向测试。首次全量28项失败均保留于`data-codecs-science-broad.log`，实际遗漏的资产定位调用、SER访问和旧mock路径已修正，未恢复旧模块。
- `data-codecs-verified.log`81项、`data-science-verified.log`72项、`data-codecs-callers-verified.log`170项定向通过，范围重叠不相加。
- `data-boundaries-results.log`：24项通过（10.01秒），覆盖底层边界与具体调用／checked结果交接；`data-formats-dependencies.json`记录10个formats模块无环、没有导入／ORM／HTTP上层依赖。相关静态约束加入架构检查。
- 新格式／科学／内容／播放及当前ingestion范围Ruff通过；`data-codecs-contract-check.json`证明公开OpenAPI哈希不变，没有手写或额外生成另一套DTO。
- `data-codecs-browser.xml/json`：当前候选13项Chromium通过（105.52秒），零失败／错误／跳过；`data-codecs-originals.json`核对52份合成FITS哈希不变。页面／缩略图／目录真实，软件结果挂载仍是明确mock，不算Siril科学运行。

旧符号与目标签名的准确来源见`data-codec-map.json`、`data-science-map.json`和原符号快照。当前私有预览回执 **c36b0dd8070c41bf89a668ad5a09c356**，固定入口54.006秒，http://127.0.0.1:32588，详见`data-codecs-preview-receipt.json`。没有操作共享dev／默认workspace／全局MCP／真实素材，也没有提交、推送、合并或发布。

G6剩余导入流水线／阶段与收尾及最终清单核验；G7真实科学与完整原生闭环尚未完成。不能以这次Data全量和浏览器通过代替整个重构完成。



<a id="modernization-g6-core-native"></a>

### G6：workbench与原生接入边界（2026-11-01，阶段进行中）

core/workbench.py拆为runtime／workspaces／paths／state／processes／observations／operations／control／constants／errors，__init__只显式导出。运行状态更新从config移入state，维护接口通过公开update_running_state协作，保留状态锁、原子替换、维护标记及真实未知状态。配置共享的写入／TOML序列化／Settings构造使用明确公共能力；新进程登记复用ProcessInfo校验后才持久化。删除无调用方active_config；单一package_directory处理包目录变化，不靠旧文件深度或兼容导出。

原interfaces/comfyui.py和canvas_native.py删除，分别归native/bootstrap／pages／canvas。native/context统一采用配置与token读取；代理只处理HTTP错误及流式转发，不再被原生注册反向导入。pages校验回复的event_id／page_id／page_token，错配返回桥接未知错误，不向错误页面发送结果或重放写入；关闭时仍等待已受理操作。engine/ComfyUI/server.py只同步注册调用点，并通过固定build_engine入口更新归档／SHA及私有runtime，未修改上游画布或执行逻辑。

证据位于`.artifacts/reports/modernization/g6/`：

- `workbench-split-verified.log`：99项通过（17.57秒），包括启停、启动失败与登记失败、未知进程、控制互斥、配置／准备入口／lifespan和边界。
- `native-boundaries-final.log`：77项通过（10.44秒），包括同源代理、媒体、原生canvas／页面及三种错配回执；旧MCP本地化测试改测实际FastMCP错误边界，保留原因、字段诊断与request_id，没有恢复已删除网关。
- `workbench-dependencies.json`：10个内部模块显式依赖无环；`workbench-split-map.json`为精确旧符号与现所有者。公开入口无业务实现的架构断言覆盖workbench。
- `core-native-contract-check.json`：公开OpenAPI哈希未变，未手写替代DTO／SDK。新源码范围Ruff及差异检查通过。
- `core-native-browser.xml/json`：当前候选13项Chromium通过，零失败／错误／跳过；`core-native-originals.json`确认52份合成FITS哈希不变。网页／目录真实，软件结果挂载仍是mock，不是Siril科学处理。

固定预览回执 **555d8482f6f249a79493c7cb37357549**，准备27.152秒，http://127.0.0.1:32588，详见`core-native-preview-receipt.json`；实际runtime/server.py已使用native.bootstrap入口。两个仓库HEAD未变，均保留未提交改动，没有操作正常dev／默认workspace／全局MCP或真实素材。

补充：Siril生成器已拆为tools/catalog/operations、nodes和coverage，构造器返回SDK模型。`siril-generator-comparison.json`对比322份操作／节点／双语声明，0项语义差异；160操作、199命令和43端点保持。`siril-generator-verified.log`56项通过，`siril-generator-ruff-final.log`范围通过。实际网页重启仅提交一次原operation_id，`core-native-real-restart.json`证实completed、两个服务身份均已变化且健康就绪，未改默认workspace。

G6仍须完成data格式／科学文件／导入流水线等职责整理和完整清单核验；G7真实科学与原生闭环未完成。本条只记录已执行范围。



<a id="modernization-g6-typed-watchers"></a>

### G6：类型化调用事实、Siril执行拆分与watchfiles（2026-11-01，阶段进行中）

SoftwareCallRecord共享真实请求／节点／操作／调用／观察／结果契约；读写校验存储路径与嵌套事实身份，completed要求checked result已登记。接入层直接使用对象，删除字典与JSON模型往返。Siril四个SDK入口拆为参数、运行配置、序列、三类计划构造、输出、分析与解析；BuildContext、RuntimeOptions、SequenceDescriptor及ResultLayout描述具体调用，布局按operation核验。没有图副本或新调度器。

software/development分成bindings／fingerprints／builder／watching；唯一BundleDevelopmentConfig校验模块入口和监听模式。原interfaces/bundle_nodes.py删除，node／catalog／watcher归native/bundles；目录与监听经software公开能力合作。watchfiles只监控声明、源码前缀、安装／生成控制和必要Git身份；事件到达后才重算内容指纹，空闲不扫描。绑定切换及目录增删会重新注册监听，生成失败不复用旧实现，关闭时取消并等待任务。

本机发现独立原生解释器缺少watchfiles，已在Windows原生锁定清单加入计划版本1.3.0。首次固定入口离线准备因缓存缺该wheel明确失败，随后按授权下载固定版本完成；没有改动其他依赖版本。原生测试发现同步注册与异步监听启动之间的编辑遗漏，现已提前固定初始指纹并复验。

证据目录`.artifacts/reports/modernization/g6/`：

- `typed-records-verified.log`：27项通过；`records-watchers-broad.log`：145项通过（143.42秒），范围含全部软件、调用装配、监听、确认、lifespan和边界，计数有交叠不相加。
- `siril-typed-layout-final.log`：56项Bundle测试通过（1.43秒），含布局身份、选择省略／null／0、单帧／压缩／多输出／解析断言；`siril-split-ruff-final.log`整个自研adapter范围通过。
- `watchfiles-final-regressions.log`：30项通过（28.25秒）；事件用例覆盖空闲不扫描、同大小／同mtime、绑定切换、目录增删、错误优先和清理。
- `native-watchfiles-final.log`：真实ComfyUI解释器／注册表的合成Bundle场景1项通过（25.55秒），含安装、连续修改、移除与关闭监听；程序版本探针为测试替身，不是Siril科学处理。
- `typed-records-public-contract-check.json`：公开OpenAPI哈希未变；未另造HTTP DTO或手改SDK。
- `typed-watch-browser.xml/json`：当前私有候选13项Chromium通过，零失败／错误／跳过；`typed-watch-originals.json`确认52份合成FITS哈希不变。原生目录和页面真实，软件结果挂载仍是明确mock。

当前预览回执 **6f30e5b30cad4d67bc1b42bfba3fcf28**，固定入口24.529秒，http://127.0.0.1:32588；详见`watch-final-preview-receipt.json`。G6余项为core／data及原生context／bootstrap／pages等职责整理、Siril目录生成函数与最终清单核验。G7真实Siril科学与原生执行闭环未完成；没有提交、推送、合并或发布。



<a id="modernization-g6-bundle-packages"></a>

### G6：软件职责、完整Bundle包加载、SDK v2唯一入口及类型化recipes（2026-11-01，阶段进行中）

本轮使用本地Python importlib／dataclass与SDK实际定义，未更换已固定依赖版本。software/public已收敛为显式导出；packages分离状态、维护、目录与安装，execution分离状态、参数校验、进程、使用观察、执行和预览。Alembic初始化保留已有logger，安装进度写入失败的诊断不再消失；首次进程身份AccessDenied保持unknown，父进程退出不构成整树停止证据。

原bundles.py拆入bundles包。loader使用importlib隔离命名空间、普通相对导入与完整命名空间失效；源码加载绕过旧时间戳pyc。测试覆盖同大小／同mtime快速修改、旧pyc、新增／删除helper、异常后的部分导入清理、不同Bundle隔离和dataclass注册。progress／failure与plan采用同一实际来源及内容指纹。脚本／测试不再消费旧模块偶然暴露的导入对象，导出脚本直接消费metadata能力。

平台不再接受SDK v1：ProcessPlan、单输入／单输出转换、解析回退和原生SDK v1准入删除。默认目录通过固定导出入口从**干净稀疏参考checkout**生成，采用仓库已有tag **v0.2.0-dev.2**、准确提交 **5d16fb6fc10b4ee57de428d6eba522c918b1b441**，160个真实操作。没有创建tag或发布。当前开发Bundle另为HEAD **f4f11b34587f989fb026607b483b740ee3b74cac**＋未提交内容，开发状态记录真实dirty／指纹，不归于该发布tag。公开节点定义返回深复制，调用方不能修改固定目录；新增回归覆盖该问题。

Siril recipes拆为types／factories／catalog，使用dataclass及SDK ParameterDefinition、SoftwareInputDefinition、SoftwareOutputDefinition；端口种类及科学颜色布局归同一来源。build_catalog不再独立维护输出模式判断。执行器改用对象属性，JSON生成处才序列化。所有runpy拼装已从Bundle自研源码删除；开发配置使用`tools.build_catalog`模块名，固定命令为`python -m tools.build_catalog`，不留旧脚本路径分支。SDK数值边界规范化后部分帮助文本0变0.0，科学语义不变。

证据均在`.artifacts/reports/modernization/g6/`：

| 验证层级 | 已有结果 |
|---|---|
| 后端与接入 | `sdk2-only-verified.log`：136项通过（127.85秒），覆盖全部软件、具体调用／预览组合、lifespan及递归边界。`sdk2-contract-regressions.log`：51项通过，不与前者累加 |
| 模块失效与公开边界 | `bundle-reload-boundaries-final.log`：26项通过；公开data／software／bundles入口只允许显式导出 |
| 独立Bundle | `bundle-typed-recipes-final.log`：52项通过，新增逐项核对160操作的参数和输入／输出。`bundle-typed-semantic-comparison.json`记录发生文本变化的160份节点／操作声明与HEAD比较，0项语义变化；未变化文件由Git内容相同证明 |
| 生成链 | `sdk2-openapi.log`、`sdk2-sdk-generation.log`、`sdk2-cli-generation-verified.log`：固定入口完成；CLI97工具，未经过搜索变换。`sdk2-catalog-snapshot.json`与实际vendor目录一致 |
| 类型与lint | `sdk2-ui-types.log`及`sdk2-native-types.log`通过；`sdk2-owners-ruff.log`与`bundle-recipes-ruff.log`范围通过，不据此宣称整个旧适配器已无lint问题 |
| 工具目录与真实协议 | `sdk2-real-cli-stdio.log`：首次5项真实集成＋3项目录单元通过，图片导出末段CLI文件名被终端折行导致唯一断言失败；`sdk2-image-stdio-verified.log`定向1项通过（31.18秒）。仅让文件名断言忽略显示空白，仍核对拒绝覆盖退出码与原件逐字节不变。6项集成均有通过证据，不冒充同次整套绿灯；旧mimeType测试读取已改为SDK mime_type |
| 新候选真实网页 | `sdk2-browser.xml/json`：13项Chromium通过（81.56秒），零失败／错误／跳过；`sdk2-originals.json`确认52份合成FITS原件哈希不变。目录与本机请求真实，软件结果挂载仍是明确mock，不代表科学处理 |

私有候选回执 **5ba44f85e4a543b0a581d4af3ec47d9b**，固定入口build／start共59.512秒，http://127.0.0.1:32588；见`sdk2-preview-receipt.json`。较早候选`92862ab061d646cb91a425841e636420`及其13项浏览器记录保留，不冒充最终候选。曾因旧服务在配置改写中留下失败生成回执，通过同一bootstrap显式重新采用隔离源码恢复。首次CLI生成卡于受限进程本机连接，核实其PID／运行状态并做有权限离线对照后，仅终止该生成进程；同一固定入口在允许本机连接的环境3.9秒完成，没有重放业务写入。

平台分支及HEAD仍为codex/equipment-image-mcp／bbb6f4a9f872fc1b79defa6dddf849247b5099d6，Bundle为codex/modernization／f4f11b34587f989fb026607b483b740ee3b74cac，两者dirty。未提交、推送、合并、发布或修改正常dev、默认workspace、全局MCP与真实素材。

文档当前链接检查462项有效；附录60个已搬走的基线文件链接改为明确基线路径，历史记录6个已删除模块文档／未保留的本机报告标明实际情况，没有伪造文件。差异检查通过；历史失败证据保留。

G6仍未完成：强类型内部调用事实、Siril planning／results／analysis与生成函数职责拆分、watchfiles、native／nodes／core及data格式／导入／清理等仍须推进。G7真实科学与原生闭环未执行；本轮类型化配方、目录生成、浏览器及合成元数据证据不能替代科学处理。


<a id="modernization-g6-result-ownership"></a>

### G6：具体调用与已检查结果分属software／data（阶段进行中）

已删除整个`src/astrophotoflow/modules/workflows`目录，不保留旧路径兼容导出。软件调用记录归`software/execution/records.py`；具体节点绑定、输入解析、执行／恢复／取消组合归`interfaces/application/software_calls.py`；HTTP状态／日志归`interfaces/http/software_calls.py`。Data执行与固定化归`data/results/data_node.py`，结果记录／校验／消费归`data/results/records.py`和`service.py`；HTTP Data结果及文件／媒体归`interfaces/http/data/results.py`与`result_media.py`。

输出引用改成明确的`run_id`（ComfyUI prompt）＋`execution_id`（具体Data execution／software call UUID）＋端口／成员。旧node_execution_id节点名／data:前缀引用删除；同一个节点发生多次调用也不扫描软件文件猜结果。process observation中的node_execution_id仍是原生身份，不混同输出引用。

Data用不可变CheckedResult记录checked path／hash／size／mtime／解释资料／顺序，软件记录不再保存第二份checked ports。程序产物路径／进程事实仍属于具体调用，已检查登记用result_registered分别表达。Data公开结果保留原reference供界面归属，并新增明确output locator供原生下一节点；导出冻结的sources是输入快照，不是第二个输出事实权威。读取始终验证登记身份、端口／成员、软件工作目录、尺寸／mtime，科学消费和保存再核对完整hash；保留HDU 0和元数据快照，不用旧预览或重跑代替缺失结果。

证据在 `.artifacts/reports/modernization/g6/`：

- `result-ownership-broad.log`：143项通过，含调用、Data图像固定化、导出、软件服务、节点目录、生命周期、客户端响应及递归架构。
- `result-ownership-verified.log`：81项结果／导出／边界通过；新增案例验证同prompt两个execution精确选择且不需要软件私有记录、节点名引用拒绝、记录不可覆盖、跨prompt／端口拒绝、HDU0／gain0快照、同大小／mtime还原后hash变化、文件缺失以及损坏登记越出原软件目录。现有导出精度、RGB／压缩与原件保护断言保留。
- `result-ui-initial.xml`：521项UI通过；`results-native.xml`：117项原生桥接通过。`results-ui-types.log`／`results-native-types.log`两端类型通过，全部夹具显式采用新output和execution字段，没有生产兼容分支。
- `results-final-ruff.log`：新结果／记录／用例／HTTP文件通过；执行外边界记录完整日志并保留真实失败，未以noqa隐藏问题。
- `result-native-contracts.log`：新旧边界及原生／客户端契约通过，架构增加“没有平台workflows业务目录”。
- `result-openapi.log`／`result-sdk.log`／`result-cli.log`：固定入口更新公开契约与完整工具目录，NativeBundleCall只接受具名inputs，删除单输入reference兼容。

初次63项检查60项通过、3项夹具失败：无lifespan的HTTP受理测试需显式替换执行依赖；两个RGB夹具原来在执行后改写已检查记录，现改为先建立真实平面RGB上游登记再交Data消费，禁止覆盖不可变事实。边界检查发现__all__增量赋值不符合既定精确规则，合并成显式单一导出表，未修改规则。143项扩展检查随后通过。

最终私有候选回执 **60fff8214135412dae4d62c13fa34e17**，build32.067秒、start12.956秒；`results-browser.xml/json`13项Chromium通过（83.028秒），零失败／错误／跳过；`results-originals-check.json`核对52份合成FITS未变。`result-native-contracts.log`新增架构约束与原生／客户端契约通过；输出引用并未引入整图运行入口，浏览器模拟结果挂载仍不算真实科学验收。

该结果登记只记录具体执行的文件事实，不保存完整图／编辑图／执行prompt，不是平台Run／Workflow数据库。软件public其余安装／执行实现拆分、SDK v1、文件监听／完整Bundle模块失效、Data格式／导入／清理及独立Siril recipes／适配器仍待G6完成；真实科学与原生闭环属于G7。没有提交、推送、合并或发布。


<a id="modernization-g6-canvas-previews"></a>

### G6：画布与可选软件预览移出workflows（进行中）

`modules/workflows/canvas.py`已删除，原4个HTTP操作与operationId保留在`interfaces/http/canvas.py`；data入图准备和nodes能力检查由`interfaces/application/canvas.py`组合。`CanvasDependencies`仅持有settings／database／NativeClient；应用层不导入FastAPI。`interfaces/native/client.py`使用lifespan已有HTTPX连接池，每次请求超时10秒，校验JSON／UUID和回执身份，保留结构化错误字段；超时或不合法响应只报告未知，不重放POST。HTTP层保留维护锁准入，统一task_admission也拒绝shutdown_started。

`modules/workflows/siril_preview.py`已删除。`interfaces/application/software_previews.py:BundlePreviews`管理原有样本资源和实际取消／清理，start_preview校验软件与参数；`interfaces/http/software_previews.py`只处理维护准入、二进制PNG、断连及consumer释放。原`/software/packages/siril/autostretch-preview`两条兼容路由、代理白名单以及未使用的AutostretchParameters／NativeSirilCall／SirilPreviewRequest移除；仍采用BundlePreviewRequest与通用`/software/preview`。没有新增科学调度器或修改Siril1.4.4。

证据在 `.artifacts/reports/modernization/g6/`：

- `canvas-split-verified.log`：6项通过，覆盖实际HTTP目标字段、未知applied、错误认证、维护和共享客户端／错误诊断。首次失败是ErrorDetail.fields实际为字典列表，修正映射后保留字段诊断，未放宽契约。
- `software-preview-split.log`：29项样本取消／缓存租约／原件保护／lifespan通过，关闭及启动失败后HTTP池与数据库均释放。
- `canvas-preview-integration.log`：85项通过，1项边界失败；应用层初写`from modules.data import public`不能满足已有精确入口规则，改为完整`import modules.data.public`，没有放宽检查。
- `canvas-preview-final.log`：25项通过，覆盖迁移后的测试、未知POST只查原operation_id、shutdown拒绝写入、取消与生命周期及递归架构检查。
- `canvas-preview-ruff-final.log`：5个新文件Ruff通过；`canvas-preview-ui-types.log`前端类型通过。原SIM102嵌套取消条件合并，逻辑及取消等待保持。
- `canvas-preview-openapi.log`／`canvas-preview-sdk.log`／`canvas-preview-cli.log`：按固定入口同步公共生成物；旧预览操作已删除，不保留兼容参数或URL。

固定预览回执 **47297d17fac84ab7b85d5010a38fbb3f**，`canvas-preview-live-read.json`确认经共享客户端的真实画布页面查询200、旧预览接口404。`canvas-preview-browser.xml/json`：13项Chromium场景通过（82.393秒），未提交真实科学队列；`canvas-preview-originals-check.json`确认52份合成原件未变。`canvas-preview-generation-check.json`：141个公共操作、268个schema、97个完整目录工具，旧专用预览操作已移除。G6其余拆分继续进行。

相关测试随职责迁为`tests/interfaces/http/test_canvas.py`、`tests/interfaces/application/test_software_previews.py`。Data结果与具体软件调用仍在待拆目录，跨模块私有输出访问、SDK v1和Siril内部改造尚未完成；本条不代表整个G6完成或真实科学处理通过。


<a id="modernization-g6-no-full-snapshot"></a>

### G6：取消平台完整图副本与原生类型化回复（2026-11-01，阶段进行中）

先读本地HTTPX async、FastAPI lifespan及Python dataclass文档，并核对真实调用点：完整图不是由前端另一次保存请求发起，而是BundleNode从ComfyUI原生extra_pnginfo取出workflow后发给私有服务。已删除该POST、AutomaticResultSnapshot模型、私有snapshot路由、calculation-snapshot.json写入及因缺失／不匹配该图副本而拒绝执行的逻辑。ComfyUI自己的workflow／队列／history及用于UI归属的calculation_signature保留；自动模式仅限声明允许的操作这一业务限制保留。

同时发现Native BundleNode仍手工组装旧端口计数／formats／names，且未完整提供共享契约默认字段。现改为读取同一公共调用摘要，通过 `interfaces/native/replies.py:software_call_reply()`校验原prompt／call和成功状态，以共享RunCallResult的JSON发布原生ui结果；不猜文件URL或复制另一套DTO。Node输出仍来自原执行结果，字段缺失／身份不符不合成成功。

证据在 `.artifacts/reports/modernization/g6/`：

- `native-call-replies.log`：10项通过（服务5项＋原生边界5项）。原有完整图保存测试替换为旧路由404／不生成图副本；真实受理／幂等测试带自动模式signature，未先创建平台图文件仍可执行，参数冲突不重复执行。原生边界覆盖完整成员引用、错prompt／call、失败状态和缺失file_url。全部用临时文件及外部边界替身，不是真实Siril处理。
- `snapshot-boundaries-contracts.log`：24项递归架构／原生消息／客户端响应通过。
- `snapshot-public-generation-check.json`：重跑固定OpenAPI与CLI生成后5个公共生成物SHA-256未变。已删除的接口本来不在公共OpenAPI，未手改SDK。
- `snapshot-preview-receipt.json`：固定入口重启私有双服务，回执 **372abc16506146eb8d7b4f5c9a1f3675**，复用前端构建，http://127.0.0.1:32588。
- `snapshot-live-read.json`：用私有服务认证请求旧路径实际404，未创建calculation-snapshot.json；原生2个Data＋160个Bundle类型仍注册。没有提交队列或处理真实素材。

G6仍未完成：workflows目录、调用／已检查结果的职责拆分、SDK v1、Bundle模块加载／watchfiles、其他后端拆分及独立Siril适配器／recipes仍待执行。未完成真实取消与科学处理验收，不把本条当作整体验证。


<a id="modernization-g5-complete"></a>

### G5：阶段完成核验（2026-11-01，隔离实现与验证完成）

本条核对G5的前端与桥接职责，不代表G6后端拆除、Siril科学处理、集成或用户验收。最新契约将素材版本、素材摘要／缩略图、项目固定引用和软件输出的媒体地址由服务端提供；软件端口改为具名成员对象，删除members计数与formats／names并行数组及前端runResultBase／runOutputBase。生成SDK／Zod／完整MCP目录／CLI同步更新，不保留旧格式分支。

| G5要求 | 当前证据 |
|---|---|
| 单一契约和媒体地址来源 | `media-links-openapi-final.log`、`media-links-sdk-final.log`、`media-links-cli.log`；`g5-media-uri-audit.json`为0个业务组件／组合函数手写HTTP业务路径，适配器只消费服务引用及协议后缀 |
| 远端数据与界面状态分工 | Vue Query管理服务数据；Pinia保存布局／筛选／选中／草稿，WorkspaceContext与RecordData=any已移除。确认hash、revision、删除指纹保留为明确意图 |
| 请求状态、错误与无重试写入 | AssetContentChange、EquipmentDeleteDialog、LibraryTrashDialog不再手动维护busy或重复复制请求错误；新增预检mutation；冻结范围及旧回执隔离保留 |
| 旧操作不能解锁新操作 | 新设备删除场景覆盖第一次操作迟到时第二次确认仍保持pending，并验证第二次使用自己的revision和预检指纹 |
| 草稿和内联编辑协调 | `inline-settlement-regression.xml`42项；不再25ms轮询，直接等待现有保存协调器的完成；销毁后结束导航等待，不取消已受理写入 |
| workspace／成员／图身份及读取取消 | 各能力键包含workspace与真实资源参数；现有快速搜索、翻页、重连、旧图结果／内容签名、迟到成员和对象URL专项及完整原生组验证 |
| 缓存、失效与跨入口更新 | 读取去重、资源失效、10秒目录发现和1.5秒活动任务查询使用统一所有者；个别任务／导出进入终态停止，目录低频发现不当作仍在执行 |
| 查看器与资源 | 当前及邻帧至多3帧；对象URL、真实media consumer、视频帧回调及OpenSeadragon销毁分工明确。协议generation、原生自动队列／内容哈希保护不误删 |
| 按能力的文件位置与依赖 | `g5-layout-applied.json`64项落点与119处引用同步；`frontend-path-audit-current.json`0项；递归架构检查12项和前端依赖279模块／1131依赖均通过 |
| 类型与现有UI业务 | `g5-current-ui-types.log`通过；`g5-current-ui.xml`521项通过。`g5-final-native-types.log`通过；`g5-final-native.xml`117项通过 |
| 后端投影与输出引用 | `media-links-python-current.log`35项；`media-links-http.log`7项（集合有重叠，不相加），包含固定项目引用／OpenAPI和读取服务器file_url下载真实临时分析文件 |
| 严格UUID缩略图分支 | `media-link-thumbnail-verified.log`29项；加入有当前版本及Preview行的真实SQL分支，显式转换SQL JSON UUID，不放宽StrictModel |
| lint与范围限制 | `media-links-data-ruff.log`通过；旧workflows/software_calls.py的既有Ruff问题保留在`media-links-ruff.log`，归G6拆除／执行边界整理，不宣称后端全量lint已过 |

首次最终浏览器运行暴露缩略图真实分支500：从model_validate_json改为Python字典后，StrictModel要求UUID实例。已在SQL投影边界显式转换并补回归；初次测试夹具缺少当前版本指针没有进入分支，补齐真实指针后29项通过。失败浏览器日志／trace保留在`g5-final-browser-results`，不得以单元通过替代失败浏览器结论。

最终复验 `g5-completion-browser.xml/json`：13项通过、82.049秒，零失败／错误／跳过；`g5-completion-originals.json`核对52份合成原件未变。最终回执 **5a4c24f367944e9e89693288bc70f9c0**，复用已验证前端，仅重启隔离服务采用UUID修复，http://127.0.0.1:32588。`g5-generation-verification.json`确认269个schema、97工具目录与离线工厂一致，记录生成物SHA-256；导出器本来静默，零字节日志不当作成功证明。`g5-completion-audit.json`逐项记录当前证据，G5本地实现／验证完成，开始G6；不是Git集成、用户验收或整体Goal完成。

本轮没有真实Siril科学运行，原件保护与完整原生执行闭环仍需G7。分支与两个仓库SHA不变，没有提交、推送、合并、发布或更改全局MCP／默认workspace。


<a id="g5-viewer-layout"></a>

### G5：查看器、样本预览与既定目录落点（2026-11-01，阶段审计中）

完整查看器的成员／相邻缩略图使用Query，媒体生成继续复用useMediaView；只保留当前与相邻3帧，返回体带请求身份和成员序号。Native保留视口、数组／HDU／切片、视频呈现时间、proxy和播放位置恢复。图像／视频与瓦片仍由浏览器和OpenSeadragon显示，未建立替代科学执行器。

补充收尾检索发现的MediaImagePreview旧循环与SirilPreviewWidget手工请求状态：卡片预览复用同一媒体能力；可选Siril样本使用retry=false mutation，保留350ms防抖。同源参数编辑保留明确标为旧的预览，换源或工作区清除；只有真正开始的请求才释放consumer，关闭取消读取不宣称进程已经停止。原生参数0、未展开不计算、开发指纹和软件安装恢复语义继续保留。

前端附录审计发现64项G5文件仍在旧目录，已在本阶段完成Query行为改造的基础上同步迁入library／equipment／imports／components及宿主canvas／results／sidebar／settings，并更新119个源码文件的相对导入、别名和对应当前文档引用。没有兼容导出或空壳目录。`g5-layout-applied.json`是准确映射，`frontend-path-audit-current.json`为0项待落地前端路径；薄API适配器与生成目录的职责差异单独保留，不将路径检查当整个G5完成。

证据位于 `.artifacts/reports/modernization/g5/`：

| 证据 | 结果与范围 |
|---|---|
| `viewer-sample-owners.xml` | 9项通过：当前及邻帧、Blob／URL上限、换工作区取消、旧成员／旧样本拒绝、同源旧预览、未执行不释放、未知不重放 |
| `viewer-sample-native.xml` | 26项通过：查看器／卡片／结果／Siril预览组合，含原像素、数组切片、VFR呈现时间、取消帧回调和恢复实际播放位置 |
| `viewer-media-clock-verified.xml` | 媒体组17项通过，精确999／1000ms轮询边界保留 |
| `layout-current-ui-types.log`、`layout-current-native-types.log` | 路径同步完成后的双端类型通过 |
| `layout-dependencies.log` | 279模块、1132依赖，零违规；源码diff --check通过 |

最终布局候选 `layout-full-ui.xml`：**519项UI通过**；`layout-full-native.xml`：**116项原生桥接通过**；两端类型和依赖检查通过。固定预览回执 **64b065aeb42343bc856ae95e70a04d57**，build30.158秒、start12.838秒，http://127.0.0.1:32588。`viewer-layout-browser.xml/json`：**13个Chromium场景通过**、78.148秒，零失败／错误／跳过。新增浏览器navigator.onLine=false并派发offline事件后，真实搜索仍向本机API读取并显示正确组；没有关闭系统网络或把本机网络请求也拦截。既有真实设置写入／队列提交继续受拦截，结果挂载场景仍是明确HTTP mock，不是Siril科学验收。`viewer-layout-originals-check.json`确认52份合成FITS原件未变，`viewer-layout-document-check.json`核对7个本轮链接／锚点与64项落点。Bundle副本仍干净。递归架构检查 `layout-python-boundaries.log`：12项通过（5.24秒），搬迁后原生与业务边界仍有效。

保留失败诊断：首次Native夹具的mock实现被全局重置而返回undefined，改为稳定真实二进制传输边界后原9项通过；媒体组首次精确时钟失败源于根配置shouldAdvanceTime=true，精确边界测试显式关闭自动时钟推进后17项通过，未放宽时点断言。Siril业务字段从生成schema omit consumer／generation派生，实际协议字段由所有者填写；原组件提前按完整schema解析导致5项无请求，修复后6项通过。原生类型检查发现推断联合的可选body不满足请求类型，改为明确request／error输入类型。第一次布局类型检查与仍在执行的路径同步重叠，捕获旧文件列表TS6053；等待同步完成后重新检查真实目录，两端通过。

本轮没有执行真实Siril科学处理。G5仍需媒体地址与确认界面状态审计，G6／G7未完成，Goal保持active；不提交、推送、合并或发布。


<a id="g5-canvas-query"></a>

### G5：Canvas检查、路径导入与服务器媒体引用（2026-11-01，阶段未完成）

CanvasDataWidget及测试已归入宿主canvas目录，调用方同步。组件不再维护inspect／媒体prepare／status的loading副本或setTimeout循环；参数、工作区和固定成员身份进入所属Query。缩略图保留到完整概览可用，0／null与固定引用不改写，原生连线／bypass解析及撤销事件保留。

原客户端importPath循环被拆为显式提交mutation和原任务Query观察：仅内容就绪即可产生固定引用，不等预览。已知任务的恢复只GET原ID；受理未知时不重发同路径导入。断连同步标记未知、结束本地等待，迟到回执可恢复原ID；关闭取消HTTP观察，不宣称后台导入已停止。最终写节点前确认原图、workflow、workspace、原引用和连线状态，用户已经改引用则拒绝覆盖。

CanvasInspectOut新增必需view_base，服务按固定资产版本提供引用地址，原件availability和预览状态仍独立。宿主使用返回引用，删除自行拼接的素材媒体路径。按固定入口重新导出OpenAPI、Hey API SDK／Zod与完整MCP目录／CLI；没有手改生成物、增加兼容入口或更改依赖锁。

本轮证据在 `.artifacts/reports/modernization/g5/`：

| 证据 | 范围与结果 |
|---|---|
| `canvas-contract-python.log` | 24项通过，61项按选定范围排除：真实HTTP固定成员／元数据、未知值与原件保护、新媒体引用，以及OpenAPI快照／代理一致性 |
| `canvas-query-final.xml` | 10项通过：导入原始2项语义继续保留，新增未知受理、终态停轮询、原ID恢复、跨workspace取消、断连迟到回执，以及成员元数据身份／待完成刷新 |
| `canvas-widget-complete.xml` | 10项通过：0值、固定引用、高清重试、缩略图排队、原生bypass，新增用户改引用后不覆盖、错误成员拒绝与缓存丢失诊断 |
| `canvas-openapi.log`、`canvas-sdk-generated.log`、`canvas-cli.log` | 固定入口生成完成；Canvas响应新增字段沿同一契约链传递 |
| `canvas-final-ui-types.log`、`canvas-final-native-types.log` | 生成后双端类型通过；最终累计组另附 |
| `canvas-query-dependencies.log` | 276模块、1115依赖，零违规；源码diff --check通过 |

最终累计 `canvas-full-ui.xml`：**510项UI通过**；`canvas-full-native.xml`：**113项原生桥接通过**。生成后的UI类型 `canvas-final-ui-types.log`、最终原生类型 `canvas-native-complete-types.log`均通过。当前私有预览回执 **559c9bc5d17247ea9a0bba6deaf92fd7**，build32.243秒、start13.571秒，http://127.0.0.1:32588。`canvas-browser.xml/json`：**12项Chromium场景通过**、81.235208秒，零失败／错误／跳过；真实队列和设置写入仍被拦截，软件结果Widget场景仍使用明确HTTP mock，不当作科学运行。`canvas-originals-check.json`确认52份合成FITS原件哈希未变。`canvas-document-check.json`：6个本轮链接／锚点、2个搬迁文件核对通过；独立Bundle副本仍干净。

保留初次失败：原native测试在缩略图先到时过早断言高清请求，改为等待实际高清请求而保留原断言；新增view_base后夹具缺字段导致3项预览断言失败，补齐真实响应字段后通过。断连专项曾因start仍await提交而超时，改为独立接收回执与本地等待，7项导入验证通过。初次SDK命令在frontend根找不到包内CLI，改用仓库既定filter入口成功，没有另装依赖或换版本。

本轮没有执行Siril科学处理，没有修改正常dev／默认workspace／全局MCP／真实素材或独立Bundle业务源码。G5还剩MediaViewer／mediaViewport及阶段审计；G6—G7未完成，Goal保持active，不提交、推送、合并或发布。


<a id="g5-native-results-media"></a>

### G5：原生结果、导出与媒体所有者（2026-11-01，阶段未完成）

本轮落实宿主三个结果组件的Query／mutation归属，并将组件及测试移到 `frontend/src/platform/astrophotoflow/results/`，更新Canvas调用方与Bundle结果显示装配，无旧路径兼容导出。UI包保留生成DTO／Zod与SDK权威，新增媒体显示消费者／概览读取能力，具体定义见[文件计划](file-refactoring-plan.md)。没有更改依赖、OpenAPI业务契约、数据库或Siril业务源码。

- `useNativeWorkspace`共享工作区核实，断连取消有效身份、重连重新核实，最后一个消费者离开清理监听。
- Bundle结果先核实实际调用，再按端口／成员读取分析；拒绝其他图、过期内容及迟到成员数据。Native输出、签名、自动预览与原生队列保留。
- 导出按原workspace／request_id／冻结来源和成员顺序观察，提交／取消／目录选择不自动重试。未知受理先GET；只有用户明确恢复且服务确认为RESOURCE_NOT_FOUND时复用原请求。HTTP成功但回执failed时显示实际原因；暂时故障继续观察原ID。
- DataRun先验证原生图／连线引用，再查询实际Data结果；后台失败状态的原因独立显示，不使用旧预览替代。媒体prepare是一次显式显示mutation，Query观察同一prepared key直到终态；切换中止旧读取、释放consumer与对象URL。协议generation保留，不新增科学执行器或运行ID。

证据位于 `.artifacts/reports/modernization/g5/`：

| 证据 | 结果与范围 |
|---|---|
| `native-result-export-ui-verified.xml`、`native-result-export-host-verified.xml` | 媒体共享能力加入前，492项UI与107项原生桥接通过；`native-query-owners-verified.xml`的14项专项通过 |
| `media-query-verified.xml` | 12项通过：生成终态、未知受理不重放、跨workspace及选择取消、迟到响应、consumer释放、错误视图身份、失败原因、Blob取消与对象URL释放 |
| `media-result-structure.xml` | 26项通过：三个结果组件及Canvas／Viewer调用方；包含原生引用不改写、其他图拒绝、断连与新工作区重新核实 |
| `media-full-ui.xml`、`media-full-native.xml` | 502项UI、109项原生桥接通过；双端类型见 `media-final-ui-types.log`、`media-final-native-types.log`，均通过 |
| `data-run-final.xml` | 最后补齐后台state=failed且HTTP成功的原因展示，6项通过；其后累计原生组另记 `media-native-final.xml` |
| `media-query-dependencies.log` | 275模块、1098依赖，零违规；源代码 diff --check通过 |
| `media-browser-verified.xml/json` | 12个Chromium场景通过，84.208秒。既有素材／成员／设备／草稿／真实断连场景与设置真实只读，加真实Bundle节点Widget挂载；调用记录由HTTP mock提供，队列提交被拦截，不是科学处理成功证据 |
| `media-originals-check.json` | 52份合成FITS原件SHA-256均未改变 |

初次检查的失败均已保留：原生类型检查发现扩展客户端后3处测试替身缺少release／image或导出方法，补齐真实边界替身后通过；`media-query-complete.xml`的一项失败来自JSDOM Blob交给Node Response后被当作字符串，使用真实Response文本主体构造二进制读取夹具后12项通过，生产代码没有为测试增加回退。更早的结果／导出验证还发现过跨工作区短暂查询旧导出ID，已用原子Session修复；新增身份核实不以旧缓存作为新的工作区事实。

最终累计原生组 `media-native-final.xml`：**110项通过**；最新原生类型 `media-native-final-types.log`通过。最终私有预览固定回执 **8701bff4f1574fd99e35cd9ce455d8e3**，build34.471秒、start14.670秒，地址 http://127.0.0.1:32588；`media-final-preview-receipt.json`保留完整证据。`media-final-browser.xml/json`：当前最终预览**12项通过**、80.654274秒，零失败／错误／跳过；52份合成原件再核对未变，见`media-final-originals-check.json`。本轮新增文档7个链接／锚点和6个搬迁文件检查通过，见`media-document-check.json`；不把附录基线散列当当前源码校验。

本地Siril开发绑定使用固定bootstrap入口，绑定到Goal隔离副本，原生目录为2个Data节点＋160个真实Bundle定义。Bundle HEAD仍为f4f11b34587f989fb026607b483b740ee3b74cac且工作区干净；绑定／目录生成不等于真实Siril处理或160节点逐项验收。未操作真实素材、共享dev、默认workspace、全局MCP或系统配置。

当前仍为G5：CanvasDataWidget、MediaViewer及mediaViewport边界与最终阶段审计待完成；G6后端workflows／完整图快照／SDK v1和Bundle内部重构、G7原生科学闭环尚未完成。Goal保持active，没有提交、推送、合并或发布。



<a id="modernization-g5"></a>

## Modernization G5：查询基础与导入任务（进行中）

<a id="g5-workbench-query"></a>

### G5：工作台配置、控制动作及重启结果

2026-11-01：设置页接入Query／mutation并拆到core/workbench。组件不再自己维护读取或每秒重启结果循环；编辑基线仍固定原config_token。不同客户端控制来源有独立键，干净表单可以采用新的配置事实，脏草稿保持原值／令牌；只有成功的新读取才能建立可编辑基线。保存与采用值分别显示，隐藏导入根与未修改default_workspace的省略语义保持。

代理源码明确以504/SERVICE_TIMEOUT表达超时，因此与网络／503一致继续查询原重启operationId；不重发POST。结果身份不匹配拒绝成功。观察最多5分钟，关闭取消GET，不能据此认定真实重启被取消。已确认completed后即使配置读取失败，也同时保留“重启完成”与“配置读取失败”两个事实。

当前证据位于 `.artifacts/reports/modernization/g5/`：

- `workbench-query-initial.xml`：原有12项通过。目录选择断言同步检查新增AbortSignal；结果fixture使用实际请求operationId，保留“不重发”的断言；Query首次立即读取，因此原1秒一次的两次读取在1秒后即可核对。
- `workbench-query-verified.xml`：24项通过；覆盖配置缓存与脏草稿、原令牌、客户端切换、目录迟到回执、读取取消、5分钟上限、关闭后停止观察、错误操作身份、已知完成后的核实失败，以及新来源读取失败时不得采用旧缓存。全部为隔离客户端／假时钟，不写真实配置。
- `workbench-native-panel.xml`：真实原生设置控件／生成客户端1项通过，使用与生产同一PlatformQueryPlugin，网络由测试替身提供。
- 初次 `workbench-full.xml`：477项通过；随后增加“旧缓存不能作为新核实结果”场景，最终累计检查另附。无依赖版本或OpenAPI业务契约变化；AbortSignal是客户端传输参数。

最终 `workbench-full-final.xml`：**73文件、478项UI包现有测试全部通过**，零失败／错误／跳过。UI类型 `workbench-verified-types.log`、原生类型 `workbench-verified-native-types.log`通过；`workbench-query-dependencies.log`：**265模块、1035依赖、零违规**。固定入口预览回执 **5b30481ee39c425296a0a088578487f9**，复用runtime并重建前端102.199秒；预览 http://127.0.0.1:32588。

`workbench-browser-final.xml/json`：**11个真实Chromium场景通过**（55.8秒）。新增设置页读取实际配置，config_path核对为隔离workspace的config.toml；编辑并发草稿后重新读取，原值恢复，画布保持。测试对该设置端点所有非GET请求硬性拦截，最终写入记录为空，因此没有保存／目录选择／重启或默认指针操作。首次定位误选画布同名设置，随后精确名称还包含提示图标；保留初始浏览器日志与trace，实际只读DOM核实后改用原生侧栏快捷入口及稳定输入ID。未放宽配置身份、草稿或零写入断言。`workbench-originals-check.json`：52份合成科学原件哈希不变。

本轮不通过真实设置页保存、选择系统目录或执行重启，不修改默认workspace／全局配置。G5原生结果／导出／媒体Widget请求仍待收敛，G6—G7未完成，整体Goal保持进行中。

<a id="g5-declarative-views"></a>

### G5：声明式记录视图、刷新与导入受理

2026-10-31（构建回执UTC跨入11月1日）：删除WorkspacePage中央loadRecords及五个可写请求槽位。库、固定成员、设备／组合、项目引用和素材挑选各自由能力view组合函数派生查询参数。useStableQueryInput仅固定编辑时的UI参数，不复制服务响应；改变资源身份不沿用旧输入。useRecordSearch负责输入防抖，Query拥有真正的读取、失效和取消。通用记录创建／设备保存及导入受理同步接入所属mutation，不再依赖父级强制GET。

证据位于 `.artifacts/reports/modernization/g5/`，报告间有重叠，不相加：

- `declarative-views-initial.xml`：119项中6失败；其中3项暴露局部setQueryData清除了先前失效标记，导致摘要／总数／导入后读取未更新。所有局部确认投影之后仍使所属查询失效，由Query在编辑暂停结束后读取；旧读取不降低已确认选中项revision。另1项私有测试改为实际refreshRecords入口；1项旧断言强制返回时GET，改为验证新鲜缓存复用且原筛选和组内容保持。`declarative-views-current.xml`最终119项通过。
- `declarative-input-lifecycle.xml`：4项通过，覆盖编辑冻结后只采用最新参数、返回新鲜原列表不再GET、固定版本切换取消旧读取、快速搜索与导航立即采用新参数。
- `declarative-full.xml`：465项中2失败，暴露刷新空尾页回退复用了旧首页总数，以及同步props watcher在全部新props采用前把旧datasetName放进新导入草稿。显式刷新先使同资源分页失效，导入草稿按正常Vue批次采用新props。
- `declarative-pagination-import.xml`保留一次错误修订：设备管理refresh方法误加到设备选择目录，出现1失败及13条运行错误；定向纠正归属，未部署错误候选。`declarative-pagination-import-final.xml` 33项通过。导入新场景还验证两个并发submit事件只发送一次、关闭重开或换工作区后旧回执不关闭新表单。
- 最终 `declarative-full-final.xml`：**73文件、465项UI包现有测试全部通过**，零失败／错误／跳过。此前4项及119项包含在其中。
- UI类型 `declarative-refresh-types.log`、原生类型 `declarative-native-current-types.log`通过；最初原生检查发现两个拆除后的未使用符号，已删除。`declarative-dependencies-final.log`：**261模块、1015依赖、零违规**。

最终补充：中央读取删除后，旧操作错误也失去了原来的清理路径。`declarative-error-scope-before.xml`首版断言误把REVISION_CONFLICT的原文当作实际本地化结果；改用明确未映射的DELETE_REJECTED业务错误，`declarative-error-scope-reproduced.xml`真实复现“删除失败后切到项目仍显示旧失败”。增加随writeViewKey清理局部操作诊断，保持Query错误与字段失败映射独立；`declarative-error-scope-verified.xml` **54项通过**，包含新增回归及查询／编辑／回执场景。前述465项全量是该两行修正之前的结果，此后定向54项有重叠，不宣称执行了519个独立场景或新466项全量。

最终固定入口回执 **de44292736a04748a3d2216a5a172643**，复用缓存70.988秒，预览 http://127.0.0.1:32588。`declarative-browser-final.xml/json`：**10个真实Chromium场景通过**（55.4秒），包括分页／零值保存、固定成员校准草稿、跨入口变更与revision冲突、本机离线、软件侧栏、设备／组合／预设及原生WebSocket重连。`declarative-originals-check.json`：52份合成科学原件哈希不变。最新UI类型 `declarative-final-types.log` 和原生类型 `declarative-final-native-types.log`均通过。阶段审计确认 `core/WorkbenchSettings.vue` 的配置读取、保存／目录选择和重启结果轮询仍未收敛，因此G5及整体Goal保持进行中；G6—G7未完成。本轮未改独立Siril Bundle，也未进行Siril科学处理。

<a id="g5-connection-boundary"></a>

### G5：连接身份、原生重连与系统选择器

2026-10-31（回执UTC跨入11月1日）：公开Workspace成为连接装配，具体页面进入WorkspacePage。重连核实期间暂停data查询、取消旧读取、隐藏包括Teleport在内的对话框；原工作区核实成功后恢复同一页面实例／草稿，身份改变后移除原工作区缓存并重建页面，其他工作区缓存不清空。queryAvailabilityKey只有只读可用状态，不恢复万能上下文；业务响应仍归Query。原生侧栏转发真实断开／重连事件，并在身份改变时清除旧任务通知。

系统选择器移至imports，调用明确无重试mutation；AbortController只保护本次系统交互的取消和迟到回执，不用于列表读取。连接恢复不会自动重开选择器。批量成员写入在revision收集阶段遇到断线、重连或组件销毁时不再发PATCH；内容接受的未知结果不跨失效连接核实，也不自动重发。

失败、修复及最终证据位于 `.artifacts/reports/modernization/g5/`：

- `connection-boundary-initial.xml`：63项中1项失败，连接错误在新Shell中未沿用既有错误显示。抽出共享library/errors.ts，恢复既有服务不可用表达，没有把初始失败展示为空库。
- `connection-lifecycle.xml`：46项中2项断言误比较Vue Test Utils的包装代理；改为组件实例uid，仍严格证明同工作区保留实例、换工作区替换实例，保留草稿值和旧缓存取消断言。
- `connection-chooser-writes.xml`中的断线guard测试首次把provide写在消费它的同一个setup中；Vue只向后代提供该值，实际读到了默认值。改为真正的上级provider，保留“不得发送PATCH”的断言。
- `connection-full.xml`：459项中147失败，暴露新增可选Boolean属性被Vue在省略时转成false，独立App因此停在重连态。用withDefaults明确非原生调用的connected=true；不修改既有业务测试。
- 最终 `connection-full-final.xml`：**72文件、459项UI包现有测试通过**，零失败／跳过。相同工作区、跨工作区、失败后只在明确点击时重试、旧身份缓存重新挂载、断开后迟到身份响应、系统选择器取消和旧成员PATCH阻止均包含其中；不累加专项报告计总数。
- `connection-native-bridge-final.xml`：原生桥接1项通过，覆盖连接状态／代次转发、工作区变更通知清理。UI类型 `connection-types-current.log` 通过；原生类型证据见connection-native-current-types.log。`connection-dependencies-final.log`：**254模块、971依赖、零违规**。
- 固定入口构建／启动回执 **4835e3824d3047f087863f15dcd3898b**，复用缓存70.131秒；预览 http://127.0.0.1:32588。`connection-browser-final.xml/json`：**10个真实Chromium场景通过**（53.9秒）。新增场景实际关闭本机原生WebSocket，暂缓真实health请求，证明核实期间表单不可编辑、返回后原未保存组合草稿恢复，未发业务写入，画布节点保持；未替换响应正文伪造身份。原9项场景继续通过。
- `connection-originals-check.json`：**52份合成科学原件哈希不变**。本轮未运行Siril科学处理；Bundle源码未修改。剩余WorkspacePage请求分支与视图职责仍需收敛，G5及整体Goal未完成，G6—G7未完成。

<a id="g5-owned-writes"></a>

### G5：写入所有者、组合／预设草稿与内容确认

2026-10-31：Workspace 不再直接调用 mutationApi／libraryApi；资料、参数、固定成员、管理归档与素材移除分别交给 assets／datasets／equipment／projects／trash 的 mutation。结算失效原工作区，不重放未知结果。UI 的有限选择、草稿和回执归属仍保留；`writeViewKey()` 防止旧回执更新已切换页面。

- 实际发现并修复：素材移除中的全局 busy 阻断了另一页面的读取。`write-owner-scopes.xml` 首轮45项有1项失败；改为只暂停原视图，`write-owner-scopes-final.xml` 45项通过。新页的项目列表、勾选与总数不被旧移除／归档回执覆盖。
- EquipmentSetupManager、EquipmentDeleteDialog 移至 equipment，AssetContentChange 移至 assets；旧路径删除，调用方和测试同步更新。`useSetupEditor()`／`usePresetEditor()` 分别管理本地组合／预设草稿；共享目录刷新不覆盖草稿，组合成员 ID／顺序、预设省略／null／0 保留。设备创建、组合／预设保存、删除影响及删除执行使用无重试 mutation。
- 内容接受结果未知时只读取当前素材，核对身份、内容版本及观察哈希；不能核实时保留原确认错误与核实错误，不声称成功。`content-owned-writes.xml` 首轮35项有1项测试替身错误：普通异常被 SDK 识别为响应契约错误。改用真实503错误信封对应的 ApiClientError，保留两项错误文案断言，`content-owned-final.xml` 35项通过。
- 设备真实浏览器验证发现后端缺陷：同批选择 equipment → equipment_setup → capture_preset 删除时，缺少 ORM 组合→预设依赖导致 SQLite 外键失败。`setup-owned-deletion-before.xml` 3个新增场景中1失败、2通过，复现了实际500。增加 EquipmentSetup.presets 所有权及 CapturePresetSelection.member 删除依赖；按真实所有权删除，保留计数去重和原件／历史快照。初步18项虽通过仍有3条删除顺序警告，未视为最终通过；补齐成员依赖后，以 SAWarning 作为错误，`setup-owned-deletion-ordered.xml` **49项通过且无警告**，覆盖两个选择顺序、只选组合的级联、稀疏预设和设备快照。只改 ORM 关系，无表结构或数据库迁移。

最终自动化证据（报告位于 `.artifacts/reports/modernization/g5/`；专项与全量有重叠，不相加）：

- `owned-writes-full-final.xml`：UI包 **71文件、450项通过**，零失败／跳过；此前 `write-owner-full.xml` 为69文件438项。范围是现有自研 UI 测试集，不表示 G5 或完整产品验收。
- `equipment-editor-final.xml` 57项、`equipment-complete.xml` 41项、`content-owned-final.xml` 35项通过，均有重叠。
- UI类型 `content-owner-types.log`、原生类型 `write-ownership-native-final-types.log` 通过。`write-owner-final-dependencies.log`：**251模块、939依赖、零违规**。`owned-deletion-ruff-final.log` 通过，未格式化上游代码。
- 浏览器创建接口真实返回201；首版场景误写200，保留 `equipment-browser-status-failure.xml` 并按真实契约修正。第二次联合清理暴露上述外键缺陷，保留 `equipment-browser-delete-failure.xml`。后续画布比较还发现测试在原生图初始化前采样，得到 undefined；`owned-writes-browser-graph-startup.xml` 保留8通过／1失败，改为等待真实图存在再记录比较基线，没有把 undefined 当作空图放宽断言。
- 浏览器中断遗留的一条滤镜及后续三条设备／组合／预设均按 trace 中精确 ID、名称、工作区与新预览指纹清理；证据 `interrupted-equipment-cleanup.json`、`interrupted-equipment-batch-cleanup.json`。没有扩大删除范围。

隔离前端构建回执 `a9030811a80645b588000230aee1f5c0`，49.288秒（复用缓存）；修复后后端固定入口重启回执 `8d3003477216438f9d974281f7b8c69d`，23.436秒（复用前端）。预览 http://127.0.0.1:32588；未操作正常 dev。最终 `owned-writes-browser-final.xml/json`：**9个真实 Chromium 场景全部通过**（50.7秒），包含注册滤镜→组合稳定成员→稀疏零增益预设→有限联合删除，以及原有固定成员分页、校准草稿、跨入口刷新、revision冲突、本机离线及原生软件侧栏；图内容保持，测试元数据已清理。`owned-writes-originals-check.json` 与最后逐字节复核确认 **52份合成科学原件哈希不变**。未将元数据／组件检查写成 Siril 科学处理。G5继续审计工作区身份／重连和剩余页面职责，G6—G7未完成，整体Goal保持active。

2026-10-31，本阶段尚未完成，整体Goal保持active。新增`core/query/client.ts`与`keys.ts`，宿主现有Vue应用安装公开`PlatformQueryPlugin`，每个应用一个缓存。查询键含workspace身份；本机读写使用always网络模式、不重试，读取stale5秒、gc5分钟、关闭聚焦刷新。没有新增应用或常驻服务。

`modules/data/imports/queries.ts:useImportTasks()`使用现有生成SDK客户端并传递AbortSignal；queued／running／cancelling每1.5秒读取，终态与interrupted暂停后停止。`mutations.ts:useResumeImport()`在成功或未知结果后按原workspace失效查询，不自动重放。ImportTasks删除自有定时器与响应副本；保留阶段通知、持久去重和暂停恢复，并在workspace变化时清除本地观察记录。空workspace身份不发起任务读取。

验证证据：

- `.artifacts/reports/modernization/g5/ui-query-foundation.xml`：首轮自研UI共347项，346通过、1失败。失败场景的health响应误用空分页，缺少workspace身份，因此新查询正确保持禁用。
- `.artifacts/reports/modernization/g5/query-and-workspace.xml`：补齐该场景有效health fixture后，受影响3文件51项通过；包括原12项任务断言、4项轮询／取消／跨workspace检查、2项本机离线及不重放策略。两轮重叠，不相加宣称执行398个不同场景。
- UI类型检查通过；原生类型检查通过，日志`native-query-foundation-types.log`。
- 当前仅单元／组件与类型证据，未重新构建部署，不宣称浏览器、真实导入或科学验收通过。

G5续记：`media/useThumbnailUrls.ts`独立管理视图URL及取消信号，Workspace不再用列表请求代次控制缩略图。实际预览字节与固定成员查询都收到signal；切页迟到字节不创建URL，换页与销毁释放已创建URL。首轮thumbnail-lifecycle.xml的38项中36通过、2失败，均为旧断言只接受一个getBlob参数；保留固定版本路径断言并增加AbortSignal断言后，media-equipment-current.xml共55项通过，其中包含3项独立资源生命周期检查。

设备规格字段与纯显示函数进入`equipment/fields.ts`；EquipmentFields直接消费所属能力，移除Workspace导入和inject，模型／属性仍为明确输入。新独立挂载检查验证小数编辑与null清除，组合／设置业务回归包含在上述55项。移除素材Workspace中的节点、软件、聊天占位导航；软件真实入口仍归原生宿主。connected-navigation-current.xml的3项通过，保留拒绝离开时不丢草稿的断言，导航目标改为仍存在的素材页。此前失败记录保留，不覆盖成通过；这些场景与前文有重叠，不合计为独立总数。

UI类型检查通过（ui-component-boundaries-types.log）。原生类型检查也通过（native-component-boundaries-types.log），当前未构建部署、未做本轮浏览器或科学验收。服务列表仍由旧Workspace请求状态管理，万能上下文的其他消费者仍未移除，不将本轮组件拆分记为G5完成。

G5续记：素材筛选目录已迁到`library/queries.ts:useLibraryFilterOptions()`，按workspace缓存、可见面板10秒刷新，并把AbortSignal传到生成SDK的实际读取。LibraryFilterPanel删除手工请求代次和服务响应副本；groups与数值控制范围从查询和本地草稿派生。新增验证覆盖同一应用的两个面板共用一次读取、5秒新鲜期内重新打开复用缓存、跨workspace取消和迟到响应隔离、后台观测范围收缩到0–6时保留未提交的10而不被HTML滑块强制改写。

LibraryPage与CalibrationBindingsEditor已删除WorkspaceContext和inject：页面接收明确的筛选／当前选择属性，以事件回传应用操作；校准编辑器通过dirty事件通知离页状态，销毁时明确清除。生成的DatasetOut复用于事件，不复制HTTP DTO。其余5个上下文消费者、列表请求状态及RecordData仍待处理。

验证：filter-queries.xml初次63项有4失败，包含3个缺失health工作区fixture和1个此前缩略图新增signal的旧断言；补齐实际健康契约并保留版本／signal断言。第二次filter-queries-current.xml尚有1个集合场景失败，定位为fixture修正在了后续场景而非共享configureLibrary，已改到正确装配处。library-boundaries.xml最终4文件69项全部通过；calibration-dirty-events.xml新增独立脏状态场景后该文件7项通过，二者重叠不相加计总数。UI及原生类型检查通过，分别见ui-library-boundaries-types.log与native-library-boundaries-types.log。未重新构建部署，不作为本轮浏览器或科学处理验收。

G5续记：设备选择目录已进入`equipment/queries.ts:useEquipmentChoices(workspace)`，由Vue Query保存完整目录和读取状态。200条分批读取共享取消信号，全部成功后才提供结果；可见应用每10秒刷新，按workspace缓存。强制刷新取消旧读取并只失效该workspace的equipment/choices键。Workspace删除该目录的响应副本、loading／ready／error可变状态和手写读取流水线，仅消费查询派生状态；历史设备快照选项继续保留。组合中新增注册设备后重新读取目录，不直接改写共享数组，并在等待后再次核对编辑目标。

验证：equipment-queries.xml的40项中5失败，均因旧组件fixture把health落到空分页、缺少workspace身份，设备目录按新门控没有读取。共享组件catalog fixture现显式提供一个符合ServiceHealth契约的隔离workspace，仍通过生成SDK进行响应校验；不属于应用健康回退，不作为真实服务健康证据。重复的各场景health分支已去除。equipment-queries-current.xml自研UI全51文件355项全部通过；equipment-pagination.xml另3项检查覆盖201台设备、第二页失败不采用部分目录及跨workspace取消后不采用旧完整结果。报告范围分开记录，不把355项写成浏览器／科学验收。

UI与原生类型检查通过，日志ui-equipment-queries-types.log和native-equipment-queries-types.log。没有部署更新、修改依赖或操作共享runtime。主列表／成员分页、其余5个上下文消费者及G6—G7仍未完成。

G5续记：主素材／集合混排与固定版本成员已接入查询缓存。`library/queries.ts:useLibraryQuery()`维护混排页；`datasets/queries.ts:useDatasetMembersQuery()`按workspace、dataset、固定version、参数及all模式区分缓存。正常列表在后端分页；显式全部模式以200条分批读取、共享取消信号，完整完成后提供页面。成员缓存保存生成的DatasetMemberPage，行是派生视图；元数据确认按稳定成员position更新当前Asset资料，固定Version不随之替换为现行版本。主列表本地缓存更新经过生成Zod items校验，不新增手写响应schema。

Workspace不再把上述两类结果复制进otherRows；otherRows／手工控制器仅暂供尚未迁移的管理、项目及独立素材范围。查询处理服务读取状态，querySearchPending只表示250毫秒输入防抖。搜索或切图切换键会隔离旧读取；行内保存／失败草稿会暂停并取消读取，保留其原缓存绑定直到用户解决。后台读取每10秒运行，重读完成后更新选中引用及视图缩略图；即使JSON结构共享、同一版本预览字节发生变化也会刷新。选择、筛选与编辑草稿没有放入服务缓存，原生画布机制未变。

验证：member-queries.xml整套自研UI358项通过。随后主列表首轮library-list-queries.xml为358项、3失败：失败编辑遇搜索时缓存绑定被过早清空，以及结构共享使可变预览字节未刷新。已分别保留失败编辑绑定、按读取完成状态更新预览；library-list-current.xml相关54项通过。新增外部修改10秒可见场景，library-refresh-and-drafts.xml相关34项通过。最终library-members-final.xml全52文件359项全部通过；UI与原生类型检查通过（ui-library-members-final-types.log、native-library-members-final-types.log）。上述范围重叠，不相加计独立场景数。

本轮没有构建部署或执行真实科学处理。尚未迁移管理／项目列表，仍有5个WorkspaceContext消费者、RecordData宽泛类型及编辑职责待拆；G5未完成，G6—G7未开始。原有固定成员、未命名画布、真实取消及Siril运行的整体验收不由本轮组件验证代替。

G5续记：设备与组合管理页已进入`equipment/queries.ts:useEquipmentManagementQuery()`。请求按equipment／setups判别，query复用生成的请求类型；结果直接来自生成SDK，缓存更新使用对应生成的Page.items Zod校验。读取键包含workspace、范围、筛选／排序／分页；每页50条。草稿或行内保存存在时暂停并取消读取，确认设备修改后只失效关联设备选择目录。删除尾页后的有效offset回退由查询结果驱动。Workspace中的这两类响应不再保存进otherRows，余下手写控制器仍暂用于项目、引用和素材选择范围。

验证：management-queries.xml自研UI52文件359项全部通过；management-draft-polling.xml该领域4项通过（包含先前3项目录边界），新增场景确认暂停时10秒不读取、不替换数据，编辑结束后读取新目录。两范围重叠，不相加计独立总数。UI／原生类型通过（ui-management-queries-types.log、native-management-queries-types.log）。本轮没有构建部署或科学验收。G5尚未完成，剩余项目／选择范围、5个上下文消费者、RecordData及G6—G7继续推进。

G5续记：项目、项目固定素材／集合引用由`projects/queries.ts:useProjectRecordsQuery()`持有；素材／集合选择范围由`library/selectionQueries.ts:useLibrarySelectionQuery()`持有。查询请求复用catalog生成SDK参数类型，缓存保存原始生成DTO；集合选择的entry_type只在视图派生，写回时从生成Dataset schema扩展的视图校验移除该标识。参数、workspace、项目及范围进入查询键，固定引用仍保留原版本。普通读取保留offset；显式全部模式统一使用library/pagination.ts:readPages()，库页、成员、项目和选择范围共同消费。

Workspace已删除otherRows／otherTotal／otherLoading、loadGeneratedPage、loadGeneration与recordsController。loadRecords只装配当前范围参数并显式请求查询；读取状态和响应归缓存，输入防抖与失败编辑等待仍为界面状态。参数装配错误统一呈现，不变成未处理Promise或伪造空页。切换模块释放旧缩略图URL；预览与固定输入身份保持独立。

验证范围分开记录：project-selection-queries.xml前一候选全52文件360项通过；共享分页完成后取消检查及参数错误边界补充后，project-selection-boundaries.xml相关55项通过、shared-pagination-members.xml相关25项通过（包括跨三页顺序、短尾页、普通offset、后续页失败及迟到取消）。最终导航资源清理后query-navigation-cleanup.xml相关6项通过。各报告重叠，不相加计总数，也不把此前整套记录冒充后续候选的完整套件。UI类型通过；首次原生类型发现失去旧catch后clearThumbnails未消费，已在模块切换使用并独立通过native-project-selection-final-types.log。首次失败native-project-selection-types.log保留。

未构建部署或进行真实科学验收。G5尚未完成，剩余5个上下文消费者、RecordData与编辑职责、软件／回收站等查询核查、跨入口新导入发现及浏览器验收。跨能力通知中的显式refetch需继续核对是否尊重草稿暂停，不能仅凭后台定时查询暂停宣称全部写入／通知路径完成。

G5续记：CalibrationLibrary删除WorkspaceContext注入及photos/loading/saving响应副本，改用明确workspace／recordsLoading属性和dirty／created事件。照片目录复用library选择查询；打开时显式读取完整校准目录，选择器不发起周期刷新。姓名、备注、帧用途和固定版本选择为本地草稿。创建通过`datasets/mutations.ts:useCreateDataset()`，参数类型复用生成客户端，提交时复制版本ID数组以固定顺序；保存期间禁用相关输入。成功或不确定错误后按原workspace失效库页、集合与选择目录，不重放写入。父级从已刷新的缓存寻找新组，只在仍处校准库且无新草稿时打开，不再额外强制读取外层列表。

验证：calibration-creation.xml相关28项通过。独立挂载新增失败保留草稿／固定版本且不重发、切换用途筛选后保持隐藏版本与选择顺序；第一次calibration-creation-current.xml为9项中1失败，原因是新增导航断言用endsWith比较带query的URL，已改为比较pathname。最终calibration-creation-final.xml自研UI53文件366项全部通过，包含创建后读取明确新version的导航断言。UI及原生类型通过（ui-calibration-creation-final-types.log、native-calibration-creation-types.log）。各范围重叠不累加。

WorkspaceContext消费者现在剩4个：EquipmentSetupManager、EquipmentSetupTable、WorkspaceRecords、SettingsPage。RecordData、通知触发的失效与编辑暂停、外部新任务发现及浏览器验收仍待完成；无本轮部署或科学验收，G5和整体Goal都未完成。

G5续记：EquipmentSetupTable删除WorkspaceContext、inject和内部EquipmentSetup[]断言，改用明确的组合数据、当前选择身份、设备目录状态、排序与选择属性；操作通过sort／select／toggle-row／toggle-page／retry-equipment事件回传。select和toggle-row只携带稳定setup ID，由WorkspaceRecords从查询原始行定位对象再调用既有操作，保持选中对象的缓存身份，不把用于展示的校验副本作为编辑权威。父级仍受RecordData限制，展示边界复用生成EquipmentSetupPage.items校验；不增加另一套DTO或响应schema。

验证：setup-table-props.xml原40项通过；独立挂载3项验证注册／组合内设备、事件、不修改父级Set以及元数据错误重试。身份事件收敛后setup-table-final.xml相关4文件43项全部通过；UI／原生类型通过（ui-setup-table-final-types.log、native-setup-table-types.log）。报告重叠，不与此前全套366项相加或冒充新的完整套件。本轮未部署或做科学运行。

现存上下文消费者为EquipmentSetupManager、WorkspaceRecords、SettingsPage共3个，RecordData与编辑职责、失效／通知及浏览器验收继续推进；G5与整体Goal未完成。

G5续记：EquipmentSetupManager已删除WorkspaceContext／Root store依赖，明确接收workspace、选中组合、列表读取状态、viewKey和关联变更标记，以dirty／saving／saved／delete事件合作。设备类别显示直接依赖equipment/fields，设备目录复用同一workspace的useEquipmentChoices；不创建目录副本。预设列表进入equipment/queries.ts:useSetupPresetsQuery()，以固定setup ID、workspace和查询参数隔离，使用共享分页、AbortSignal及10秒后台刷新，编辑草稿时暂停。presets／presetLoading／presetError成为查询派生值，presetGeneration和手工读取循环已删除；setupSelectionGeneration仅保留写入目标校验。

保存与父级的组合改为显式确认事件，父级setupSaved核对viewKey后刷新相应列表并采用本次服务确认的saved对象。首轮setup-manager-queries.xml全369项中1失败：重读旧列表时错误地选择了旧对象，破坏了原有“预设读取重试不影响同一保存”的断言；已恢复按确认返回值设置当前选中记录，并保留切换目标不跳回的校验。setup-manager-current.xml相关场景通过，setup-manager-independent.xml独立挂载2项通过，验证确认结果／原页面身份事件以及迟到保存不应用到新页面。最终setup-manager-final.xml全55文件371项全部通过，UI及原生类型通过（ui-setup-manager-final-types.log、native-setup-manager-types.log）。范围重叠不累加。

现存上下文消费者仅WorkspaceRecords与SettingsPage共2个。编辑职责进一步拆分、RecordData、写入失效与通知、跨入口新任务发现、软件／回收站等查询和浏览器验收仍待完成；本轮未部署或进行真实科学验收。

G5续记：SettingsPage中的项目／设备表单已抽到无provider依赖的RecordEditorForm，以RecordEditorState判别project／equipment；项目草稿复用生成ProjectCreate字段，设备草稿复用EquipmentDraft。Root仍持有当前编辑状态与服务操作，表单只接收模型、读取／保存状态、错误与保存单字段回调，发出更新／提交／关闭／取消字段事件。通过SettingsPage的editor插槽保留原先位于表格与详情之间的结构位置，未另做视觉系统。

EquipmentFields改为通过update:modelValue发出新对象与specs，不再修改父级模型；空规格保留null、数值不混用。设备名仍是字符串，型号／备注等保留可空语义。调整该组件原先依赖副作用的测试为明确应用父级模型事件，并验证原对象未变；既有组合／预设使用v-model继续同步。SettingsPage详情区和Root的RecordData尚未拆除，不能把表单抽离视为最后两个上下文已消失。

验证：record-editor-extraction.xml前一候选全55文件371项通过；补充独立表单测试并恢复原结构插槽后，record-editor-controlled.xml相关4文件24项通过，覆盖项目草稿／设备规格事件、原对象不变和离页保护。UI与原生类型通过（ui-record-editor-final-types.log、native-record-editor-types.log）。范围重叠不累加，不宣称后续候选已跑新的完整套件，也未更新预览或做科学验收。

G5续记：项目详情已进入`projects/ProjectDetails.vue`，只消费生成ProjectOut、归档阻拦状态和3个明确的保存绑定；回传带project ID的操作／取消字段事件，不导入WorkspaceContext、不请求HTTP或修改传入项目。SettingsPage通过project-details插槽保持原项目详情位置；Root只装配项目数据和事件，动作校验当前选中身份。保存绑定捕获当时行对象，直接传给InlineField现有saveAtEditStart机制，避免背景revision变化时把用户草稿改为新目标或使用新保存绑定。

验证：project-details.xml相关54项中1失败，新增动作测试将“移入回收站”误写成另一文案，修正文案后project-details-final.xml全57文件375项全部通过。独立项目详情检查验证带身份的归档事件／阻拦，以及远端revision变化后草稿保留并继续使用原保存函数；原函数冲突时错误可见，不自动改用新函数。UI与原生类型通过（ui-project-details-final-types.log、native-project-details-types.log）。未更新预览或执行科学处理。

SettingsPage素材／集合详情和WorkspaceRecords仍消费上下文，RecordData与通知／写入失效、其他请求能力及浏览器验收继续推进；这次项目局部抽离不记为整个G5完成。

G5续记：SettingsPage已删除WorkspaceContext、inject与Root类型导入，成为明确的项目范围／详情标题／固定版本展示及事件布局。素材字段进入assets/AssetDetails.vue，直接消费生成AssetOut与明确的设备显示／选择、Binning、保存绑定；集合字段进入datasets/DatasetDetails.vue消费生成DatasetOut。Root分别装配捕获原记录的保存函数，取消事件回传recordId；该身份可以是项目引用ID，不会被素材／集合ID替换。固定版本标题继续优先使用引用中的version身份，设备显示名仍采用已有快照解释。Dataset状态展示使用实际dataset.status，避免项目引用外层没有status时误显示未知。

SettingsPage的旧设备详情分支在activeArea非library且isEquipmentManagement为false的前提下不可达（activeArea仅library／settings，equipment／equipment-setups恰好被排除），已删除；实际设备编辑仍由RecordEditorForm和设备表格提供，没有恢复兼容分支。页面位置由具名插槽保持，不把保存回调放入第二份上下文。

验证：settings-details.xml原全57文件375项通过。独立详情初次settings-details-independent.xml为3项中1失败，新增零值断言未包含现有显示中的分隔点；修正预期后settings-details-final.xml全58文件378项全部通过。新增检查涵盖固定引用版本与操作身份、Gain／Offset及曝光0、快照名／非对称Bin、取消编辑返回引用而非实体身份。UI及原生类型通过（ui-settings-details-final-types.log、native-settings-details-types.log）。源码检查只剩WorkspaceRecords注入上下文；未部署或做科学运行。

G5未完成：WorkspaceRecords、RecordData、编辑服务／失效通知和新导入发现、其余查询及浏览器／依赖验收继续推进；不把本轮组件验证当作Siril或原生执行验收。

G5续记：WorkspaceRecords状态区和分页进入RecordsFeedback／RecordsPagination，两者只接收明确的格式化状态、数量／offset／有效页大小和阻拦标志。分页回传move(delta)与page-size，父级使用原Pinia界面动作；不读取服务或改写页码。读取失败时不同时显示空成功状态，保留请求标识；设备页仍只在完整结果超过50条时显示分页。

设备卡片进入equipment/EquipmentCards.vue，消费生成Equipment类型与明确选择／阻拦属性，以稳定ID回传选择、编辑、逐项与整页勾选。WorkspaceRecords适配层校验设备行并从查询原对象定位操作目标，展示用对象不作为第二份编辑权威。equipmentSubtitle()由卡片与原显示辅助函数实际复用，保持同名型号不重复、异名型号显示规则。该改造只分离实际区域，WorkspaceRecords仍是唯一上下文消费者，未换名为另一个万能容器。

验证：record-controls.xml前一候选全58文件378项通过；record-controls-independent.xml独立状态／分页4项通过。设备卡片抽出后的record-controls-equipment.xml相关4文件28项通过，包含独立卡片与设备管理回归，验证事件不修改父级Set；范围重叠，不合计为当前候选完整套件。UI及原生类型通过（ui-record-controls-final-types.log、native-record-controls-types.log）。未部署、未执行浏览器或科学运行。

G5续记：项目卡片进入projects/ProjectCards.vue，消费生成ProjectOut和明确选择／布局状态，仅回传稳定ID及整页选择意图。旧泛记录图标判断被实际项目类型替代，不引入未接入实体。集合引用表格进入datasets/DatasetReferenceTable.vue，输入只读DatasetReferenceRow显示模型，原DTO与操作留在适配层；recordId、datasetId、versionId分别保留，预览／选中回传recordId，FixedDatasetMembers接收明确的datasetId和固定versionId，不展开所有成员。

WorkspaceRecords仅生成这些显示行、从当前查询原行解析事件，并将实际复用的设备／组合／项目选择转发收敛为selectRecord(id)／toggleRecordSelection(id)。这些是当前表格的身份适配，不访问HTTP或建立Repository；素材混排与字段编辑表格仍待迁出，尚未删除最后的上下文。

验证：project-dataset-tables.xml前一候选全60文件384项通过；身份适配复用及独立视图新增后，project-dataset-views-final.xml相关3文件54项通过，检查父级Set不变、预览不触发行选择，以及引用／集合／固定版本身份不混用。UI类型通过。原生类型也通过（native-project-dataset-views-types.log），UI类型日志ui-project-dataset-views-final-types.log；未部署、未做浏览器或科学验收。

G5续记：素材／集合混排和固定成员的表格展示进入library/LibraryTable.vue，以tableTypes.ts的LibraryTableRow、InlineBinding、ParameterBinding接收显示值、逐字段保存函数及固定CanvasDataRequest。实际字段值、混合摘要解释、设备快照、旧Bin、错误及保存仍由现有适配层处理；表格不导入Root类型／上下文。每行事件按类型／记录ID／成员position形成的键定位原始行，避免把预览或展开误落到另一行；固定入图引用保留原有版本。

首轮library-table.xml全386项中2失败：第二次排序未作用，因为读取时整个新表格组件被卸载，旧按钮组件发出的事件被Vue丢弃。改为已有缓存表格读取期间保持实例、读取状态单独显示；同时避免行内草稿随10秒轮询卸载。library-table-current.xml相关55项通过。library-table-drafts.xml新增实际10秒刷新场景，确认未提交行草稿仍在，并以原base_revision=1提交而不改用后台revision=2；冲突可见且不自动重写。累计曝光标题和参数来源换行按原文案／格式保留。

行身份与最终候选library-table-final.xml全62文件388项全部通过；UI和原生类型通过（ui-library-table-final-types.log、native-library-table-types.log）。独立空表格验证无需Workspace provider即可显示列并回传排序意图。旧WorkspaceRecords源保留于g5/WorkspaceRecords.before-library-table.vue作为本次拆分前的回看证据，不作为兼容入口。当前WorkspaceRecords仅剩场景／绑定适配和最后注入，仍须删除；RecordData与后续失效／其他查询、浏览器及G6—G7未完成。未更新预览或做科学运行。

G5续记：最后的WorkspaceContext、workspaceContext对象和provide('workspace')已删除，源码中无对应注入。WorkspaceRecords成为受控场景组件，RecordsPresentation／RecordsBody明确区分library、datasets、projects、equipment、setups和none，字段直接引用各展示组件的公开props契约；不携带Root store、ref集合或私有业务命名空间。Root只装配显示／事件，四个页面通过records插槽复用同一RecordsPanel功能组件，没有新Vue应用。原混合成员范围业务断言从错误的展示组件实例移到实际拥有函数的Workspace实例，断言本身不变。

删除上下文后首轮records-presentation.xml全388项通过，原生类型暴露旧对象掩盖的4个未用导入、1项状态和11个未用包装函数；核对源码及测试调用后删除，没有保留伪导出，旧源码快照见Workspace.before-records-cleanup.vue。最终records-presentation-final.xml全63文件390项通过，含无provider独立空场景与具体项目场景事件检查。UI／原生类型通过（ui-records-cleanup-types.log、native-records-presentation-final-types.log）。拆除前WorkspaceRecords快照只作回看，不是兼容入口。

前端依赖检查初次仅报固定Hey API生成客户端内部types.gen.ts与utils.gen.ts的引用环；未手改生成文件。no-circular仍为error，仅从生成目录内部起始的边单独排除；自研到生成目录的跨界环仍会被其自研起始边检查，其余边界规则不变。最终records-presentation-dependencies-final.log：230模块／828依赖，无违规。该例外不是自研代码排除，也不宣称生成SDK无类型环。

G5仍未完成：RecordData、Root编辑与通知失效、新导入发现、其他能力查询和真实浏览器待继续；未更新预览或做科学运行。G6—G7未完成，不能将上下文清除记为整体重构达成。

G5续记：编辑表单不再使用Root的RecordData字典。workspace/useRecordEditor.ts以project／equipment判别Session管理生成DTO基准、明确UI草稿和原始草稿，提供model／dirty／source及创建、打开、同步、提交、关闭。模型更新必须匹配当前kind与持久身份，迟到旧目标更新不写新编辑器。设备更新只发送变更字段与基准revision，不把未修改的null规范化字段或规格重新提交；创建仍用固定生成schema验证。Root只协调保存／错误／列表刷新，saveEditorInline读取编辑基准而非后台最新列表行，原资产／集合编辑的遗留草稿分支已删。

验证：record-editor-owner.xml前一候选全63文件390项通过；record-editor-owner-boundaries.xml独立2项通过，覆盖旧目标拒绝、稀疏设备更新及原规格不变。UI类型还发现旧场景测试直接写只读feedback属性，已改为替换其受控对象，不改业务断言。原生首次native-record-editor-owner-types.log报4个旧创建schema／规格／草稿类型导入未使用，清理后双端类型通过（ui-record-editor-owner-final-types.log、native-record-editor-owner-final-types.log）。前端依赖检查231模块／836依赖无违规（record-editor-owner-dependencies.log）。报告范围重叠，不把独立2项与此前整套数相加宣称新全套通过。

RecordData仍用于查询行及部分参数／更新表达，尚未清零；失效通知、外部新任务发现、其他查询和浏览器／科学验收仍待完成。未更新预览或执行Siril处理，整体Goal保持active。

G5续记：参数写入和展示不再复用RecordData。保存参数使用生成AssetParametersPatch，分类使用生成AssetClassification，集合覆盖使用DatasetMemberParametersUpdate的parameters／classification；动态单字段与组合输入先经相应生成schema校验。临时构造payload改为unknown字典并在原边界验证，没有添加第二套HTTP类型。rowParameters／rowClassification返回生成契约与明确摘要视图联合。

library/summary.ts:summaryParameters按生成摘要的实际字段推导输出，保留数值字段的number／mixed／null区别，不再返回任意键宽泛字典。Binning的值、编辑值和旧值选择进入assets/binning.ts，以明确参数显示类型为输入；原混合、非对称与范围外值展示保留，编辑值不会暗中转成方形。Dataset Bin读取通过明确参数摘要收窄，Root不再将泛用string误当作合法数值。

验证：parameter-contracts.xml前一候选全64文件392项通过；parameter-view-boundaries.xml独立2项通过，覆盖0／null／mixed和非对称旧值保留，含类型断言确保gain不是任意string。UI类型通过；前端依赖232模块／839依赖无违规（parameter-contracts-dependencies.log）。原生类型也通过（native-parameter-contracts-types.log），UI类型日志ui-parameter-contracts-final-types.log。未部署、未做浏览器或科学处理；查询行与部分身份／快照仍为RecordData，尚未清零。

G5续记：activeDataset从RecordData改为datasets/viewIdentity.ts的DatasetViewIdentity，仅保留打开时的id／name／revision／member_count与明确固定version。openDataset从实际LibraryDatasetSummary构造，不再混合实体／版本／引用对象；无固定version时明确停止并显示契约错误，不猜测现行版本。calibrationUpdated消费生成DatasetOut，仅在明确确认后采用对应版本。

历史设备选择改为equipment/snapshots.ts的EquipmentChoiceSnapshot，源于生成LibraryEquipmentLabel／EquipmentSnapshots；Root删除遍历任意object后as RecordData的断言。投影区分实际设备kind和UI选择槽：旧telescope仍原样保留在观察快照中，只作为optical_system槽显示其名称和身份。空ID保持null，不创造可选择的注册设备身份。

验证：view-identities.xml前一候选全65文件394项通过；view-identity-boundaries.xml独立2项通过，确认外部摘要新增版本不改变已打开视图，只有显式ack才采用新版本，并确认投影不改写旧快照。UI类型与依赖检查234模块／843依赖通过；原生类型也通过（native-view-identities-types.log），UI类型日志ui-view-identities-final-types.log。未部署或执行浏览器／科学处理，通用查询行RecordData仍待消除。

G5续记：跨入口新导入发现已补齐。imports/queries.ts的可见任务目录在无活动任务时每10秒读取，以发现MCP／CLI新增任务；queued／running／cancelling时改为1.5秒，终态或interrupted暂停后停止高频并恢复10秒目录频率。此处是同一查询资源的频率调整，不是另一份任务权威；未增加timer、服务或执行器。卸载后观察者清理停止两种频率，继续传递AbortSignal；互联网断开仍按既定always模式访问本机。

该补记细化此前“终态停止轮询”：停止的是活动进度高频，保留普通可见目录的低频发现，与既定可见列表10秒策略一致。旧通知去重、暂停恢复、真实状态和不自动重放写入保持。

验证：import-task-discovery.xml任务18项通过，新增空目录10秒发现外部任务、1.5秒活动读取、终态回落和卸载30秒无新请求。import-discovery-final.xml全66文件398项全部通过，UI类型通过；原生类型也通过（native-import-discovery-types.log），UI类型日志ui-import-discovery-types.log。未部署或做真实导入／科学运行，不能用组件计时器检查替代实际MCP跨入口浏览器验收。

G5续记：导入受理、登记进度和完成三个通知入口不再直接loadRecords／refetch，改为invalidateImportedLibrary()按当前workspace的library资源键失效；由Query决定活跃／暂停查询的读取。覆盖同资源筛选与摘要缓存，不全局清空缓存；用户主动刷新与明确保存后的原流程未改。本项不宣称所有写入或能力通知已审完。

验证：import-invalidation.xml相关3文件55项通过；import-invalidation-paused.xml相关36项通过，新增实际页面场景：行内POST等待时收到registered通知不增加素材读取，确认完成后列表更新且POST仅一次。双端类型通过（ui-import-invalidation-final-types.log、native-import-invalidation-types.log）。未部署、未执行实际跨入口浏览器或科学运行；RecordData和其他能力查询仍待继续。

G5管理选择续记：项目、设备、组合的勾选Map不再保存RecordData整行；由trash/selection.ts使用生成DTO的有限身份／名称／revision和资源判别。确认框打开时固定选择，不再以空row占位或在确认时读取变化后的Map；单项与批量统一确认，等待行内写入前阻止重复确认。项目恢复移除没有实际调用的通用设备／组合分支。主体查询行和其余写入失效归属仍未完成。

验证：management-selection.xml页面37项通过；management-selection-full.xml整套自研UI400项通过（含此前通知检查，不与其重复相加）。新增实际挂载页面场景验证确认打开后收到第二个项目勾选事件，确认文案与提交范围仍为原先一项／原revision，POST只有一次，另一项目保留。UI类型通过；依赖检查235模块／847边、无违规。原生类型首次发现删除通用分支后遗留的未用导入，已删除并复验通过（management-selection-native-types.log）；没有扩大生产行为修改。未部署／未执行本轮真实浏览器和科学运行；不计为G5或整体Goal完成。

G5素材移除续记：libraryRows直接引用Query生成摘要，选择／确认不再以RecordData整行或asset／dataset克隆作提交来源；新librarySelection.ts仅投影LibraryEntryRemove与确认展示资料，保留审阅时的revision／固定version_id。素材删除入口限定摘要库列表，校准挑选数据不伪造成素材删除DTO。请求仍通过生成契约与既有HTTP能力，不创建第二份数据库或科学输入。

验证：removal-review-full.xml整套66文件／400项通过；removal-review-types.log UI类型通过；removal-review-dependencies.log为236模块／849边、零违规。与前一份400项报告重叠，不累加。后续仅调整菜单分组以保留原有回收站入口，removal-review-final.xml页面37项复验通过，原生类型最终复验通过（removal-review-native-types.log）。未构建部署，未跑本轮浏览器／科学处理；G5及整体Goal仍进行中。

G5回收站续记：组件已从workspace移动至trash能力目录，旧导入删除；顶层列表／组内分页独立使用Query键和AbortSignal，不再共用readGeneration或手抄rows／total／loading。查询10秒刷新；勾选、预览和写入暂停读取，关闭及切工作区取消旧读取。恢复／删除采用两个无自动重试mutation，settled后只失效原工作区受影响资源；Root不再通过changed强制refetch。预览的selection／fingerprint继续明确保留。实际部分失败在刷新、组内第二页收尾后仍显示，不因清理UI状态抹去；尾页回退不使用正在刷新中的缓存总数。

验证：trash-query-full.xml，UI包现有全部自动化测试66文件／406项通过；trash-query-final.xml为组件移动后58项调用方检查，与全量报告重叠不累加；trash-query-types.log UI类型通过；最终候选原生类型通过（trash-query-final-native-types.log）。trash-query-final-dependencies.log为238模块／860边、零违规。新检查实际挂载组件，覆盖切组和关闭时signal.aborted、工作区迟到响应、10秒发现／选择暂停／关闭停止、普通及组内第二页部分删除失败、读错误不冒充空列表、旧缓存总数不取消新分页。原有竞态测试补充flushPromises以先证明请求已发起，再判断真实取消；没有弱化过期结果断言。

失败与修正：新增测试最初预览响应错误使用selection DTO代替真实LibraryTrashItemOut，已按生成契约修正；服务失败按真实错误响应模拟，非成功响应；部分失败状态文案断言修正为既有翻译。新增缓存场景进一步收紧尾页判断，仅在成功读取结束后执行。未构建部署、未执行本轮浏览器／科学运行；“全部自动化测试”不等于UI整体重构完成。G5及整体Goal仍进行中。

G5软件续记：宿主通过UI公开hook读取真实workspace，再装配必传workspaceId的软件界面。目录／详情／发行版本拆至software/queries.ts，删除组件手写load状态、generation和轮询定时器；运行操作1秒读取、其他目录／状态10秒，发行版本仅打开或显式刷新。安装／卸载提案及原生确认拆至software/mutations.ts，重试关闭，settled按原工作区资源失效。未知回执先查原包／operationId；UI actionSession仅保护旧目标回执，不管理读请求。读取AbortSignal已贯穿真实生成SDK。外部安装／卸载更新版本选项，保留未提交版本选择；只有实际running显示进度。

验证：software-query-full.xml，UI包现有全部自动化测试66文件／411项通过；software-query-final.xml软件专项37项通过，重叠不累加；software-query-final-native-types.log原生类型通过，software-query-types.log UI最终类型通过。依赖检查240模块／880边、零违规。新增场景证明：丢失提案回执后只提交一次、读取原包恢复真实待确认计划而不自动确认；切工作区取消旧读取且不展示迟到状态；真实SDK传播取消信号；没有本地动作的外部安装／卸载能改变已安装选择，且不重复检查发行版本或执行动作。初次新增计划标题断言把Dialog title误当成内容文本，已按现有控件属性修正；最终UI类型发现测试Deferred Promise被推断为unknown，已补生成SoftwarePackageDetails类型并复验。关键有限动作与原操作读取断言保留。

限制：未构建部署、未进行本轮浏览器、实际安装／重连或科学处理。既有migration_required业务分支不据此宣布清理，后端workflows、完整图快照及SDK v1仍待G6。G5尚有主体查询行RecordData、其余能力与最终浏览器验证，整体Goal保持进行中。

G5固定资料续记：新增library/materialRecords.ts，将画布来源、固定素材／集合引用、预览成员与路径及缩略图身份从RecordData读取中分离，全部基于有限生成DTO联合和生成Zod。集合选择的entry_type UI标记与查询缓存还原共用一个转换；不引入第二套公开DTO、旧输入回退或科学输入来源。修正两项实际错误：同一素材多个固定成员版本的缩略图曾共用asset.id；原件就绪曾优先取asset.current_version而非成员固定version。现以版本／位置独立显示，并以固定版本可用性判定。

验证：material-record.xml成员及页面60项通过；material-record-full.xml UI包现有全部自动化测试66文件／413项通过，二者重叠不累加；material-record-types.log UI类型通过；material-record-dependencies.log为241模块／883边、零违规；最终原生类型通过（material-record-final-native-types.log）。新增真实挂载页面证明：重复素材两个固定版本各自缩略图不同，入图引用依次为对应版本，第二项预览也指向第二固定版本，未访问素材当前版本；固定版本missing而当前版本available时显示“原件异常”并没有入图来源。预览允许既有display/auto-stretch显示请求，不把它误记为科学原件写入。

定位记录：首次生成DTO严格校验识别到选择列表的UI entry_type标记与成员投影额外字段，现只显式还原已存在的UI投影，并复用唯一生成约束，没有改为宽松接受未知API字段。最初新增预览测试误断言完全无POST，已改为仅允许第二固定版本的既有显示预览请求，保留所有固定版本断言。未构建部署、未执行本轮真实浏览器或科学处理；主体RecordData及G6—G7仍未完成。

G5主记录闭合续记：Workspace的Record<string, any>／RecordData已删除，以生成DTO和现有Query视图闭合为WorkspaceRecord。recordTypes.ts集中实际类型守卫、嵌套实体、固定版本以及有类型的Asset／Dataset回执。编辑接口依据记录实体选择，Query页及所选资料按相应实体更新，不跨类合并DTO；重复素材成员共享可编辑资料，但保持各自固定version和position。成员页setter不允许非成员记录；Project引用保持自身reference id。

验证：closed-row-full.xml UI包现有全部自动化测试66文件／413项通过；closed-row-shared-asset.xml成员与页面60项通过，重叠不累加；closed-row-types.log、closed-row-final-native-types.log双端类型通过；closed-row-dependencies.log 242模块／890边零违规。扩展页面场景在两个固定版本的重复素材上执行一次资料PATCH，两行名称同步，两个原有画布来源保持相同版本，第二条预览仍为第二固定版本。源码定向检查Workspace／recordTypes无RecordData、any或as unknown as。

定位修正：有限联合初次产生163处不成立的属性访问，已按真实数据归属收窄，未恢复可选字段袋或类型断言；严格DatasetOut解析发现选择标记，复用既有datasetChoiceToRecord还原实际DTO。原生类型发现未用生成schema导入，已删除。一个校准测试把完整DatasetOut与LibrarySummary拼为历史混合对象，改为真实摘要输入，保留“只匹配部分成员不可编辑完整范围”和无写入断言。

当前限制：G5仍需固定成员展开等剩余读取组件与写入失效检查、主页面职责拆分收尾、隔离构建及浏览器验证；本轮未部署，科学处理与G6—G7未完成。不能将闭合记录联合完成视作G5或整体Goal完成。

G5固定成员展开续记：FixedDatasetMembers从workspace移至datasets目录，新增工作区显式props并复用固定成员Query；删除手写JSON读取、响应副本、generation与请求控制器。图片URL继续视图持有，由共用useThumbnailUrls管理；显式refresh支持相同图片多个可见位置一次读取并发布，位置token阻止旧读覆盖新图，关闭释放所有URL。Workspace的显示更新同样采用此有限二进制刷新，不强制读取整份资料列表。固定版本与顺序保持。

验证：fixed-browser-full.xml，当时UI包现有全部自动化测试66文件／414项通过；随后只补两项折叠／工作区切换取消场景，fixed-browser-final.xml最终专项19项通过。两份报告重叠，不把新增项相加宣称全量416。fixed-browser-types.log、fixed-browser-native-types.log双端类型通过；fixed-browser-dependencies.log 242模块／892边零违规。场景证明旧signal被取消、迟到成员不出现；同一版本多个成员位置刷新只请求一次图片；旧批次字节迟到不覆盖新URL，dispose全部释放。已有分页只读固定版本、不读取整份集合及当前版本B不替换固定A断言继续通过。

定位：初版对每个别名分别读取，既有测试发现10处别名刷新请求变为10次，已改为一次读取发布多处显示，保留原来一次读取断言，没有放宽测试。未构建部署、未运行本轮真实浏览器或科学处理。G5仍进行中，接下来核查其余服务数据读取与编辑归属，再做隔离构建与浏览器验证；G6—G7仍未完成。

G5实际构建与浏览器续记：已通过固定入口在modernization-current／modernization-preview构建、启动两私有服务，端口32588／32590，最终回执387b10ec310542969aed931e608bad7a（HEAD仍bbb6f4a、dirty，未提交）。此前“未部署”均为各次候选当时状态；当前预览已包含G5查询和组件改造。准确阶段和日志见.artifacts/dev-prepare.json及对应run目录；未操作旧Feature／共享／默认workspace。

真实浏览器：browser-g5-six.xml六项通过，覆盖实际摘要、固定成员50+2分页、曝光0保存、原版本内容观察、生成契约、跨入口改名10秒发现、后台刷新不覆盖草稿且原revision保存被真实409拒绝、浏览器报告离线后仍读取本机服务。browser-g5-software.xml追加软件侧栏只读挂载一项通过：真实health的workspace与合成seed一致，读取Siril包详情且没有安装／卸载／prepare动作。共7个不同场景，重跑与失败记录不累加。

发现并修正实际接入错误：真实双击名称时第一次click已启用原生放置，全局document pointerup捕获会在dblclick取消前添加Data节点；失败trace实际记录POST library/canvas-data，画布从空变为Data节点。LibraryCanvasSource.vue仅增加mousedown捕获阶段取消已有原生放置，单击随后仍可重新启用；没有改上游ComfyUI拖放实现或新增画布机制。browser-name-pointer.xml原生13项通过，按真实pointerdown／mousedown／pointerup／click／dblclick顺序证明没有意外写图，既有单击落点、拖放、Escape和固定源测试保留。browser-pointer-native-types.log原生类型通过；重新构建后浏览器验证原生草稿图节点不变。

测试定位修正：最初新增测试用原名称hasText定位编辑器，名称变为input后定位失效；另一个把普通文本输入当searchbox。已按实际控件修正，不改业务来迎合定位器；错误trace均保留。随后观察到的真实写图问题单独修复，未放宽画布不变断言。跨入口改名在finally读取最新revision后恢复原名称；52份G2合成原件SHA-256全部保持，证据browser-originals-check.json，范围不扩展为所有文件或真实照片。

限制：以上是私有环境实际浏览器＋真实本机API和合成素材验证，尚未执行本轮Siril科学处理、完整导入到保存闭环或所有计划浏览器场景。未证明G5全部完成；剩余服务读取／编辑职责、G6后端workflows与SDK v1清理及Bundle重构、G7完整验证仍待推进。预览http://127.0.0.1:32588，服务http://127.0.0.1:32590。

G5导入报告／预设读取续记：报告和导入表单移到imports，CapturePresetPicker移到equipment，旧导入路径删除、所有调用方同步workspaceId。问题报告用Query聚合分页并传递取消信号，活动任务1.5秒、终态停止；未读齐声明总数即遇空页时明确错误，不给出部分成功报告。重试用无自动重试mutation，失效原工作区任务并核对旧回执目标；失败列表读取有误不能提交。预设目录用Query／readPages 10秒刷新，保留选中身份及手工Gain 0，删除后的选择显示不可用而不静默清除。

验证：import-report.xml报告与任务25项通过，覆盖完整报告异常、工作区取消、旧重试回执不关闭新分类。import-lifecycle-full.xml首次并行全量420项通过、一个既有真实成员夹具场景5秒超时；import-member-diagnostic.xml该文件23项单独通过；import-lifecycle-serial.xml保持默认超时／零重试、单worker完成66文件／421项通过。两项新预设场景分别验证目录改名或移除后仍保留预设ID和Gain 0，且不产生导入写入。import-lifecycle-types.log与import-lifecycle-native-types.log最终双端类型通过，依赖242模块／892边无违规。

定位修正：新增workspaceId揭示SettingsOrganization中一个独立导入表单挂载漏传，已同步；原生类型发现uiT未用，改为保留原组件非Error异常的既有提示，未用虚假引用掩盖。并行超时未重现于单文件及串行全量，没有放宽断言／超时或引入自动重试。

最后导入表单增量：移除equipment的any数组与loadEquipment分页，直接复用工作区设备Query，保留只读选项与手工参数草稿。import-lifecycle-final.xml三个直接调用方文件31项通过；import-lifecycle-types.log、import-lifecycle-final-native-types.log最终类型通过。此前单worker全量421项对应此最后增量前的候选；未将两份结果相加或宣称这一步已重复全量。

部署限制：最近私有预览仍为387b10ec310542969aed931e608bad7a，对应前一轮7个浏览器场景；本轮导入界面改造尚未重建部署，不沿用此前浏览器通过作为本轮证明。G5剩余读取／编辑职责与浏览器收尾及G6—G7仍未完成。

G5旧编辑器清理续记：全量src／原生接入检索确认AssetEditor、DatasetEditor无产品调用，仅测试挂载，删除两组件与旧专属测试，不保留兼容入口。旧AssetEditor Gain 0与冲突草稿两项迁到Workspace.asset-editing.test.ts的真实App入口；旧DatasetEditor有效规则对应当前Workspace.regression的枚举编辑、保存后读取、失败草稿独立取消，以及dataset-groups固定成员规则。恢复副本／原字节SHA-256／未提交补丁先保存到retired-editors证据目录，未丢失未提交内容。

验证：retired-editors.xml三个当前业务测试文件62项通过；retired-editors-types.log及retired-editors-native-types.log双端类型通过；retired-editors-dependencies.log 240模块／878边零违规。迁入测试严格断言请求仅{base_revision:4,parameters:{gain:0}}，没有offset／classification／current_version_id；服务冲突保留Draft name及原revision，只发一次请求，原asset对象不变。Source检索无旧组件名，恢复四文件hash已核验。

范围：retired-editors-full.xml清理后单worker全量65文件／418项通过；与专项62项重叠不累加，也不沿用删除前421项作为本轮数量；真实浏览器仍对应最近部署387b10候选。本项未重新构建部署，不宣称完成G5或后续科学验证。

G5查看所有者续记：Workspace的照片／原生查看器编排已提取useLibraryPreview，关闭与scope dispose取消当前首读和所有后续懒成员读取；调用方信号与所有者信号合并，旧目标响应／错误不发布。固定版本、first member limit=1、position顺序及完整范围总数保持；PreviewPhoto视图类型归media/previewTypes，各消费者同步，不留旧组件类型导出。Workspace不再维护photoPreviewRequest读代次及四个旧包装函数。

验证：preview-owner.xml相关页面73项通过；preview-owner-cancellation.xml新所有者3项通过，二者范围不同但不将其冒充整个UI包；preview-owner-types.log与preview-owner-native-types.log双端类型通过；依赖242模块／889边零违规。新场景实际检查AbortSignal：关闭待首读后无照片／查看器及错误，换成新固定照片后旧集合迟到不覆盖，关闭原生查看器使正在读的后续成员和原先回调都以AbortError结束。这里只证明普通读取被取消，不声称科学进程已停止。

preview-owner-full.xml单worker全量66文件／421项通过，报告范围不相加。本轮源码未重建部署；7条真实浏览器结果仍仅对应上一轮387b10候选，Siril科学处理与G6—G7仍未完成。

G5大图预览查询续记：PhotoPreviewDialog移至media，删除组件手写loading／error／generation／500ms定时轮询。usePhotoPreview将明确生成和自动状态读取分为无重试mutation、Query，状态失败停止轮询且不重新提交生成；Blob读取也是工作区／固定目标下的Query，Object URL由视图创建释放，关闭／换目标取消信号。当前没有引入后台服务或另一套科学输入。组件只保留焦点、Escape和图片解码失败的呈现。

验证：photo-query.xml专项15项通过；photo-query-types.log、photo-query-native-types.log双端类型通过；photo-query-dependencies.log为243模块／895边无违规。保留每张图仅请求生成一次、已保存配方读取、正在进行的普通预览结束后确保自动配方、原件未就绪不伪造图片、关闭后不处理迟到响应及精确project-reference路径等断言。新增状态GET失败后3秒内仍仅一次POST／一次GET／零图片请求，以及浏览器图片解码错误后显式重试能重新展示图片。

photo-query-full.xml单worker全量66文件／423项通过，与专项不累加。本轮源码未重新部署，当前预览仍是387b10旧候选；不能把此前7条浏览器通过用于证明本轮。G5审计仍有剩余页面职责／读取与构建验证，G6—G7未完成。

G5项目引用mutation续记：项目素材／集合固定引用的四个写入从Workspace直接API调用迁至projects/mutations.ts，body由生成客户端参数推导、重试关闭，settled只失效原工作区projects资源。Workspace保留固定选择及导航上下文，旧成功／错误不修改新工作区／新项目／新选择，删除采用服务返回revision；选择模式新增成功才装配新列表，删除不重复强制读取。按钮pending禁用、入口检查防止重复提交。

验证：project-reference.xml两文件／40项通过，包含全部既有引用行为及新增迟到回执：A移除等待时切到B revision17，A完成revision5不影响B；仅发一次DELETE且B详情仍显示。project-reference-types.log UI类型通过；project-reference-native-types.log原生类型通过；依赖244模块／900边零违规。创建接口没有返回项目revision，UI仍依现有服务单次写入递增一次不变量更新捕获的旧基线，不将新API结果字段伪造出来。

定位修正：初次替换引用handler区间时误含四个相邻导航／筛选函数，类型检查揭示缺失；已从既有工作副本精确恢复setQuery、openManagementFilter、applyManagementFilter、clearManagementFilter，并复验搜索／排序／过滤。没有恢复旧引用实现或放宽断言。

project-reference-full.xml单worker全量66文件／424项通过，专项不重复相加。本轮未部署；最近7个浏览器场景仍为387b10候选，不将其当本轮证明。G5及整体Goal仍进行中。

G5导入流所有者续记：useImportFlow管理文件选择、确认、命名、问题详情和追踪任务；Workspace不再定义这些ref或startImport／localFilesSelected／importSubmitted／importRegistrationCompleted／importTaskCompleted实现。选项只含真实workspace、UI选择清理和通知边界，不重建万能上下文。任务事件只失效当前library资源，保留查询暂停及固定读取；工作区改变清空上一范围意图。没有新增后台任务或科学输入来源。

验证：import-flow.xml现有页面／任务58项通过；import-flow-owner.xml新2项通过，证明换工作区后旧选择及任务不残留，三类事件严格调用当前libraryQueryKey失效且不生成通知／写入。import-flow-types.log、import-flow-native-types.log双端类型通过，依赖245模块／905边零违规。初次直接从generated导入LocalImportFile失败，已核对其为api/contracts现有LocalSelectionFile+root_id的本地投影并复用原定义；未新增手写公共DTO。

import-flow-full.xml单worker全量67文件／426项通过，专项不重复相加；本轮源码尚未部署，仍不沿用387b10的7条浏览器结果。G5其余职责与审计、更新构建验证及G6—G7未完成。

G5校准编辑 Query 续记：编辑器由 workspace 迁至 datasets，使用工作区／集合／固定版本查询键；响应留在 Query，表单保存明确的 revision 与固定成员基线。未编辑时 10 秒刷新，草稿与写入期间暂停读取，关闭中止请求。版本发布成功与资料核实失败分别表达，重新读取不会再次发布，未保存描述保持。

验证：calibration-query-lifecycle.xml 两文件 36 项通过；新增场景为草稿暂停后台读取并使用原 revision、已发布但核实失败后仅重读且保留描述、关闭取消全版本读取、无草稿刷新并采用新 revision。最初错误模拟使用普通 Error，接口错误分类与预期不符；改用真实服务错误契约的 503 后通过，失败报告 calibration-query-draft.xml 保留，未以放宽产品校验解决。calibration-query-full.xml 为单 worker 全量 68 文件／432 项，零失败／错误；专项与全量重叠不累加。calibration-query-final-types.log、calibration-query-native-types.log 双端类型通过；calibration-query-dependencies.log 为 246 模块／911 依赖，零违规。

本轮固定入口完成私有预览重建，回执 `2e698e20cbbb4b948d69c9e4f5190ccc`（89.833 秒，非冷准备），网页 http://127.0.0.1:32588，服务 32590；完整回执 calibration-preview-receipt.json。calibration-browser.xml／json 为真实 Chromium 的 8 个不同场景，全部通过；新增场景明确读取 52 个固定成员及其顺序、编辑后 11 秒不读取集合资料、无 API 写入、画布节点未变化，另回归摘要分页、0、跨入口刷新、草稿冲突、本机断网读取及原生软件页。calibration-originals-check.json 核对 52 份 G2 合成 FITS 原件 SHA-256 均未改变。已查看本轮页面截图；不据此宣称全部视觉或科学验收。未执行 Siril 科学处理；完整 Goal 保持 active，G5 其余职责／写入失效审计及 G6—G7 尚未完成。

G5初始化Query续记：useLibraryBootstrap并行读取生成health及capabilities，Signal由Query管理。Workspace不再在onMounted内依次读取并回写能力／身份，capabilities与能力错误为直接计算值；实例内workspace字符串仅作为后续资源作用域，列表在成功数据到达后装配。待定／失败不显示空库结论。

验证：bootstrap-query.xml页面46项通过；bootstrap-query-final.xml两文件40项通过（包括原有页面与新取消／初始失败边界，和46项重叠）；bootstrap-query-types.log、bootstrap-query-native-types.log双端类型通过；依赖245模块／905边零违规。新初始化所有者测试检查两个signal在最后页面卸载后实际aborted，迟到响应不发布；真实SDK错误模拟503后页面显示服务不可用、不声称空库且无写入。原生类型定位旧catalogApi导入已无使用，移除后复验通过。

限制：只改变初始读取及其取消，没有新增或宣称完整服务重连策略。bootstrap-query-full.xml单worker全量68文件／428项通过，专项不重复相加；本轮源码未重建部署，7条浏览器仍仅对应387b10候选，G5及G6—G7未完成。

待继续：编辑职责和其余能力查询、能力页面拆分、万能上下文删除、跨入口低频刷新、草稿保护与失效规则；活动轮询停止后如何发现跨入口新任务，随可见列表刷新一并落实。G6—G7仍未完成。

<a id="modernization-g4"></a>

## 现代化G4：实际FastMCP／CLI替换（阶段完成）

G4收尾审计closure-audit.json已通过；整体Goal继续G5，不是整体重构完成。最终97项类型化工具覆盖原81项操作，7项主要列表直接复用HTTP／客户端／工具查询模型；新增固定引用PNG预览、消费者释放及已有CLI预览文件导出。错误统一ToolError/isError并保留字段和请求标识，所有子层策略一致。

当前证据：preview-final.xml 45通过；protocol-current.xml原6项中5通过，第6项正向预览与导出已完成，仅因旧stderr断言失败，修正为官方CLI实际输出后preview-protocol.xml该项通过。两报告共同覆盖6个原有协议业务场景，不相加计作7项。保留了注册设备／组合内设备、预设0、固定集合／校准null、项目固定引用、未知写入、JPEG图片与独占文件写入断言。最终差异在测试解码／包装／新命令规则，没有生产兼容表。

final-source-audit.json验证完整目录97、原81覆盖、旧实现不存在、CLI／目录重复生成一致且无本机路径烘焙；final-ruff.log通过，UI／native类型检查通过。909项仅收集，不是全部执行。Skill quick_validate通过，资料包未修改。development/development.json记录官方reload工厂新标记、worker PID变化、HTTP显式重连和2个新stdio会话，读取同一总数53，探针自有进程树已清理。

旧源退役曾被自动审批拒绝；检查11个文件（8个有未提交类型／导入调整）并保存字节一致原文、补丁及SHA256后重新获准，恢复清单保留在g4/retired-source-recovery。没有丢弃用户内容、绕过审查或操作默认workspace。整体待办仍是G5页面／查询、G6后端workflows及完整图／SDKv1／Siril改造、G7真实科学与完整闭环验收。


G4续记：97项工具已包含7项共享query、Bundle PNG预览／204消费者释放及既有独占文件导出。ProjectQuery／DatasetQuery同时进入HTTP／Python客户端／MCP；其他5类复用既有模型。旧Registry、tools网关、locale助手及手工业务commands共11文件在逐项检查并校验恢复副本后退役；自动审批最初拒绝未审查批量删除，补充检查与字节恢复证据后通过，没有绕过审查。原文／差异清单见g4/retired-source-recovery/manifest.json。

preview-final.xml 45通过，含实际生成CLI的不覆盖目的文件、图片内容、节点短摘要／单会话批读、语言不修改原定义、共享query及PNG／释放检查。collection.log为909项仅收集通过，不表示909项运行。项目Skill按skill-creator约定更新，quick_validate通过；系统Skill、全局MCP与默认workspace未修改。

官方开发探针development/development.json通过：两个新stdio会话、真实create_server目录的临时HTTP reload、修改工厂文件日志标记、前后worker PID不同、明确新HTTP连接查询相同只读总数53；finally停止自身进程树。首次失败是reloader调用环境缺当前venv PATH，补入进程级PATH后成功，没有改框架或增加常驻服务。

协议测试迁移保留原6项业务流程。初次失败定位为框架对union/list的result包裹、旧describe调用和数组参数flags；不增加生产兼容表。另修正迁移误改的members字段、列表名lists及UTF-8子进程捕获。MCP业务域已通过；CLI完整业务流程已走完正向断言，负向捕获因未指定解码导致stderr=None，已显式UTF-8。最终整组protocol-current仍在执行，未标成功；阶段审计尚未结束。


固定fastmcp4.1.4／cyclopts5.3.2；新server已实际替换旧双网关执行入口。完整94个工具按data／software／graph组合，Agent列表为框架search_tools与call_tool，已知名称可直接调用；描述含中英文及明确词项，BM25不是语义模型。构建目录／生成CLI离线，不创建业务客户端。

shared-errors.xml 3通过：覆盖目录不含注入参数且无业务I/O、共享客户端开关一次、手工null／gain0不混入缺省值、业务错误保留code／字段／request_id并使用isError、双语检索最多10项完整schema、已知工具直达及原生JPEG内容。CLI生成94项，root-help／asset-help离线通过；local-status.json验证当前私有workspace running，cli-assets-list.json为生成CLI→真实stdio→HTTP的limit1分页成功。Ruff本轮新增／替换源文件通过；仅把框架不可变依赖标记Depends／CurrentContext登记到B008合法调用，没有排除模块检查。

已定位并修复的失败保留：受限Windows异步目录探针挂起，确认后终止并用实际权限重跑；子ctx.lifespan_context不含根client，改用根请求上下文；返回AssetClient被依赖引擎当contextmanager逐调用关闭，改用官方asynccontextmanager借用；挂载执行会先屏蔽非ToolError，统一转换移到类型保留的函数边界。生成CLI初次未转发自定义env，子进程尝试不存在的默认配置后退出，没有操作该默认workspace；现明确转发选定配置和UTF-8并通过私有真实调用。

尚未完成旧Registry／tools／commands删除、共享query契约收敛、全部能力审计与软件预览、旧协议测试和Skill／示例同步、热重载及重连。当前旧测试导入_parser等仍需改写；本记录不代表整套测试通过，也不是G4阶段完成或Siril科学验证。G4 evidence/progress.json的complete保持false。


<a id="modernization-g3"></a>

## 现代化G3：契约、客户端与生成链（阶段完成）

G3收尾：closure-audit.json逐项核对后通过，整体Goal仍未完成。全部143个公开operationId现在显式固定，135处原自动ID写入路由声明而保持生成身份不变；所有422及默认错误均声明实际ErrorEnvelope，不再生成HTTPValidationError。最终运行服务的143操作／268 schema与本地OpenAPI逐项相等，19个OpenAPI／TS文件重复生成相同。

JsonValue的空schema在生成输入中等价展开为递归JSON，TS与Zod不再退化为unknown；9项新场景覆盖嵌套值、null／0、函数／undefined／非有限数。软件面板完整替换的服务快照改用shallowRef，避免递归类型深层展开。原生确认回执经生成schema校验，非法关联回执以invalid_response结束原请求、不重放。

最后的手写调用／分析DTO已删除：具体调用客户端归software/calls/client.ts，AnalysisView归data/results；UI包workflows目录、未引用bundleDevelopmentSource schema及旧通用JSON get/send全部删除。旧传输测试转到真实生成SDK，保留取消、冲突、畸形响应、稀疏写入及JPEG断言。分析、调用与输出端口声明实际序列化默认字段必需；链接构造仍定位原生prompt／call／端口／成员，后端调用和结果归属继续在G6完成。

实际部署发现原生runtime缺httpx；requirements及Windows锁补固定httpx0.28.1／httpcore1.0.9，保留httpx2。离线缓存缺wheel后仅下载固定版本，固定入口重建并成功启动。还发现受限进程查询曾报告stopped、实际权限下仍running；按真实私有PID身份停止后继续，没有操作旧Feature。此权限下未知状态表达问题保留到G6，不能据受限查询断言实际停止。

可见浏览器发现BundlePreview初始化失败：共享请求器把原生fetch作为对象方法调用。新增native-fetch-receiver-red.xml先失败，普通回调修复后的green报告通过；浏览器检查现在同时捕获扩展内部吞掉的初始化错误。修复后ui-native-fetch-final.xml 341通过、浏览器3场景通过，IAB标签3刷新后错误提示消失，显示原生未命名画布与2条素材记录。浏览器首次失败为旧workspace种子ID，保留browser-seed-mismatch报告并添加当前workspace健康身份预检。53份合成原件SHA-256保持一致。

本阶段各报告范围有重叠，不相加：error-contract.xml 30通过，call-contracts.xml 43通过，json-value-native.xml 29通过，UI341、最终浏览器3通过；双端类型、生成器配置严格类型与构建通过。最终成功启动回执ad53a51d284d46f7aba54362c07f9e89；私有32588／32590。尚无真实Siril科学运行验收；旧MCP／CLI留待G4，Vue Query／万能上下文留待G5，后端workflows／完整图快照及Siril内部留待G6。


已阅读固定版本HTTPX clients和FastAPI response-model／handling-errors本地正文。根AssetClient保留公开组合，连接、配置选择、JSON请求与关闭归interfaces/client/transport.py；唯一ServiceApiError归errors.py，客户端内部不再反向导入根client。修复非对象错误正文导致属性异常的问题，明确返回带请求标识的INVALID_RESPONSE。

ServiceHealth／ServiceCapabilities归contracts/system.py；导出目录选择复用DirectorySelectionResult。三个操作固定operationId。HTTP错误使用ErrorDetail／ErrorEnvelope实例生成；OpenAPI及六项Hey API生成文件同步，未手改生成物。

证据：`.artifacts/reports/modernization/g3/client-transport.xml`为62通过；后续system-contracts.xml为41通过（含部分重叠检查，不相加冒充独立场景数量），覆盖公开入口、连接关闭、无效错误正文、真实TestClient响应、请求标识、离线schema、生命周期和边界。前端vue-tsc通过。尚未刷新预览或完成G3其余调用方／媒体响应改造；G3及整体Goal未完成。

G3接入归属补记：节点public仅显式导出，存储／绑定／纯差异／定义写入分开；节点HTTP归interfaces/http/nodes.py。导入检查、批次、内容观察、显示预览、媒体和配置删除的HTTP已全部移出data，data/routes.py删除；core/http.py迁为interfaces/http/dependencies.py，所有调用方更新。data／nodes全部递归禁用HTTP依赖，public与catalog双向导入顺序、data.public不加载HTTP框架均实际通过。具体路径见文件计划4.3。

G3删除／导入独立组件补记：新增api/trash.ts的createTrashClient，六项真实操作涵盖素材回收站分页／恢复／预览／永久清理与设备直接删除预览／执行。EquipmentDeleteDialog删除手写预览和结果DTO，EquipmentDeleteItem从生成选择契约派生；LibraryTrashDialog保留选择、有限确认指纹、部分失败、翻页清空与恢复限制，改用具体SDK。

新增api/imports.ts的createImportClient，list／get／resume／retry／submit／select直接调用生成SDK，ImportTasks、ImportIssueDialog、ImportDialog和LocalImportPicker已消费；原1500ms活动任务观察与内容／预览独立通知仍由现组件维护，G5再交Vue Query统一。恢复接口本就无正文，SDK不再发送旧空JSON。导入草稿通过生成CreateImport校验且保留稀疏值；设备选项读取复用catalog SDK；本机选择保留取消信号，未增加浏览器文件上传或设置跳转。

证据：trash-sdk-fixed.xml 30通过；import-picker-sdk-fixed.xml 21通过；trash-import-regression.xml 33通过；trash-import-sdk-verified.xml完整UI 326通过。UI类型检查与native-trash-import-sdk-fixed.log通过，diff检查通过。trash.test.ts证明只读影响不会自动删除、确认使用原指纹以及丢失回执不重放。

失败修复记录：首次两项回收站延迟测试在SDK请求尚未开始时调用resolver，现等待实际请求建立；选择器五项也按实际异步开始验证关闭／卸载／快速重试和新旧选择隔离。旧resume断言改为无正文协议。完整回归中的5项旧回收站样例缺少真实响应必有source_dataset_id，补为null并保留原身份／取消断言后通过；未放宽生产schema。未部署预览或宣称新浏览器／真实Siril处理通过。

G3独立客户端补记：assets.ts使用三个生成operation实现读取／内容观察／接受；AssetEditor使用现有catalog和mutation。datasets.ts提供固定集合、版本摘要／详情、校准目标及创建／发布。CalibrationBindingsEditor不再将无members的版本摘要当完整详情；版本切换实际读取选中详情，读取时禁止编辑。CapturePresetPicker与Workspace健康读取均走生成operation。

PhotoPreviewDialog通过display.ts使用生成Fetch／DisplayPreviewState及共用JPEG校验，保留固定素材和项目引用的超媒体base；自动拉伸按实际无正文协议发送，未把超媒体读取说成固定operation。确认无源码／宿主／测试／scripts调用方且无原有修改后删除旧SettingsTrashDialog，真实设备删除与素材回收站保留。

定向证据：asset-editor-sdk.xml为5通过（含新增Gain=0／冲突草稿检查及原有未知接受结果不重放）；dataset-sdk-fixed.xml通过；asset-dataset-sdk-regression.xml为328通过。首次内容确认夹具classification=null不符实际契约，修为对象；集合详情夹具补齐真实摘要字段，版本列表去除members，并等待真实异步详情。生产schema没有放宽。

display-sdk-fixed.xml通过；首次完整独立客户端回归有3失败，原因是父组件mock未装配新预览客户端／JPEG媒体头以及导入通知场景没有有效workspace健康响应。修复HTTP夹具后independent-clients-regression-fixed.xml 56通过。原56项行为断言保留；无正文预览断言按真实协议更新。最终independent-clients-final.xml完整UI为328通过，UI类型检查通过，native-independent-clients.log宿主类型检查通过；本轮源码／文档diff检查通过。不将此前失败报告改写为成功。

G3 Python领域客户端补记：六组Operations共93个公开能力返回具体契约；TypeAdapter在HTTP响应边界按JSON模式解析，成功但类型不符时给出INVALID_RESPONSE、字段诊断和请求标识。CLI／MCP共用json_value展示，exclude_unset保留省略／null／0；76个直接转发标注同步。JPEG独占文件写入归client/exports.py；上传受理／分块回执也验证，不因未知结果重放。

证据：python-client-final.xml 31通过；python-client-callers-fixed.xml 42通过；python-client-protocol-final.xml真实隔离HTTP／CLI／stdio 6通过。契约拆分后的python-native-final.xml合并回归48通过，含真实stdio；各报告有重叠，不相加。类型清单python-client-type-inventory.json列93个公开能力，无缺失返回标注；清单不是逐接口行为验收。最初10项旧ok占位／非UUID上传任务响应不合契约，替换为真实领域夹具；另1项上传路径断言同步合法UUID。新测试发现默认值补入响应字段，修正展示序列化后8项新增边界检查通过；软件详情替身改放在HTTP边界，保留路径／节点UUID解码断言。超时不重放、非法回执不启动处理、原件不变、严格日期／数值／联合及无原输入泄漏均覆盖。

原生契约补记：删除contracts/workflows.py，分到canvas／packages／native，更新15处导入。删除三个取消的Workflow类型及两个空占位字段；业务modules/workflows与完整图快照仍待G6。register_native_schemas只补真实消息组件，不加假HTTP操作；冲突可诊断，离线app构建不创建业务数据库。宿主canvasContracts与NativePageReply不再手写DTO。

native-contracts-fixed.xml后端44通过，native-message-ui.xml UI328通过，native-message-canvas.xml宿主23通过，UI及native-message-typecheck-fixed.log宿主类型检查通过。native-generator-determinism.json证明OpenAPI与18个TS文件重复生成相同。最初1项缓存冲突测试未按FastAPI当前路由版本缓存机制建立有效缓存，现使用实际已生成缓存注入冲突；宿主unknown值类型错误通过真实Widget边界检查及声明的空参数默认修正，没有as any。已保留首次失败报告。

以上为此前分步状态；后续G3收尾证据见本节开头。G3阶段审计已通过，整体Goal继续G4，真实Siril验收仍未完成。

G3编辑SDK补记：data/api/mutations.ts封装17项实际生成写入：项目／设备／组合／预设创建更新、素材与集合PATCH、批量固定成员参数、项目固定引用增删、素材移除及管理归档。Workspace与EquipmentSetupManager已移除assetApi.send、动态path/schema表和ZodType<any>分派，仍保留原base_revision、固定base_version_id、成员去重及更新后摘要刷新。

core/api/input.ts的validatedInput在UI草稿→请求边界使用生成schema校验，校验后返回原输入而非补齐默认值后的输出。只有此验证边界作类型收窄；无效字段转唯一ApiClientError并保留字段路径。专项覆盖gain=0、offset=null、未提供字段不注入、非法值不发送及回执丢失不重放。不引入写入重试或兼容参数层。

证据：editor-sdk-ui-fixed.xml原阶段321通过；editor-sdk-verified.xml当前完整UI 324通过（包含专项），UI类型检查及native-editor-sdk-verified.log通过，diff空白检查通过。旧schema import全部清理，未将未使用导入失败计作类型通过。模拟HTTP写入仍运行真实SDK；样例在SDK验证下补齐实际DatasetOut.summary／input_ready／current_version_number，保留原延迟保存、版本选择、最新revision与删除确认断言。首轮editor-sdk-ui.xml的11项失败对应旧spy结构、较差的泛化错误文本与不完整集合写入响应；以生成模型修复样例和回执诊断后原行为断言通过，未放宽生产schema。

仍未完成G3：导入任务／回收站等独立组件、自研原生消息、Python领域客户端及完整运行核查。未部署新预览、未操作真实素材或共享服务，未运行本轮Siril科学处理。Goal继续active。

G3管理查询SDK补记：data/api/catalog.ts提供capabilities、projects、equipment、setups、datasets、assets、projectAssets、projectDatasets及presets的明确生成SDK调用，输入／响应直接复用生成operation类型。Workspace不再以path＋schema分派管理读取；删除apiPath、formListPath、loadWorkspacePage、loadAll和其上下文导出。项目新增集合和已固定集合明确分支，去除该分支的ZodType<any>断言。设备选择仍以200条name排序显式分批，预设列表同样读取生成SDK。

实际项目素材接口的role／frame_type为标量，与混排素材筛选的数组不同；首次接入误传数组被生成校验器在发送前拦截，已按真实operation schema修正。项目引用样例补齐当前版本号、added_at及摘要版本头；固定A／当前B与项目revision原断言保留。相机快照从现行Snapshot生成schema构造，不携带注册行状态和时间戳。网络失败使用统一network诊断，仍清空旧项目行，不显示成设备。没有新增业务兼容路径。

证据：catalog-sdk-regression-final.xml定向项目／照片回归通过；catalog-sdk-ui-final.xml完整UI 321通过；UI vue-tsc及native-catalog-sdk-fixed.log通过。新增catalog.test.ts验证设备status／sort／分页和准确项目范围，非法身份不发送。首轮catalog-sdk-ui.xml的4项失败对应以上样例及真实标量参数问题；后续预设样例缺少equipment_selection已补齐。排错时临时日志已删除；fake timers环境中的一次观察等待未执行到日志，不作为运行证据。

目前只完成读取；assetApi.send的编辑、删除等写入与Python领域客户端仍待G3收敛。未更新私有预览、共享服务或真实素材，未执行新浏览器／Siril处理，Goal保持active。

G3素材查询SDK补记：新增data/library/client.ts的createLibraryClient，search／filters／members复用生成Query、SDK及响应schema；parseLibraryQuery只转换筛选表单范围字符串，再交生成schema约束键及类型。Workspace的混排素材与集合成员读取已改为明确SDK调用，保留用户显式“全部”的200条分批读取；LibraryFilterPanel与datasets/members.ts不再拼查询URL。其他管理列表与编辑的旧通用路径仍待切换，不据此宣布G3完成。

Workspace列表每次读取持有自己的AbortController，切换读取或卸载时实际取消旧请求，保留已有内容／请求代次保护。旧管理列表暂经原路径，但也传入本次固定signal。定向协议验证重复数组、gain_min=0、搜索编码、无效固定版本不发请求以及卸载真实取消。请求取消仅表示HTTP读取取消，不冒充Siril进程停止。

测试fixture现在通过模拟HTTP回执执行真实SDK，而非绕过schema；新增library-api.ts诊断及library-members.ts显式当前成员组装。未改原始历史dataset-groups-real-api.json；历史快照flat参数与nullable设备资料只在测试构造中转换，未给生产代码增加兼容层。完整UUID及固定A／当前B仍保持不同，断言保留原成员顺序、分页与预览归属。

证据：library-sdk-protocol.xml 23通过；library-sdk-cancellation-fixed.xml 28通过；library-sdk-verified.xml完整UI 319通过。UI类型检查及native-library-sdk-fixed.log通过；diff检查通过。首次library-sdk-ui.xml 13项失败来自旧包装列表、无效标识和不完整成员fixture；修复后仅剩一条旧包装样例，已改为当前摘要。接入实际取消后，两项延迟测试在请求尚未开始前离开导致resolver未建立，现明确等待请求开始再验证迟到响应不覆盖当前页；卸载专项保留actual signal abort断言。没有放宽生成schema。新查询客户端尚未构建部署到预览或执行新浏览器，整体Goal保持active。

G3 data契约单一来源补记：api/contracts.ts的设备判别联合、组合成员、素材／版本、项目引用、导入来源、任务、校准、集合成员、回收站与FITS资料均改为生成schema；剩余通用分页组合从生成ProjectPage派生，不手写页头。LocalImportFile仅在生成LocalSelectionFile上增加实际界面root_id，设备草稿在equipment/drafts.ts从生成创建契约派生，允许尚未校验的编辑值；不把草稿当响应DTO。当前列表／编辑HTTP路径及SDK切换仍未完成。

后端ImportReport定义登记／复制／预览三个已知进度对象，继承稀疏序列化并允许类型化JsonValue附加事实。66项真实导入／批次／科学输入检查通过，附加agent_batch及缺席阶段的往返检查保留。19个实际页模型共用PageMetadata约束，负total／offset和非正limit由源契约拒绝；摘要泛型使用当前Python语法，导出OpenAPI内容保持完全一致。

精度修复：AssetContentObservation.observed_mtime_ns改为十进制字符串，来源stat纳秒整数仅在HTTP DTO边界转为文本，原件检查仍在Python整数域／哈希中。原约10^18的数字无法在JS保持精度，未通过放宽Zod安全整数约束掩盖。前端样例和精确往返断言同步，未保留数字兼容输入。

生成器约束修复：固定版IR丢失propertyNames枚举键约束，新增openapi-input.ts将有限键纯map规范化为等价可选属性对象＋禁止未知键。输入仍读取同一OpenAPI文件，原文及服务契约不改；CLI环境指定的本地输入路径继续支持。不修改生成文件、不手写语言或校准schema。生成schema已验证空映射、明确null校准和未知键拒绝；生成配置与辅助函数经过独立严格tsc检查，最终日志generator-config-typecheck-verified.log通过。重新生成18项TS文件SHA-256完全一致，证据generator-determinism.json。

本轮结果：data-generated-contracts-fixed.xml 314通过；data-single-contract-source.xml 316通过；import-report.xml 66通过；data-contract-parity.xml 36通过；page-contracts.xml 46通过。UI vue-tsc、native-data-contracts.log、contracts全范围Ruff及diff空白检查通过。报告有重叠，不相加。首次5项UI失败暴露纳秒精度与旧组合成员身份样例，按真实模型修复；曾将相机规格随kind改为滤镜的无效样例也已修正。data-report-enum-contracts.xml仅1项负分页断言失败，已从后端共有页元数据修复。生成配置首轮静态检查暴露unknown输入和IR false分支，已正确收窄；一次venv路径拼写错误未执行检查，后续实际运行通过。

尚未部署新私有预览或运行新浏览器／Siril科学处理。G3继续：列表／编辑SDK、Python领域客户端、原生消息与剩余开放JSON契约仍需完成；G4—G7未因此完成。

G3画布／媒体消费补记：data/api/canvas.ts的本机路径受理、任务查询、固定版本准备与资料检查已使用生成SDK；CanvasDataRequest／CanvasDataOut／CanvasInspectOut及ScienceReference直接来自生成契约。删除没有调用方的display／displayStatus方法。core/api/images.ts统一处理服务器提供的JPEG预览URL、no-store、取消和错误；原通用getBlob只委托这项真实共享能力，不再重复实现错误正文解析。

data/api/media.ts删除手写MediaState／MediaSelection schema，消费生成Fetch客户端及生成校验器。成员地址来自服务返回，不另建资源映射；发送前验证选择，但不把解析补出的默认值写回body，明确保留省略／null／0。MediaMember／MediaViewerRequest继续是前端查看器请求模型。data/api/contracts.ts另将能力、项目、AutoStretch和DisplayPreviewState四项schema改为生成来源，其余列表／编辑契约仍待清理。

后端契约差异：MediaState和CanvasDataOut序列化始终输出默认字段，原schema却把它们标为可省略。使用固定Pydantic的json_schema_serialization_defaults_required标明真实输出，输入稀疏规则不变；原官方JSON Schema模式章节及已安装pydantic/config.py文档字符串是依据。宿主MediaViewer将slices作为明确界面草稿字典，不给科学输入补值；查看器／画布样例补齐实际响应的phase、hdus、display_recipe，未放宽生产schema。

证据：canvas-sdk-final.xml 23通过；frontend-canvas-media-final.xml 313通过；native-canvas-media-fixed.xml 27通过；native-media-result.xml 3通过；serialized-media.xml 33通过；media-client-contract-fixed.xml 12通过；data-shared-contracts.xml 281通过；preview-abort.xml 9通过。测试存在重叠，不累加。UI类型检查、native-canvas-media-final.log和Ruff通过。

首次canvas-sdk.xml的两项失败是旧RequestInit结构断言及同步取消假设，改为保留no-store并等待实际读取启动，检查实际收到abort；另增已取消信号不发请求。首次native-canvas-media.xml的11项失败来自缺少真实媒体响应字段的样例，补齐后保留全部行为断言通过。media-client-contract.xml的1项失败是新样例省略必需字段，补成完整状态后通过。新源代码尚未部署到私有预览，未据此声明浏览器或科学处理验收。

G3软件／结果SDK补记：software/api/contracts.ts改为生成类型和schema的明确导出，client.ts七项软件操作消费生成SDK。Bundle预览使用生成请求／响应及统一错误，明确parseAs:blob并检查PNG；删除前端没有真实宿主调用的createSirilPreviewClient／SirilPreviewRequest，宿主本就使用Bundle预览。core/api桥接现在保留keepalive／credentials／redirect等实际Request属性。服务端旧Siril专用兼容路由仍待G6移除，不能宣称全仓库旧入口已删除。

Data结果／导出读取、提交、查询、取消与目录选择已接入生成SDK，exports.ts删除手写DTO，宿主DataExportDialog按生成ExportRequest校验冻结草稿及sessionStorage恢复内容。结果展示样例的run_output补全真实定位信息，不通过放宽schema接受无效引用；用户取消目录选择不提交导出，未知写入只查询原request_id，不自动重放。

本轮证据：software-sdk-preview.xml 56通过；frontend-software-export.xml 309通过；software-export-contracts.xml 8通过（含新增2项导出恢复及PNG类型／真实abort／keepalive）；native-export-preview-fixed.xml 13通过；upload-contract.xml 8通过，验证真实上传、固定设备快照和失败后身份恢复。UI vue-tsc、native-software-sdk-typecheck.log及native-export-sdk-typecheck-fixed.log通过。各报告存在重叠，不相加为独立场景数。

首次software-sdk.xml仅旧GET无init断言失败，保留具体路径与GET断言后通过。首次native-export-sdk-typecheck.log暴露遗漏schema导入及无效引用样例，修复后通过；首次native-export-preview.xml有1项结果展示失败，因样例仅有kind而无定位内容，按contracts/inputs.py补齐后保留原断言通过。旧报告保留。

上传计划差异：全仓库自研UI没有调用原createApiClient.upload，只有未接入的XHR实现及返回属性。依“不创建空服务”规则删除死助手，不新建无消费者core/api/upload.ts；未删除现有上传HTTP／Python能力。FastAPI上传handler通过request.stream处理文件，原OpenAPI未声明body，导致生成SDK认为不应有正文。现使用固定版本openapi_extra声明required application/octet-stream binary，SDK自动获得Blob请求和真实Content-Type，仍不缓冲整个文件。对应官方说明见已安装FastAPI routing／applications的openapi_extra文档字符串；不修改原官方文档包。

新客户端尚未构建部署或执行新浏览器验证，未运行真实Siril处理。Python领域客户端、data列表／编辑／媒体、原生消息及生成器剩余约束仍待G3，整体Goal继续active。

G3前端SDK消费补记：新增core/api/client.ts与errors.ts，按workspace注入fetch与baseUrl创建独立Hey API实例，不改生成全局客户端；网络、协议、业务错误及AbortError统一分类。工作台配置／目录选择／重启／结果查询、语言读取和节点目录已真正改用生成SDK；core/contracts.ts与nodes/client.ts删除手写DTO／Zod，保留明确的包公开名称。其余data／software／结果客户端仍待迁入，不宣称全部HTTP调用已生成化。

发现并修复生成器差异：Hey API 0.99.0默认z.object会忽略额外字段；固定版上游source map显示additionalProperties:false归一为IR never，现通过官方object resolver追加strict，所有生成物重建，未手改生成文件。默认workspace输入实际拒绝null／空白，原OpenAPI却允许null；contracts/workbench.py使用Pydantic SkipJsonSchema及字符串约束表达省略但不可清除，仍保留服务端校验。相关本地原文为Hey API Fetch／Zod v4及Pydantic JSON Schema。

证据：frontend-platform-fixed.xml 33通过；严格生成后frontend-strict-all.xml及节点接入后frontend-sdk-adoption.xml分别为301通过（同一套覆盖，不相加）；后续frontend-platform-final.xml 13通过，frontend-shared-errors.xml 38通过；workbench-schema.xml 31通过；native-sdk-bridge.xml 11通过，native-sdk-typecheck-final.log与UI vue-tsc均通过。宿主按真实可省略类型处理显示字段及数值边界，测试样例补全实际操作字段，未增加类型断言掩盖差异。

失败记录：首次前端检查有跨realm DOMException误分类和旧GET参数结构断言两项失败，已修复取消识别并保留路径／方法断言；Promise.withResolvers超出当前目标lib，改用现有Promise而不升级编译目标。native-sdk-typecheck.log因子命令误取全局pnpm 9失败，改用固定本地pnpm直接调用typecheck:app；第一次真实宿主类型检查暴露可省略字段与不完整样例，已修复。未安装全局工具。新前端尚未构建／部署到私有预览，不以单元或类型通过冒充浏览器／科学验收。

统一装配回归：http-regression.xml为83通过，覆盖当前data服务、批次及节点写入的真实隔离TestClient流程；日志保存在同目录http-regression.log。未使用旧预览结果证明这些新改动。

新增证据：node-ownership.xml 33通过；import-ownership-fixed.xml 23通过；preview-ownership-fixed.xml 60通过；media-ownership-fixed.xml 30通过；http-adapters-fixed.xml 49通过；public-boundaries.xml 17通过；media-contracts.xml 10通过。各报告范围有重叠，不累加为独立场景数。测试直接发送真实ASGI文件响应，覆盖发送完成、OSError断连及CancelledError取消，租约均释放一次。

失败与修复：首次批次检查的4项失败为测试旧导入及公开入口写法；显示预览收集失败为剩余Siril样本旧路径；媒体拆分时覆盖已有preview_response造成收集失败，已恢复其所有权检查后的字节响应，并与LeasedFileResponse并存。http-adapters.xml为不存在的测试文件导致未执行，不能计为通过；后续以实际入口回归。上述初次失败报告保留，不以新增空接口或旧路径兼容解决。

日志、科学文件、缩略图、瓦片、视频及Siril预览均声明真实媒体；204不含正文。新增全公开接口成功响应检查阻止空JSON或遗漏正文声明，归档／恢复返回具体计数模型。重新导出OpenAPI并生成六项SDK文件，vue-tsc通过。仍未重新部署G3到预览，未运行Siril真实科学处理；Python领域客户端与前端生成SDK消费仍待完成，整体Goal保持active。

软件HTTP补充：modules/software/routes.py已删除，真实handler迁入interfaces/http/software.py，应用装配和测试调用同步；新增递归software无HTTP框架／接入层依赖检查。software-http.xml为34通过。迁移后重新离线导出OpenAPI，SHA-256与迁移前完全一致；无需伪造接口变更或手改生成物。

G2收尾补记：closure-audit.json的检查均通过。index-baseline.xml 16通过、query-owners.xml 42通过、setup-unicode-fixed.xml 5通过；browser-library-indexed.xml两项通过。新workspace modernization-current实际包含四个计划索引；索引探测记录在index-probe.json。旧浏览器报告和失败尝试保留。当前只有合成素材与元数据场景，不是Siril真实科学处理或用户验收。


本页保留各日期、候选和范围的历史证据；段落中的“当前／尚未实现／未合并”只指当时，最新状态见 [当前上下文](current-context.md)。按具体条目查询，不作为每次任务的必读清单。


<a id="modernization-g2"></a>

## 2026-10-31 现代化Goal：G2 SQL查询推进

G1收尾审查的13项条件及对应测试、20表所有者、实际服务签名已记录于`.artifacts/reports/modernization/g1/closure-audit.json`，阶段交付完成。最后补齐activity.py：data.public只保留显式导出，数据库任务／预览观察归活动能力，导出与媒体各自通过busy_blockers()提供锁内快照。owned-activity.xml有9项通过，覆盖维护准入、完整结果准备／读取、导出及释放；data-exports-gate.xml有10项通过，新增公开入口无业务实现与真实活动服务无HTTP框架加载检查。未放宽现存检查。

G2已新增DatasetMemberQuery／DatasetMemberPage和LibraryMemberFilters；datasets/queries.py通过SQL完成固定版本归属校验、组合筛选、计数、稳定position排序及limit／offset，仅装配当前页成员。assets/filters.py统一已实现的分类、设备、Binning及数值范围条件，显式区分0与未设置，温度使用与既有半值离零取整对应的SQLite round。成员映射供分页与完整版本详情共用，固定关系缺失仍报错，不静默缩小输入。HTTP使用明确operationId=listDatasetMembers，Python客户端返回类型化DTO，SDK／Zod／Vue Query生成物同步。

证据位于`.artifacts/reports/modernization/g2/`：member-pages.xml初步17项通过，member-filters.xml最终21项通过（包含10项架构检查，不能相加为独立用例总数）。使用1001条合成成员元数据，验证空页／空集合、越界／跨集合拒绝、固定版本／顺序、组合筛选先于分页、0／负半温度／非法Binning，以及5条页仅加载5个DatasetMember、5个Asset和5个AssetVersion；SQL允许扫描计数所需数据。不是1万／10万全规模验证，也不是科学处理运行。

混排素材摘要／筛选聚合、Unicode casefold、前端接入与删除全成员汇总、完整规模验证仍待G2；G3—G7尚未完成。未操作共享runtime、真实素材或全局配置，未提交／推送／合并／发布，整体Goal继续active。

G2名称与筛选选项追加：names.py为素材／集合／设备／组合／预设／项目保存name.casefold()派生键，展示名保持原文。ORM赋值、批量插入默认及revision保护的PATCH同步维护，SQL搜索／名称排序和项目固定引用查询消费该键；未将键作为另一份可编辑资料。新初始baseline同步六列与索引，移除无消费者的原project.name索引，仍为20表，不改旧库。

筛选选项不再读取全库Asset／Dataset ORM或调用dataset_version_out。assets/visibility.py用SQL处理可见组、成员、显式素材移除及回收组冻结成员，assets/queries.py用DISTINCT及MIN/MAX投影选项／范围；只在结果边界整理已去重的设备标签，不装配素材对象。当前仅筛选目录采用此范围；旧混排列表仍待替换。归档但仍被可见固定组引用的成员保留在目录中，显式移除后隐藏，避免将归档状态误当固定成员删除。

证据：name-search.xml初次26通过／2失败，均为新增测试遗漏DatasetCreate必需asset_version_ids或EquipmentPatch的kind；按现有契约修正测试后name-search-fixed.xml的六类真实HTTP创建／改名／搜索／ORM改名全部通过，不放宽产品契约。name-write-regression.xml16通过，覆盖事务、revision、成员／预设固定语义及baseline与ORM一致。sql-filter-options.xml有3项通过／69项未选中，不能记为架构检查；filter-projections.xml最终24通过（含完整10项架构检查），覆盖1001成员、零ORM投影、负半温度、冻结范围及归档／显式移除区别。定向Ruff与差异检查通过。OpenAPI重新导出前后SHA-256相同（name-filter-openapi.json），本项不改变HTTP字段，未无故重复SDK生成或UI类型检查。

这些结果不代表混排摘要、前端分页或全规模查询已完成；G2继续推进，Goal保持active。

G2混排摘要追加：原518行library.py删除，SQL逻辑归library/queries.py、projection.py、ordering.py、summary.py，HTTP归interfaces/http/data/library.py。列表返回contracts/assets.py中的扁平asset／dataset判别联合，包含固定版本引用、成员／匹配数、输入准备状态、类型化资料摘要、缩略图引用和导入问题；不返回成员数组或原始科学JSON。空集合仍显示，过滤只改变命中数量与可见条目，不改写固定成员。原Python排序测试改为真实SQLite执行，保留ISO／Gain／Offset、数值Binning、未知／混合分区、双向排序及稳定身份断言。

调用方验证：library-contract.xml初次90通过／2失败／3设置错误，两个失败为旧嵌套响应访问，三个设置错误为G1后漏改的imports.process_task mock；均改用新摘要／独立详情或真实data.public入口，library-callers-fixed.xml定向40通过。library-import-contract.xml为80通过／1旧响应访问失败，已修正并由library-final-read.xml中的对应回收场景验证。library-final-read.xml27通过，library-union.xml22通过；后续实际SQL重组下library-final-shape.xml最终33通过，library-page-gate.xml另验证重复offset及全量total共11通过（这些报告包含重叠用例，不相加）。member-proxy.xml2通过，使用真实本机aiohttp代理验证新成员分页GET、重复frame_type参数和服务端令牌；OpenAPI快照一致。已生成6份SDK／TS／Zod／Vue Query文件，UI类型检查通过。UI仅接入新schema及行结构，显示／编辑／预览／入图／回收和成员分页完整接入仍待G2，未运行浏览器验收。

规模证据：新增固定入口pnpm benchmark:library -- --output <新.artifacts目录>，脚本拒绝覆盖已有目录或在worktree.artifacts外创建数据。实际1千／1万／10万合成元数据，包含单件、小集合和占半数素材的大集合，记录四种查询与EXPLAIN。当前报告`.artifacts/reports/modernization/g2/library-benchmark-current/report.json`：50项响应约60KB、2条SQL、0 ORM对象，5万成员集合摘要1240字节；开发环境SQLite3.45.3下10万名称排序2.264秒、曝光排序4.011秒、Gain筛选6.652秒、大集合查询4.137秒。没有约定或宣称毫秒级SLA，秒级复杂查询仍明确保留。报告仅元数据，不是科学处理或原生UI性能验收。

首轮10万查询约6.8秒；根据计划将计数与全摘要分离、对头字段提前分页、用MIN/MAX加非空计数判定一致、区分单件值与集合聚合，并缩窄缩略图／筛选引用。共享成员范围重复版本映射按[SQLite物化规则](https://www.sqlite.org/lang_with.html#mathint)做了实际测量后固定一次；[优化约束](https://www.sqlite.org/optoverview.html#flattening)用于解释计划，不将提示或有索引直接当成功证据。试验覆盖索引没有获益，未加入产品模型或baseline；仅存在于明确标为probe的合成数据库，当前报告来自另建的干净基线库。中间报告保留以追溯，current是本轮最终测量。类型注解／import修正与定向Ruff通过，差异检查通过，未提交、推送、合并或发布，Goal继续active。

G2前端接入追加：逐字段分类摘要保留共同frame_class和混合frame_type，模板不再通过成员回调计算资料。共享SQL列／排序／聚合／DTO映射归assets的summary_columns、ordering、summaries，供library、成员分页及当前／固定集合引用复用。DatasetOut增加摘要、输入准备状态及当前版本号；项目固定引用带固定版本摘要、成员数，不嵌入members；版本历史页仅返回DatasetVersionSummary，完整详情接口继续显式提供。固定项目引用测试中集合由1001成员A切到单成员B，引用仍为A；列表无DatasetMember／Asset／AssetVersion ORM装配，响应小于10KB。

Workspace已直接读取生成摘要；移除datasetValue／datasetRawValue／datasetMembers和默认版本详情预取。组成员搜索、排序、分页均走服务端。显式批量编辑按200项页收集去重revision，保留固定版本与逐素材冲突检查，提交后重读摘要；连续编辑使用已确认revision，导航等待保存后的读取。项目选用组不再重复保存dataset响应，避免名称与revision回退。FixedDatasetMembers按展开后的10项页读取，媒体翻图按一个成员读取；页面变化／关闭传递AbortSignal，BlobURL按代次释放。默认列表不以详情请求补回成员。

验证：member-search-sort.xml35通过，shared-dataset-summary.xml30通过；member-ui-contract-final.xml36通过，shared-version-number.xml2通过，覆盖新版本号字段、固定引用和快照一致性。fixed-reference-summary.xml初次86通过／1接口快照旧数据失败，重新生成后对应快照在上述最终报告通过。UI初次受限环境临时模块缓存ENOENT，未执行用例；主机权限下按隔离目录执行后，原响应夹具逐项换成当前schema，不放宽生产校验。ui-summary-groups-fixed.xml31通过；最终ui-summary-workspace-final.xml在自研数据工作区／摘要／客户端范围236通过、0失败、0未处理错误，含固定A而当前B、延迟响应不串图、组编辑、外层筛选状态、0值与取消读取。类型检查通过，相关Python定向Ruff与差异检查通过。UI回归中的旧“无自动刷新”实现断言改为明确验证自动摘要刷新后仍使用已确认revision，未削弱冲突／草稿断言。

预览隔离：只读确认旧Feature PID65640／101328仍存活，未启停它们。固定准备入口新增--runtime-dir，仅修改本次子进程环境并拒绝worktree.artifacts外路径；private-runtime.xml26通过。新的workspace／runtime均为modernization-preview目录，目标32588／32590预先确认空闲。第一次准备回执81cf35f3f8554fdf943e5e8495b02246在原生完整构建发现Workspace未使用Asset类型导入，尚未启动runtime；删除该导入后通过相同入口继续。第二次调用以当前回执和实际进程为准，目前不将准备中记为ready或页面展示成功。

本段不替代原生浏览器、实际科学处理或用户验收；G2尚待新预览及收尾审查，G3—G7仍未完成。旧规模报告对应当时摘要schema，当前逐字段DTO若对外引用大小须重新测量；不把旧字节数冒充当前结构的最终性能结果。

G2私有预览追加：固定准备回执7bbe26ba96814e668d5fae7b9cc1f6d1完成77.798秒完整构建、35.857秒私有runtime准备和1.195秒新workspace初始化，但数据服务启动5.186秒后失败；实际日志为CLI在lifespan之前读取app.state.database。将mark_interrupted_tasks移到lifespan创建database之后，保留原有真实中断观察，不在应用工厂创建资源；serving-recovery.xml4通过。

不重复已完成构建，按相同入口仅--start继续。回执a0c0384819db47fc9e2c86f0cd8ec04b实际completed／ready=true；新网页32588、数据服务32590，私有runtime与新workspace均在modernization-preview路径。浏览器实际打开http://127.0.0.1:32588/#/workflows，确认ComfyUI原生未命名画布、空素材库、设备管理以及返回素材库均渲染，捕获的console error为空。浏览器检查仅空库与导航，不代表合成数据交互、Siril处理或用户验收。准确路径、dirty=true及源码HEAD记录于`.artifacts/reports/modernization/g2/preview.json`，本轮未提交／推送／合并／发布；G2仍待合成数据浏览器与收尾审查，整体Goal保持active。

G2实际数据浏览器追加：只在modernization-preview经HTTP导入12＋52＋1张16×16合成FITS，任务全部completed；未直接写SQLite或读取真实素材。browser-byte-protection.json验证65张源文件SHA-256未变，65份托管科学字节与源集合一致。浏览器会话不可用后使用计划固定的Playwright Test1.63.0及匹配浏览器，浏览器缓存安装于本Worktree.artifacts，未修改系统浏览器。

新增tests/browser/modernization.config.mjs及modernization-library.spec.ts，独立context／单worker／0重试，真实本机双服务、无业务API mock；非本机网络被测试上下文阻止。当前browser-library-observed.xml两个场景通过：摘要无成员数组、52成员的50／2分页、PATCH曝光0及页面显示、元数据编辑前后原生图节点一致、返回素材库、单素材已有版本的content-observation=unchanged。截图browser-members.png／browser-standalone.png位于g2目录。首次失败是原生简约侧栏返回时没有h1、同值0不发送PATCH，以及隐藏的紧凑资料不能点击；按真实UI修正定位与显式测试前置状态，不强制点击隐藏元素、不增加产品兼容分支。各失败trace分别保留在browser-results、browser-results-current、browser-results-final，当前成功与旧失败分开记录。

浏览器核对另发现LibraryPage仍用current_version_id判断单素材是否有版本；摘要已是version_id，内容观察按钮会被错误禁用。已修正并新增ui-content-summary.xml回归（21通过），只重建本Goal私有实例，回执f0545b5c8d904f3abe86c19d96e6b3a7 ready／completed，旧实例未操作。browser-contract-gates.xml当前36通过。当前DTO重新测量1千／1万／10万，结果library-current-dto-report.json：50条约61.7KB，5万成员摘要1271字节，均2 SQL、0 ORM。初期后端检查与测量并行，报告明确标出负载条件，耗时不能冒充空闲SLA。这里只验证元数据、页面和字节保护，未运行Siril处理。

G2还需逐项检查模型／计划的反向引用与设备筛选索引，未以已执行查询替代索引覆盖审查；G3—G7仍未完成，整体Goal保持active。未提交、推送、合并、发布。

<a id="modernization-g1"></a>

## 2026-10-31 现代化Goal：G1设备能力推进

G0阶段交付完成后进入G1，整体Goal继续active，G1尚未完成。

- 设备模型移入`modules/data/equipment/models.py`，所有实际模型消费者同步更新，不在旧models路径重导出。Alembic通过`data/persistence.py:schema_metadata()`显式装配；旧迁移链尚待G1其余模型完成后替换，不能将本项记为新基线完成。
- 设备服务归`equipment/service.py`，输入为Session与Pydantic契约，返回具体DTO；HTTP归`interfaces/http/data/equipment.py`，只调用data公开能力。EquipmentQuery是查询字段来源，SQL计数／排序／分页保持在数据库执行。新服务不依赖FastAPI／Starlette、不隐式提交；revision冲突、null清除与省略语义保留。
- EquipmentOut改为按kind判别的六类输出，specs使用对应模型；创建／补丁／输出共用规格定义，删除重复SpecsPatch。相机只保留`pixel_size_um`，网页登记、内联编辑与组合内设备同步更新，删除x/y转换及回退，不转换旧库内容。
- OpenAPI与正式TS／Fetch／Zod／Vue Query生成物同步更新，生成于`frontend/packages/astrophotoflow-ui/src/generated/api/`；前端完整类型检查通过。页面使用生成接口的替换仍属于G3／G5，不能将首次生成误写为全量接入。
- 原设备／项目／组合／快照／导入回归127项通过（`g1/equipment.xml`，当时像元收敛前）；像元字段收敛后，快照／导入／服务37项通过（`pixel.xml`），最终共享规格定义下服务／递归边界9项通过（`equipment-service.xml`）。严格UUID输出映射和公开入口导入在首次失败后修正，不放宽契约／边界。
- 前端设备、组合和Workspace回归73项通过（`equipment-ui.xml`），类型检查通过。首次检查发现万能上下文残留已删除转换器，已删除该引用后复核；不恢复转换器作为兼容层。
- 新增模块Ruff检查通过。证据在`.artifacts/reports/modernization/g1/`。未运行真实Siril科学处理、未启停共享服务、未提交／推送／合并／发布。

G1追加：EquipmentSetup与CapturePreset模型归入equipment所有者；组合JSON改为EquipmentSetupMember关系表，成员有稳定UUID与顺序，数据库约束注册设备／组合内设备互斥。组合查询的成员筛选、关联名称排序、计数与分页改为SQL，只有当前页组合装配成员；Unicode casefold搜索键仍待G2统一落实。编辑／重排保留成员ID，跨组合ID拒绝并回滚，前端schema与组合内编辑同步保留ID。删除注册设备时移除当前成员并清除当前预设引用，保留既有文件／运行资料，不再创建新的组合内兼容快照。

旧9段迁移链已删除，仅保留0001_baseline，17表的新库可直接初始化，旧revision明确要求重建且不更改旧数据。`scripts/generate_database_baseline.py`仅对内存空库生成初始DDL，入口`pnpm generate:database-baseline`；当前G1模型仍在演进，baseline会随目标模型同步更新，不对已有数据转换。移除两项旧迁移／回填测试，将备份失败与旧profile升级断言替换为拒绝旧库、原数据不变和新关系表断言。原有asset／version及dataset／version互相外键仍产生metadata排序警告，未隐去，待后续模型收敛核查。

验证：组合／服务／边界35项通过（members.xml），稳定ID及数据库约束4项通过（member-identity.xml）；新基线／资料／打包回归93项通过、1项因测试加载旧schema时生成文件更新而快照差异，生成稳定后该快照项单独复核通过（baseline.xml、baseline-recheck.xml）。直接使用组合模型的导入／CFA／边界13项通过（baseline-imports.xml）；组合与设备UI40项通过（members-ui.xml），前端类型检查、定向Ruff与Git差异检查通过。HTTP查询参数显式允许字符串到受约束整数转换，请求体仍严格校验。所有证据保留在g1目录，未把重复执行次数加成不同业务场景。

G1预设追加：CapturePresetSelection通过复合外键同时约束预设归属与成员归属；省略记录继承、null记录停用、member UUID精确选择，提供PATCH选择对象时整组替换，以空对象恢复继承。选择只允许同组合匹配种类的成员，支持注册／组合内设备和多滤镜；成员移除或改变种类清除相关选择并更新预设revision，已受理输入快照保持。

预设服务归`equipment/presets.py`、HTTP归`interfaces/http/data/presets.py`，固定资料归`equipment/snapshots.py`，共享成员角色归`equipment/members.py`；删除旧data/setups.py与data/presets.py，不保留转发导出。CaptureParametersPatch不含设备ID，AssetParametersPatch扩展它；预设通过equipment_selection引用成员，不在parameters保存第二份设备引用。设备快照原先跨文件的私有函数改为具名snapshot_equipment共享。导入对显式null和0分别保留，文件观察仍优先于预设默认；组合内设备通过固定资料解释，不伪造注册ID。注册telescope与组合内光学设备使用同一科学角色校验。

OpenAPI及SDK同步生成；预设网页直接复用生成的Zod输出schema，删除该手写响应schema。相机／光学／滤镜选择都有继承和不使用选项，滤镜可选注册或组合内成员；恢复继承不会清除其他数值。新初始基线现为18表，尚不是全部G1目标模型完成。

验证证据：preset-selection.xml最终批次74项通过、1项素材编辑因快照函数与局部字典同名失败；修正命名后，设备快照／成员选择35项通过（selection-final.xml），包含该失败项。初次设备删除出现成员引用未先清理的外键失败，已显式先flush引用更新再删除注册行，同一事务不隐式提交；后续删除、固定快照、重试均通过。预设数据库约束／跨组合拒绝／删除整个组合／角色与null优先级及边界15项通过（selection-constraints.xml）；基线、OpenAPI与完整导入流水线47项通过（preset-imports.xml，既有表间外键排序警告保留）。前端74项通过（selections-ui.xml），类型检查及新增代码Ruff通过；一次旧选项文案断言按新增“不使用”能力修订后复核。全部为隔离自动验证，未运行真实Siril处理或操作共享服务。

G1固定资料类型追加：共用Frame／拍摄参数定义归`contracts/metadata.py`，创建、补丁和预设共用数值字段／有限值规则；AssetParameters仅覆盖完整输入的默认模式，删除重复AssetClassificationPatch及旧assets路径的类型导出，所有源码／测试消费者同步更新。这样`contracts/snapshots.py`可以依赖metadata与设备／组合契约，不与资产输出形成循环。

设备快照按kind划分六种具体规格；EquipmentSnapshots约束相机／滤镜／光学角色，注册与组合内成员分别有FrozenMember契约。`capture_defaults_snapshot(Session, UUID|None, AssetParametersPatch) -> ImportDefaultsSnapshot`返回类型化对象，接受服务只在JSON持久化边界调用model_dump(mode=json, exclude_unset=True)，保留省略／null／0和已有固定快照。`snapshot_equipment()`返回设备快照类型，素材／集合元数据纠正调用方同步序列化。当前版本capture_snapshot、原始科学metadata的公开响应及图片列归属仍待继续收敛，不将本项说成全部图片契约完成。

验证：固定资料／设备删除与重试／预设／边界53项通过（typed-defaults.xml）；共用字段收敛后，完整导入流水线、成员选择、OpenAPI与边界61项通过（metadata-contracts.xml）。前端类型检查和新增模块Ruff通过，科学原件／共享实例未触碰。

项目实际缺陷追加：原模块两个get_project定义使公开服务被路由函数覆盖。直接服务已改为(Session, UUID)返回ProjectOut，路由read_project委托服务并采用固定operationId；直接服务与HTTP一致性及递归禁止同名覆盖9项通过（project-service.xml）。项目文件与全部引用服务的拆分尚未完成，不把这个修复记为完整模块重构。OpenAPI／SDK同步生成，前端类型检查通过。

G1图片列与版本资料追加：Asset／AssetVersion／FitsHduMetadata归`data/assets/models.py`，删除Asset.parameters与Asset.classification两个JSON列，不创建同名ORM兼容属性。帧分类／用途、设备身份、模式、ISO、Gain、Offset、曝光、积分、温度、Binning与CFA为明确列；`assets/metadata.py`只负责API分组与列之间的具名映射。登记、纠正、集合批改、预览、科学输入、回收清理和筛选全部更新到列；当前设备UUID属于素材记录的设备身份资料，赋新值时验证注册设备，已有已受理资料不因设备行删除而丢失，解释仍依赖固定快照。新初始baseline同步更新，未转换旧库。

AssetOut的参数／分类／设备资料／来源与AssetVersionOut的capture_snapshot改为具体契约。VersionCaptureSnapshot分开保存接受时的parameters、classification、equipment_snapshot与import_provenance；观测原文保留JsonObject。内容接纳新版本重新构造本次快照，保留旧版本及固定项目引用。SnapshotModel按Pydantic已设置字段序列化，递归保留省略／null／0，不重写科学metadata内普通时间字符串。只对新闭合契约调整合成fixture，不加入旧结构兼容分支。

验证：改列首批素材／设备／校准108项通过（asset-columns.xml），导入／入图／边界76项通过（asset-inputs.xml）；结构化版本资料后导入／科学输入／入图77项通过（version-snapshots.xml），相关素材／校准／边界116项通过（structured-assets.xml）。新增物理列／无兼容属性／null与0／视频约束和版本重观察4项通过（observed-versions.xml），明确证明新文件曝光从31更新到33而旧快照及固定引用不变。

最终强类型资产响应检查先39项通过、1项筛选选项把UUID再次当字符串解析失败、1项OpenAPI导出瞬时OSError后快照尚未更新失败（asset-output.xml）。已同步旧列表对UUID的消费并正确跳过无注册身份的组合内设备，重新导出成功后相关97项通过（typed-asset-output.xml）。OpenAPI／SDK已更新，前端类型及定向Ruff检查通过。原有asset／version、dataset／version外键排序警告仍保留，尚待最终模型审查；所有验证均在隔离合成数据中完成，未将其记为真实Siril验收。

G1集合与校准追加：Dataset／DatasetVersion／DatasetMember归`data/datasets/models.py`，默认校准与成员覆盖分别归DatasetCalibration／MemberCalibration关系表。删除JSON校准列及旧路径模型导出，不建立同名兼容属性；owner+用途唯一，数据库检查“明确停用且无目标”或“唯一固定素材／集合版本目标”，目标和所有者均有外键与反向索引。公开映射仍区分省略、null停用与目标引用。

校准引用预检改为按关系目标SQL查询，外部仍存引用时在文件清理前拒绝，范围内永久清理由外键释放残余关系；保留确认指纹、部分失败与恢复限制，不宣称文件系统和数据库统一事务。集合服务与校准服务归`datasets/service.py`、`datasets/calibration.py`，HTTP适配归`interfaces/http/data/datasets.py`、`calibration.py`，服务接收Session并返回具体契约；旧data/datasets.py和data/calibration.py已删除。new baseline现20表。

网页和导入现在共用publish_dataset_members构造固定版本，校准复制／成员顺序／去重与版本号规则只有一个发布入口；初次导入仍保持初始revision=1，冲突和任务报告按实际结果表达。公开publish_dataset_version与update_dataset等服务采用Session优先签名，HTTP仅经data公开入口调用；common旧映射／私有辅助依赖仍待剩余服务拆分一起收敛，未把当前代码写成最终全部依赖完成。

验证：关系化首批引用保护／清理／科学输入／服务86项通过（calibration-relations.xml），导入／批次／边界65项通过（dataset-publication.xml）。实际共享发布逻辑落实后84项通过（shared-publication.xml）；数据库停用／唯一目标约束、无JSON或兼容属性及既有保护24项通过（calibration-constraints.xml）。源勘查发现导入发布实际函数名为_publish_dataset，修改脚本最初未匹配且没有写入，已修正定位并停止旧代码对应检查，最终结果对应已落实共享入口。OpenAPI／SDK更新，前端类型、定向Ruff和Git差异检查通过；既有表间外键排序警告保留。

G1映射／资产／项目服务追加：资产、版本、FITS HDU和头映射归`assets/mapping.py`，固定引用范围校验归`assets/references.py`，集合映射归`datasets/mapping.py`，均返回具体契约。common中的对应私有函数删除，所有调用方改为具名入口；旧列表确需字典时显式model_dump，不在旧路径转发。集合服务去除对common通用页面／时间／UUID／配置更新包装的依赖，设备新赋值校验归`equipment/references.py`。

资产CRUD／固定版本／HDU服务归`assets/service.py`，HTTP归`interfaces/http/data/assets.py`；项目3个模型归`projects/models.py`，背景资料、固定引用、映射分别归service／references／mapping，HTTP归`interfaces/http/data/projects.py`。乐观revision写入步骤在项目所有者内共享，导入批次直接消费项目固定引用服务及DTO；不关联图文件，不恢复任何工作流生命周期。

Preview模型归`media/models.py`，读取由`media/previews.py`返回PreviewContent，接口响应在`interfaces/http/responses.py`创建；预览源使用PreviewReference，固定版本／项目范围在业务服务验证。删除common._read_preview和旧项目模块，预览路由声明实际二进制媒体类型，公开能力不返回Starlette对象。静态小预览仍为字节读取，原有大图租约／消费者机制未替换。

验证：owner-services.xml有95项通过，project-intake.xml有57项通过，覆盖CRUD、校准、项目固定引用、批次关联、预览与科学输入。递归边界扩展到assets／datasets／equipment／projects／media，并在独立进程实际导入服务，确认没有加载FastAPI或Starlette。针对反复出现的asset／version、dataset／version依赖循环，按固定版SQLAlchemy官方use_alter方式声明有名当前版本外键；重新生成20表baseline后不再出现该排序警告。owner-boundaries.xml共14项通过，包含SQLite实际外键仍存在、写入不存在版本失败及ORM与基线一致性；不是删除约束或忽略警告。

下一步继续G1：导入任务和回收记录等剩余模型归属、剩余任务／清理的服务职责与公共基础包装收敛；随后进入G2数据库摘要与分页。13条前端WorkspaceContext循环仍按G5处理。


G1导入／回收与入图追加：AssetTask／AssetTaskItem归imports/models.py，LibraryEntryRemoval归trash/models.py；20表全部由所有者装配，删除旧data/models.py。imports/submission.py、uploads.py、tasks.py、sources.py只接收数据库、配置及契约；HTTP负责请求流、断连、准入与既有后台执行安排。新增ImportTaskStateOut／UploadReceipt及明确任务状态，未将取消受理误写为运行线程已停止。旧data/imports.py删除，测试的后台暂停mock更新至真实公开入口，不保留旧路由函数兼容导出。

回收站按scope／service／cleanup／files拆分，HTTP归interfaces/http/data/trash.py；确认步骤在写事务中核对指纹、保存有限pending_paths，返回具体删除时间标识。每条文件删除返回FileDeletionResult；部分成功、恢复阻止、活动预览保护及KeyboardInterrupt恢复语义保留。预览所有权查询移入media/ownership.py，服务不导入HTTP预览路由。逐项数据库清理收尾及导入runner／pipeline深拆仍待G6，不把本次拆分记为这些目标已经完成。

固定数据入图及检查移入assets/canvas.py；HTTP归interfaces/http/data/canvas.py，仅调用data.public；软件样本调用方同步更新，删除旧data/canvas.py。prepare_canvas_data／inspect_canvas_data继续固定版本与成员范围，不编辑原生画布。

验证证据：import-boundaries.xml初次93通过／3失败为旧mock路径，import-recheck.xml定向12通过，intake-regression.xml40通过；trash-services.xml92通过，preview-ownership.xml77通过。一次确认函数提取遗漏局部变量返回导致durable-cleanup.xml的3项失败，已撤回并改为显式返回删除时间，confirmed-cleanup.xml最终10通过。owner-gates-verified.xml11通过；canvas-owner-fixed.xml的32通过／1边界失败后，改为显式data.public导入，canvas-final.xml最终32通过（含完整9项架构检查及真实无HTTP框架导入）。入图拆分过程首次引用尚不存在的dependencies模块造成收集失败，改为当前真实core.http；其最终迁移仍属G3。早期final-owner-gates.xml使用不存在的测试符号未执行测试，不能计为通过。基线与ORM一致性在canvas-owner-fixed.xml中的对应测试通过。

本轮OpenAPI与6份SDK／TS／Zod／Vue Query生成物已同步，生成后UI类型检查通过；新增服务／HTTP文件定向Ruff通过。上述用例可能重叠，不相加作为独立场景总数。未运行真实Siril科学处理、未启动预览、未改变共享runtime；G1尚待收尾审查，Goal继续active。


<a id="modernization-g0"></a>

## 2026-10-31 现代化Goal：G0阶段交付

用户已授权完整实施，不再受之前仅文档范围限制。平台基点`bbb6f4a9f872fc1b79defa6dddf849247b5099d6`，分支`codex/equipment-image-mcp`；保留实施前未提交文档。Bundle原dev干净且HEAD为`f4f11b34587f989fb026607b483b740ee3b74cac`；隔离副本位于本Worktree`.artifacts/bundles/AstroPhotoFlow-Siril`，分支`codex/modernization`，尚未改Bundle源码。

- 固定依赖已解析并安装到本Feature开发环境：FastMCP4.1.4、Cyclopts5.3.2、watchfiles1.3.0、Ruff0.17.3、pytest-asyncio1.4.1、Hey API0.99.0、Vue Query5.105.0。uv／pnpm锁更新，原有依赖版本未升级；这不代表业务接入完成。
- 数据库和HTTPX客户端由`interfaces/http/lifespan.py`创建／关闭，启动失败也释放已取得资源；App与OpenAPI检查不创建这些资源。安装热加载和空闲观察使用共享客户端并单独设置60秒／3秒超时。原测试中多余的手动关闭随所有权更新移除，真实资源测试显式使用lifespan。
- 生命周期、递归Python边界及导入预设最初13项通过；增加启动中途失败清理后，生命周期／边界／本地化23项通过（`lifespan-boundaries.xml`）。软件／节点／画布／控制先58项通过、1项因测试未初始化数据库失败；补齐测试库初始化后该项通过。数据回归509项通过、1项因并行pytest清理共享basetemp导致数据库路径丢失而setup error（`data-regression.xml`）；改用独立目录后，设备完整文件及关闭后数据库检查27项通过，包含该失败场景（`data-recheck.xml`）。不隐去原批次错误，也不把复核次数相加为不同场景数。
- `python scripts/verify_modernization.py`通过：类型化schema、多层mount、中英文BM25、已知工具直达、真实stdio、官方生成CLI及Cyclopts扁平组合；证据`.artifacts/reports/modernization/g0/mcp.json`及`cli-result.txt`。搜索隐藏工具时框架会提示客户端未缓存schema，直达调用及明确结果断言仍通过。
- `frontend/packages/astrophotoflow-ui/openapi-ts.config.ts`固定生成Fetch／TS／Zod4／Vue Query。G0样例发现0.99.0将binary生成`z.string()`，通过生成器resolver生成`z.instanceof(Blob)`，不手改生成物；启用偏移时区。生成SDK运行时与TypeScript检查通过，覆盖省略／null／0、判别联合、日期、数组query、二进制、错误和响应校验。证据`.artifacts/reports/modernization/g0/sdk.json`及`tsconfig.json`。
- Python边界改为递归；前端循环升级error。基线169模块／580依赖发现13条WorkspaceContext相关循环，尚未修复，按G5清理；当前完整边界门未通过，不将旧warn结果作为通过。正式业务SDK／MCP／CLI尚未替换，G0仍在推进。
- 新增代码Ruff定向检查通过；OpenAPI重新导出无差异。沙箱中Windows事件循环卡在socketpair，获准在允许本机socket的环境执行后通过；未改产品事件循环来规避环境限制。

G0追加：应用工厂已仅负责装配，安装确认移至`interfaces/application/package_actions.py`，维护／原生页面／统一错误分别归`interfaces/http/maintenance.py`、`native_pages.py`、`errors.py`；MaintenanceAction归contracts，错误响应的跨文件调用使用具名公开函数。OpenAPI重新导出无差异。定向回归130项通过，1项因旧测试patch指向不再参与安装的get_usage失败，删除该无效patch后复核通过（`factory.xml`、`package-recheck.xml`）。18份生成文件重复生成散列一致（`generation-repeatability.json`），新增模块Ruff通过。G0阶段交付完成，进入G1；完整边界门的13条前端循环仍按G5处理，未宣称整体通过。

尚未运行应用预览或真实Siril科学处理，未操作共享服务／默认workspace／真实素材，未提交、推送、合并或发布。原官方文档正文保持原样，版本阅读快照与依赖安装证据分别记录。

<a id="native-workflow-refactoring-plan"></a>

## 2026-10-31 文件结构与原生工作流归属：计划修订

分支`codex/equipment-image-mcp`，源码基点`bbb6f4a9f872fc1b79defa6dddf849247b5099d6`；保留本轮开始前未提交的现代化计划、入口／验证记录及官方资料包。独立Bundle基点`f4f11b34587f989fb026607b483b740ee3b74cac`，只读核对。

- 用户确认工作流全部使用ComfyUI原生体系，取消自研workflows模块、项目图关联／生命周期、完整运行库、完整图副本和先保存自研工程的准入；具体调用、固定科学输入、结果检查、原件保护、画布校验和真实取消保留。有效规则更新到需求和架构；上下文、导航及相关README／AGENTS明确当前旧实现仍待拆除，不宣称已经改代码。
- 更新[现代化计划](modernization-plan.md)，新增[文件与函数计划](file-refactoring-plan.md)：四条规则、路径与函数去向、目标签名、直接依赖／导入方、阶段及验证映射；728个文件、3117个命名定义（平台391、Bundle337个文件），保留／生成文件也列出。静态导入不等于实际调用，附录不作为第二套运行契约。
- 本轮检查范围为文档来源、覆盖、取消项一致性、本地链接、源文件／锁文件与官方原文不变、Git文档差异。报告为`.artifacts/reports/file-refactoring-plan/validation.json`；提取证据为同目录`source-inventory.json`及`frontend.json`。未运行pytest／Vitest／Playwright、依赖解析、类型编译、构建或真实Siril处理。
- 检查通过：728份来源文件大小／SHA-256、3117个命名定义（含2521个Python AST定义）、546处本地链接／锚点、254份官方原文散列；目标中残留workflows路径为0，唯一多来源函数合并resolve_result_member已明确说明，无未解释的目标符号冲突。`git diff --check`通过；应用测试及实施状态均为false。
- G0—G7未开始；未改应用源码、依赖锁、数据库、运行实例或独立Bundle，未启停服务、创建Goal、提交、推送或合并。历史计划／应用验证记录保持，不能从历史完整工作流目标恢复已取消需求。

<a id="modernization-plan-documentation"></a>

## 2026-10-31 现代化重构计划：文档交付

分支 `codex/equipment-image-mcp`，基点 `bbb6f4a9f872fc1b79defa6dddf849247b5099d6`，开始时工作区干净。

- 新增[重构计划](modernization-plan.md)，记录技术选型与利弊、目标数据模型、SQL分页、契约生成、FastMCP／CLI、前端查询状态、Siril Bundle、G0—G7阶段及验收／Goal交接目标；当前计划链接到该文档，不复制完整方案。
- 本轮只交付文档，G0—G7未开始；未修改业务源码、依赖、数据库、运行环境或独立Bundle，未运行应用测试、类型检查、构建或真实科学处理，未启停实例，也未创建Goal或提交、推送、合并。
- 静态检查：10处本地链接／锚点全部有效，计划章节和G0—G7齐全，记录29个官方文档URL；`git diff --check`通过。报告为 `.artifacts/reports/modernization-plan/links.json`。官方文档链接来自本次在线调研，本轮未重新请求外链；静态结果不表示候选技术已联调通过。

<a id="modernization-official-docs"></a>

## 2026-10-31 精确版本与本地官方文档包

在上述未提交文档基础上继续，分支和源码基点不变。本轮只完善文档，没有开始重构G0—G7。

- 固定7项新增依赖的精确版本，记录已有锁定版本与实际Python／SQLite差异；补充FastMCP与HTTPX2的依赖边界，Hey API插件标识不等于额外安装包。未安装候选依赖或运行解析器，未把声明约束核对写为组合兼容通过。
- 下载[本地官方资料](../references/modernization/README.md)：28组、254份原文／片段／许可证／发布元数据，5,760,389字节，下载失败0项。来源以发布tag解析出的固定提交为主，滚动源码及网站快照明确标注；保留来源URL、时间、大小、SHA-256与许可位置，原文不改写。
- 补齐80处必要引用，包括TanStack的公共正文、FastAPI示例和Sphinx片段；watchfiles生成API页配有固定版本源码与docstring。29份中文总／分库索引按G0—G7导读，普通延伸阅读保留回源入口，不宣称完整离线站点构建。
- 来源清单为[manifest](../references/modernization/manifest.json)，下载过程和文档校验报告位于 `.artifacts/reports/modernization-docs/`。本轮文档检查只验证内容完整性、版本依据、必要引用、本地链接和Git增量；未执行应用测试、类型检查、构建或科学处理，未改依赖锁、数据库、运行实例、全局配置或独立Bundle，也未创建Goal、提交、推送或合并。
- 校验通过：254份文件的大小／SHA-256、其中164份原始选择文件的上游Git blob散列、80处必要引用、573处本地链接／锚点、7项官方正式发布依据和8项声明约束核对；31份自编Markdown无行尾空白。报告 `.artifacts/reports/modernization-docs/validation.json` 明确将应用兼容验证记为false。原文通过目录内Git属性保持字节，不为消除上游排版差异而改写。

<a id="database-mcp-domains-feature"></a>

<a id="data-node-input-export-feature"></a>

## 2026-10-30 Data节点输入与完整结果导出：Feature静态验证

分支 `codex/database-mcp-optimization`，基点 `711bd850b122ca64e1f147c645ba6fc0015c42ab`，候选为保留已有MCP／导入改动的未提交工作区；未合并、推送或发布。

- 原生节点：Data保留ID／reference／science输出，新增互斥science与images输入及输出节点声明，复用原生执行上下文、队列、输出Store和图序列化。恢复旧图时通过原生API补缺失端口，不改节点ID、已有引用或连线。File保持原输入／输出契约。
- 后端：新增独立Data执行记录和运行结果解析，IMAGE批次固定为完整FITS（float16提升float32，float32／64保留），不伪造Bundle调用或拍摄资料，不自动登记素材。新增共享HTTP／MCP `exports.*`，选定成员可保存素材库或导出本机，任务回执防重复、保留部分结果、明确取消／中断；既有上游不重跑。新增tifffile 2026.10.15、PyPNG 0.20220715.0，锁文件同步，依赖安装在Feature私有环境。
- 格式与数据：实现FITS／XISF／TIFF／PNG／JPEG及各自精度组合；默认原格式／原精度复制完整容器。数值转换不自动裁切、归一化或显影；显示转换固定完整查看器参数，按完整分辨率处理。高精度TIFF／PNG读取同步更新。多HDU／视频转换需选定平面／帧；复杂TIFF、多图XISF和RAW数值开发明确要求上游处理或原样复制。入库保留来源及转换依据，本机同名文件不覆盖。
- 已完成：Python源码与新增测试文件编译；UI包及原生前端类型检查；完整网页构建；OpenAPI快照生成；独立双服务启动。首轮构建暴露新增测试mock缺少方法及引用未安装测试辅助包，定向修正后构建通过，未为此新增测试依赖。
- 页面展示：浏览器已重新加载最终构建，从节点库放置空Data展示节点，确认science／images真实输入、science输出及原生输出节点菜单。未执行图、未操作真实素材、未实际保存／导出文件。撤销展示节点的Ctrl+Z清理动作被自动审批拒绝，因此保留当前展示画布。截图 `.artifacts/reports/data-node/data-node-preview.png`。
- 已编写未执行：`tests/modules/data/test_image_exports.py`（格式精度回读、灰度／RGB、数值决策与NaN/Inf、多HDU、IMAGE固定与科学下游解析、显式入库／本机导出、防重、部分失败）；`tests/interfaces/comfyui/test_data_node.py`（原生端口、互斥和File契约）；`DataRunWidget.test.ts`、`DataExportDialog.test.ts`（真实结果／来源匹配、失败运行隔离、格式精度联动、取消选择器及未知受理恢复），同步原控件测试。测试套件、实际Data→Siril、原生队列／缓存／图保存重载、取消恢复及各格式跨软件科学验证留Manager集成阶段，未宣称通过。
- 预览与版本：网页 `http://127.0.0.1:32688`，服务 `http://127.0.0.1:32690`。构建manifest为上述基点SHA，回执 `dirty=true`；最终启动 `completed=true`、`ready=true`。回执副本 `.artifacts/reports/database-mcp/data-node-prepare.json`，最新回执 `.artifacts/dev-prepare.json`，阶段日志由回执引用。正常dev、默认workspace、全局MCP及独立Siril仓库未修改。

## 2026-10-30 数据库与MCP分层：Feature实现及静态验证

分支 `codex/database-mcp-optimization`，基点 `711bd850b122ca64e1f147c645ba6fc0015c42ab`；候选仍为未提交工作区，不是已合入dev或用户验收通过的版本。

- 实现：仅注册 `data_management`、`node_canvas_management`，通过固定注册表执行具名操作，按需发现／读取契约；既有69项能力迁移，旧扁平MCP名不再注册。节点摘要分页、指定定义批量读取、MCP原生图片与错误回执保留。更新仓库Skill与操作参考；已有客户端需要重连，不修改全局注册。
- 导入：递归只读检查来源及分组依据，扫描清单留在workspace；文件头优先、名称为待确认线索。用户确认后批量受理，保留原件与固定来源范围、请求ID防重复、各阶段独立事实及项目关联结果。聚合等待有20秒上限，重试项目关联不重新导入。沿用既有任务、项目、设备、校准及版本模型，无数据库迁移或新增依赖。
- 网页：素材库后增加项目入口，复用项目资料和固定素材／组引用界面；不包含项目与原生图文件保存联动。独立网页 `http://127.0.0.1:32688`，平台服务 `http://127.0.0.1:32690`。
- 已完成：Python编译、MCP注册／契约静态装载、OpenAPI快照生成、UI包与原生前端类型检查及网页构建。构建版本为上述基点SHA加未提交修改，构建manifest非unknown。浏览器确认工作台和项目空态实际渲染，未创建项目或导入真实素材。
- 静态体积对比：等价69项扁平工具的输入schema合计87,762字节，两个领域入口合计513字节（JSON序列化，仅输入schema，不代表全部上下文或总延迟）。实际批量导入调用次数、返回体积及耗时尚未实测，不能据此宣称端到端加速通过。
- 已编写未执行：`tests/integration/test_mcp_domains.py`、`tests/modules/data/test_import_batches.py`；同步迁移既有stdio／原生图片协议测试与侧栏注册测试。覆盖发现直达、范围／来源变化、请求ID冲突、部分失败、项目revision冲突与关联重试、取消／恢复、分页及等待边界。测试套件与综合验收留Manager集成阶段，不把编译或页面展示当作功能验证。
- 证据：本Feature的 `.artifacts/reports/database-mcp/build-prepare.json` 保存带build阶段的回执，`.artifacts/dev-prepare.json` 为最终启动回执；对应阶段日志由回执引用。项目截图在 `.artifacts/reports/database-mcp/projects-preview.png`。正常dev、默认workspace、全局MCP和真实素材未操作；未提交、推送、合并或发布。

## 2026-10-31 自动结果计算与单帧序列：Feature 实现与定向演示

- 平台与Bundle仍在 `codex/node-ui-bundle`，基点分别为 `711bd850b122ca64e1f147c645ba6fc0015c42ab`、`8310d4da2e68b2c3434fee22ca3ee100e8eb6dae`，含未提交修改。Bundle逐项声明160个策略，131个处理／分析操作自动，29个导出／脚本／查询管理操作手动；旧Bundle缺省手动。
- 实现：原生指定目标通道支持经过整条依赖验证的自动处理节点，不改变原有输出节点身份；前端500毫秒合并语义变化，按受影响分支选择末端目标，同一次prompt共享上游。草稿无需命名或手动保存，软件调用前写入不可覆盖的计算快照。调用摘要携带可选内容签名；移动、标题与显示选项不参与科学计算签名。运行期间只保留最新修改，切图停止旧图后续提交，失败不循环重跑。已有十种快速样本预览默认收起。
- 合成数据演示：通过本Feature公开导入／画布接口创建独立草稿，两张256×192浮点FITS经 `seqsubsky` 自动返回两个成员（prompt `5c806174-7878-4389-8e6b-65cee52849ed`）；连续三次参数修改合并到最终samples=24。链式 `seqsubsky → seqmtf` 在prompt `3084e6d7-e192-4a70-872c-1a6817cbd5b4` 中两个节点均完成，各保留两个成员。未点击顶部运行或保存工程。
- 演示暴露并修复：主进程退出后已知子进程短暂存活时，有界观察5秒后再判定；无法核实时仍unknown。Bundle节点使用原生输入指纹使新prompt重新计算，避免跨运行复用科学输出引用，保持同次prompt内共享上游。历史unknown／失败记录保留，没有据此自动重跑旧调用。
- 用户后续把草稿输入换为单张NGC2018时，Siril未自动发现单帧输入及输出序列。适配器现在明确记录version-6单帧序列，处理后核对唯一实际文件再登记缺失输出描述；不重复帧或替换原命令。prompt `41ca76a4-b76b-4494-b836-eb1214f4f2a1` 的 `seqsubsky`、`seqmtf` 均完成，输出各为3294×1990 RGB完整FITS；下游引用同次运行节点2的输出，原件blake3不变。参考固定版官方 `src/io/seqfile.c`，不是160操作全面科学验收。
- 统一结果组件保留上次结果并标注待更新，过滤其他工作流与迟到签名。旧原生画廊和新结果预览造成双图，已复用原生 `hideOutputImages` 隐藏重复画廊，保留原生历史图像与文件结果。用户明确要求取消RBF samples=256并加载新网页后，已定向取消prompt `073ae2d2-4334-4489-be07-cbdc7c5d38b6`，确认 `cancelled`／`active=false`。取消前通过节点原生开关暂停其自动更新，避免重载后重新启动同一计算；草稿、连线及参数保留。
- 已编写依赖签名、分支合并、500毫秒防抖、草稿、切图、失败不循环、结果归属、快照不可覆盖、显式非输出目标、手动上游阻断、单帧输入／输出描述及旧Bundle默认策略回归用例。按Feature约定未执行pytest／Vitest套件或综合验收；分支及分析展示的完整应用验收仍待集成。证据在 `.artifacts/reports/automatic-result-demo/summary.json`、`observations.json` 及对应workspace运行快照／日志。
- 去重候选已通过根构建（含UI包与原生应用类型检查）、9个受影响实现文件ESLint及Python编译，OpenAPI已生成；没有运行测试套件。取消后的准备回执 `7400ad76f7ae478b86b7550f099a259b` 为completed／ready，已将该网页安装到独立32689实例；构建网页index SHA256为 `995fb426ca9fb4ce6f56cb762ec56db82f3669af0b60eaebab0604c35b84d048`。固定引擎归档SHA256为 `8c72ee3298339ba10a281a4de372e5f78725a66c5cdfcc1c59ec94ded19b3e73`。本地待审提交后的最终预览回执与准确提交SHA以交接Brief为准。

## 2026-10-30 预览 RGB 显示及分辨率：Feature 预览

- 需求：所有图像预览提供512／1024／2048 px及原尺寸选择，继续单击打开；黑白图保留亮度拉伸，RGB背景平衡只影响彩色显示。原件、科学执行参数及结果文件不变。
- 实现：统一查看器、素材节点、Siril快速预览和完成结果的预览接入显示选项；选项参与缓存身份。线性RGB查看兼容旧的无白平衡百分位配方，重新计算显示拉伸；完成结果默认保留输出亮度，显式RGB平衡不重新拉伸直接显示的结果，黑白图忽略RGB切换。高清瓦片仍读取原尺寸，px选择控制概览；Siril FITS显示样本按所选尺寸准备，其他格式非1024档由原程序处理后缩小显示，原尺寸可能更慢。
- 构建／类型编译通过，受影响实现文件ESLint通过，Python编译及OpenAPI生成完成。回执 `57bbe9f75f55493e913f5cbbe26cddd7` 为completed／ready；平台基点仍为 `711bd850b122ca64e1f147c645ba6fc0015c42ab`，含未提交修改，网页32689／服务32691。没有提交、推送或发布。
- 网页观察：新构建已打开，素材节点及快速预览显示分辨率／RGB选择；此前NGC2018素材节点的大幅偏绿消失。素材列表旧缩略图仍为先前生成的版本，未批量重写。新增旧RGB配方、分辨率、保留比例、黑白直接结果及控件请求回归用例；未运行测试套件或综合验收。各分辨率、运行结果、黑白与视频暂停帧的完整联调仍待集成阶段验证。

## 2026-10-30 Bundle开发源码绑定：Feature实现与真实联调

- 两仓基点仍为平台 `711bd850b122ca64e1f147c645ba6fc0015c42ab`、Bundle `8310d4da2e68b2c3434fee22ca3ee100e8eb6dae`，分支均为 `codex/node-ui-bundle`，均含未提交修改。开发绑定只写本Feature workspace的 `run/bundle-sources.json`，不改默认workspace、全局MCP、正常dev或其他Feature。
- 实现：bootstrap支持 `--bundle-source PACKAGE=PATH`、`--clear-bundle-source PACKAGE`。复用原生Bundle watcher，按Bundle `development.json` 生成／校验作者资料，元数据、翻译、节点注册、适配器计划、结果解析、预览和执行统一解析来源。辅助Python内容纳入适配器及预览缓存指纹；软件面板、回执、节点能力与调用记录分别保留开发来源和已安装版本。生成失败阻止新调用，修正自动恢复；原生加载回执核对源码路径、指纹和存活进程，切换来源时旧回执失效。
- 实际网页：独立32689工作台显示160节点及9个一级组／32个二级组。临时将Auto Stretch改名并移至“分析与测量／图像统计”，同时将参数默认值改为0.42，目录及新增节点自动更新，无需前端构建或服务重启。English／简体中文往返后分类展开状态和自定义标题保留。默认标题改用原生空标题回退，最终构建再次观察到“自动拉伸→动态更新演示→自动拉伸”，手动标题未覆盖。
- 真实软件服务演示：使用预解析的64×64合成FITS，经共享软件服务入口完成Siril 1.4.4预览和实际调用，输出为有限数值的64×64图像，原输入SHA256不变。仅修改 `recipes.py`、不改适配器入口，内容指纹变化且同一进程的适配器缓存得到新模块，随后再次真实预览／执行成功。没有使用真实素材，也未将该演示记为完整原生图端到端验收或160节点科学验收。
- 失败与恢复：无效分类声明使生成明确failed，160项能力均不可用，新预览在启动程序前被拒绝；软件面板显示日志诊断，画布及自定义标题保留。恢复作者资料后自动ready。解除绑定实际恢复既有 `v0.2.0-dev.2`／`5d16fb6fc10b4ee57de428d6eba522c918b1b441` 的160节点；安装副本的声明、翻译、适配器、锁及主程序哈希核对未变。随后重新绑定开发源码，临时名称／参数／辅助文件修改均已恢复。
- 自动检查：UI包与原生应用类型检查、网页构建通过，完整构建入口 `1cd63d8eb5764de0a26d863de51a3217`；追加预览指纹回归后原生应用类型检查通过。受影响9份TypeScript／Vue实现文件ESLint零错误，受影响Python实现／测试语法编译通过，OpenAPI已重新生成。首次回执路径解析错误和新增测试清理回调类型错误已修复；没有跳过类型检查。
- 最终回执 `6c7d26164ee64c438e6db644e7155546`：磁盘 `completed=true`／`ready=true`／`dirty=true`，复用已构建网页及私有依赖／CPU runtime，启动调用23.632秒。网页32689／服务32691，开发源HEAD为上述Bundle基点、dirty=true，内容指纹 `231129715f5ff17694d827f532cea70799e9cf7edb8df6c1c95412d49c17a76e`。网页清单HEAD为上述平台基点，包含本次未提交前端修改，不是干净提交的发行物。
- 证据：`.artifacts/reports/bundle-development-demo/summary.json` 及同目录的 `presentation.json`、`helper-cache.json`、`execution.json`、`invalid.json`、`detached.json`、`restored.json`，准备日志位于 `.artifacts/logs/dev-prepare/`。已编写生成失败恢复、旧安装保护、辅助模块缓存、原生就绪回执、软件面板刷新、默认／自定义标题及预览仅指纹更新的回归用例；按Feature约定未执行测试套件或综合验收。
- 交接边界：开发绑定保持启用，预览保留演示节点；已安装副本保持原版本。两个仓库的配套修改须一同集成；未提交、创建／移动tag、合并、推送或发布。

## 2026-10-30 Siril节点名称与两级分类：Feature实现与构建

- 平台基点 `711bd850b122ca64e1f147c645ba6fc0015c42ab`、Bundle基点 `8310d4da2e68b2c3434fee22ca3ee100e8eb6dae`，两仓分支均为 `codex/node-ui-bundle`；本节记录未提交候选，不代表已发布版本。
- 实现：160节点中英文“功能名＋命令名”，Siril根目录下9个一级功能组及32个二级子组；显式映射由两份生成入口共用。节点及显示契约支持分类路径，旧声明缺省为空且保留旧内容标记；原生目录路径稳定，标签随语言切换，中英文名称及命令名可搜索，Bundle刷新／卸载清理旧分类翻译。
- 静态比对：160份节点相对Bundle基点仅名称和分类变化，UUID、端口、参数及执行绑定未变；操作声明、适配器、程序与manifest未变。完整双语名称／分类清单及比对结果为 `.artifacts/reports/siril-node-presentation.json`。Python受影响实现及生成辅助完成语法编译，OpenAPI已通过固定入口重新生成。
- 构建与服务：固定bootstrap `--build --start` 回执 `8f5a07b9482f4766a6d716641ee26758`，磁盘最终 `completed=true`／`ready=true`／`dirty=true`；UI包与原生应用类型检查、网页构建通过，构建阶段101.033秒、完整调用118.660秒，复用本空间依赖与私有CPU runtime。预览网页32689、服务32691；产物清单基于平台上述HEAD及本次未提交修改，不是该干净提交的发行物。浏览器刷新后确认工作台实际渲染。
- 已编写未执行：Bundle全量分类／双语名称／生成拒绝错误映射、旧声明与内容标记兼容、真实原生schema分类及搜索别名、语言切换后的目录身份与双语搜索、卸载清理分类翻译、保留旧图及自定义标题。按Feature约定未运行测试套件或综合验收。
- 受影响的6份TypeScript实现文件ESLint检查0错误；两份原生前端测试文件因现有ESLint配置未匹配而被忽略，不记为Lint通过，未修改配置扩大范围。
- 实际安装边界：本workspace仍为既有 `v0.2.0-dev.2`／`5d16fb6fc10b4ee57de428d6eba522c918b1b441`，本次源码候选未安装，未宣称新分类实际原生加载或功能验收通过。未提交、创建tag、推送、合并或发布；候选安装继续走固定版本和原生确认流程。

## 2026-10-30 Siril完整Bundle候选：Feature静态验证

候选分支`codex/siril-full-bundle`，平台基线`2a6053eb3e8351156d7fb2b4b1ed208e6e628bc0`；独立私有Bundle基线`12fd2d1d55daeadf7acb3972385d5c2bfcb52d4d`，候选`0.2.0-dev.1`／Siril 1.4.4／SDK v2。以下是未提交源码的Feature记录，不表示已发布、原生加载或用户验收。

按用户确认，199条参考索引逐条保留覆盖依据；181条可脚本能力落实为160个真实具名操作、会话／输入输出／运行设置及共享别名。固定Windows程序实际提供198条，非脚本17条，另有仅Unix的`ls`；非脚本项不生成执行节点。`visu`的显示阈值复用通用查看器，`inspector`提供原尺寸平移缩放的人工检查，九宫格及其余GUI交互仍待后续方案。平台只增加通用SDK、文件引用、多输出／分析及同源查看／查询能力，Siril程序和命令适配保留在私有Bundle。

- 静态构建：39份受影响Python源码／测试完成语法编译；私有Bundle清单、160份操作／节点契约验证通过，160个调用计划完成静态构造，43个明确执行端点。RAW构造样本仅验证路径与计划，未伪称真实RAW解码。OpenAPI已重新生成。记录在`.artifacts/siril-audit/final-static.json`和`plan-compilation-v3.json`。
- 类型／网页：UI包类型检查通过；原生应用类型检查排除已知基线`WorkbenchSettingsPanel.test.ts`的TS2769后通过，未重复执行已知失败的根完整构建。Vite网页构建通过并保留已有资源／动态导入警告，产物位于`.artifacts/build/frontend`；未提交候选以基线加`dirty-siril-full-bundle`标记，不能冒充已提交SHA。日志为`.artifacts/siril-audit/ui-typecheck.log`、`native-typecheck.log`、`frontend-build.log`。
- 定向原生资料探查：保留固定程序的`help`／格式输出和固定1.4.4源代码依据；三张合成64×64单色FITS的序列布局、`getref`、`seqstat`和直接编号文件探查完成。首次进程启动在OpenBLAS分配阶段失败；显式BLAS／OMP单线程后探查成功。日志为`sequence-layout/layout.log`、`layout-threads1.log`和`direct-stage.log`。这些探查不等于160个节点执行验证。
- 回归用例已编写但按Feature约定未运行测试套件或综合验收。待Git Manager独立审查／验证：具名／可选／增长端口原生加载、原件与容器帧数、颜色布局及精度、校准／配准／叠加、序列旁文件、多输出、分析实际解析、依赖缺失、进程树取消／unknown查询和查看器视觉交互。

本轮未修改正常dev、默认workspace、全局MCP或真实素材。现有32688／32690独立实例仍为准备阶段版本；完整候选安装须先取得本地提交／新开发tag授权，生成固定目录快照并走现有安装确认。包内默认发布目录仍指向先前Bundle，不用旧SHA承载当前源码。用户确认可以集成前不合并、推送或发布。

<a id="docs-minimization"></a>

## 2026-10-29 文档最小化

基线：dev `51046067`，开始时工作区干净。用户确认旧22 Batch仅作参考，后续按当前目标重新排序。精简根规则、需求、架构、现状与模块入口，旧计划和数据／接口草案退出默认阅读路径；需求继续保留原件、固定范围、人工接管、保存后运行及结果登记等未完成目标。

接口复用已有OpenAPI导出脚本，增加根`pnpm docs:api`入口；既有CI中的schema／快照／代理一致性测试保持。导出已执行成功，生成快照与基线一致。本轮只做文档与静态检查，没有运行应用测试、类型检查、构建、浏览器验收或启停实例，不表示业务闭环通过。

静态链接与锚点检查覆盖92份当前文档、局部规则和相关历史参考，0个失效本地链接／锚点；`git diff --check`通过。根AGENTS从113行减至35行，当前上下文从468行减至44行；默认起读从16份约758KB改为2份约6.7KB，其余按任务读取，不代表全部需求只剩这些内容。

范围、缩减统计及链接结果见`.artifacts/docs-minimization-20261029/summary.json`与`links.json`。旧15份计划／草案保留正文及修正后的引用；必要用户规则已归并现行需求，原文仍可按Git基线追溯。本次未提交或推送。

## 2026-10-29 三个独立 chat 的 dev 集成

本次按用户要求合并 ComfyUI 展示精简、素材库 UI 优化与 Workspace 内容跳转三个 chat 的当前实现。原分支均起于 `366a3112`；ComfyUI 未提交实现先保存为 `e7e6e4f6`，素材库保存为 `cbfb8914`。Workspace 分支无新增提交或未提交源码，原有内容已在 dev；本轮不将其写成新增实现。Siril 集成 `e56a4ee5` 保留。

合并冲突仅为需求、当前上下文、验证矩阵及桥接 README 顶部的独立新增段落，保留双方有效说明和证据；没有源码冲突或不同实现方向需要选择。设置的固定 Nodes 2.0 策略与素材组件兼容旧画布的显示能力同时保留。以下各候选段落中的“未提交／未合并”描述为此前记录，提交和集成状态以上述来源及实际 dev 历史为准。

本轮遵循“只有明确要求才测试／构建”的约定，未运行应用测试、类型检查、构建或网页更新；历史通过结果不代表合并后的验收。仅核对 Git 祖先关系、未合并索引、空白冲突，以及两个来源的 41 个源码／测试文件与合并结果逐文件相同。证据为主工作区 `.artifacts/verification/three-branch-integration-20261029/integration-audit.json`。

分支清理按用户授权执行：主工作区使用 dev，三个独立 worktree 保留数据、依赖、运行资源与此前证据并脱离已删除分支；origin 的旧 M2 分支从远端删除。upstream 指向第三方模板仓库，按用户确认仅移除本机跟踪引用及 remote 配置，不删除第三方服务器分支。推送和清理结果以实际 Git 回执为准。

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

候选为`codex/m2-ui-acceptance`的`be0422e5`加本轮未提交改动；保留B31／B32／B41等原有未提交内容。本轮不提交、推送或合并。实现逐项及证据见报告（历史本机报告`.artifacts/implementation/m2-ui-optimization-20261028/report.md`，当前工作区未保留），原始问题清单保留为实施前证据。

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

基线为 `demo`／`741f6f1d` 加当前未提交实现，用户指定以当前代码为准，只改文档。补齐[源码文件／公开函数／消费者映射](../architecture/module-map.md)，纠正M1／M2、B31／B32／B41与⑤剩余能力的状态，以及详细设计中的已有文件／测试标记。保留原有未提交源码和历史证据，不提交、推送或合并。

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

候选为dev `75aab88714095d77f2d576c14712a31c2b987bf6`上的本轮文档增量，非业务实现。[总计划](../archive/2026-10-29-planning/development/implementation-plan.md)保留M1～M6、22 Batch／建议分支、79项验收、G01～G10及V01～V18；六份任务卡把需求／数据／接口映射到准确文件、关键函数、实施顺序、测试输入／命令／预期及人工操作。

- 使用Context Researcher、Software Architect、Senior Developer、QA Engineer、Git／DevOps Reviewer并行审查，由Document Editor装配，Independent Verifier另行逐卡复验。审查报告、基线、静态检查和独立结论进入`.artifacts/implementation-plan-review`，最终状态以该候选报告为准。
- 用户确认五项取舍，见[ADR-0061](../../frontend/docs/adr/WORKBENCH-PLAN-0061-executable-batches-and-shared-client.md)。原④契约只补真实调用缺口及冲突，未另建协议体系；计划区分Batch技术集成与用户Milestone批准，不把尚未锁定的首包／模型或未过原型写成Ready。
- 本轮仅执行文档及静态源码检查，没有创建业务源文件／测试实现／实际分支、执行迁移或修改schema0009；未运行构建、原型、业务回归、软件／MCP客户端操作、工作台启停或环境维护，未提交推送。当前OpenAPI、锁文件、MCP／Skill及原有脏改动保持。
- 第④阶段下列散列与结论对应其当时历史候选；本轮补文后的新契约与任务卡由本轮报告独立记录，不能把旧散列冒充当前文档。所有业务验收及M1～M6用户批准仍待实际实施。
- 全仓前端ADR脚本实际返回1：历史ADR两处、既有工作流前端README两处短号引用不合现行命名规则，均与本轮开始时内容／散列相同，按范围保留；未当作检查通过。ADR目录命名与元数据单独执行通过；具体失败和范围证据见`.artifacts/implementation-plan-review/adr-check.json`，不以此扩改历史文档。

## 2026-10-27 第⑤阶段近期实施计划编制

候选为dev当前文档工作区。[近期计划](../archive/2026-10-29-planning/development/implementation-plan.md)对接现行接口与文件级详细设计，按M1～M6列出22个建议分支、分项验收及V01～V18责任；M2完成②自身近期范围，跨模块项分别由B53／B54／B55／B57联调，最终在M6验收。

- 本轮只检查计划结构、分支依赖、验收编号、接口断言覆盖、本地链接／锚点和Git增量；报告进入`.artifacts/implementation-plan`。检查结果以报告为准，不把计划中的测试名称视为已经执行。
- 所有建议分支、新增原型和功能验收均未实施；首软件准确版本／操作、实际素材和本地检索模型仍按计划门槛确认。保留第④阶段独立证据及下列历史状态，不将当时“近期计划尚未开展”解释为当前状态。
- 未创建实际分支，未修改代码、OpenAPI、依赖、环境、MCP／Skill或业务数据，未运行构建／业务回归、启停工作台、提交或推送。完整产品S6范围继续保留。

## 2026-10-27 第④阶段接口与文件级详细设计

候选为dev当前文档工作区，非新增功能实现。主文[接口与文件级详细设计](../archive/2026-10-29-planning/api/platform-contracts.md)通过Context Researcher、Software Architect、Senior Developer、QA Engineer、Document Editor及Independent Verifier复核；报告与本轮增量在`.artifacts/fourth-stage-design`。独立候选主文SHA-256为`1c59ace39a76603e91e261f655444e2dc6b6a3f474c7f4dc7082354c29815738`，R1–R8/I1–I7已逐项关闭。

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

[五模块接口契约](../archive/2026-10-29-planning/api/platform-contracts.md)覆盖①本机控制、②科学数据／所选结果、③软件包、④可编辑节点及⑤原生画布／运行／MCP交接；局部改图、保存成功后运行、网页按钮绑定目标已按用户选择同步需求。新增路径和工具名均为未来设计，尚未实现或运行验收。

本轮逐项核对领域路由、OpenAPI和同源代理的78个操作，以及58个MCP工具的迁移覆盖；检查任务增量链接、锚点、ADR格式、Git范围及保留文件散列。报告见接口设计检查（历史本机报告`.artifacts/interface-design/report.md`，当前工作区未保留），详细清单见 `.artifacts/interface-design/checks.json` 和 `inventory.json`。未运行构建、业务回归、原型或服务，未修改OpenAPI、当前MCP或Skill。历史需求包在任务开始前已删除，本轮不恢复，也不声称通过不存在的冻结清单校验。

## 当前行为与验证入口

| 需求范围 | 已有行为及边界 | 验证入口 |
|---|---|---|
| FR-01 项目 | 资料、回收站、资产与集合固定引用；项目托管工作流未实现 | `tests/modules/data/test_service.py`；UI Workspace／Settings |
| FR-02 工作流目标 | ⑤复用唯一原生当前图、自动保存、本地草稿和会话撤销，项目关联／另存和在线桥接待实现；无永久逐编辑历史 | 按⑤概要（原模块文档`src/astrophotoflow/modules/workflows/README.md`，G6已拆除）、AT-06～11验证保存重开、另存、活动目标及断连，不以原生测试代替新增业务 |
| FR-09 运行目标 | ⑤记录当次图／输入／参数及原生任务关联，两类输入保证、真实调用／停止核对和所选结果保存待实现；复用ComfyUI队列 | 按⑤阶段（原模块文档`src/astrophotoflow/modules/workflows/README.md`，G6已拆除）、AT-14～18／28／29补真实软件及运行证据 |
| FR-03/13 软件包 | ③软件专用副本及配套节点、安装版本位置和可用状态仍待实现；Agent只连接平台MCP | 按[③概要](../../src/astrophotoflow/modules/software/README.md)、AT-02／03／25／33验证安装、许可引导、节点发现及确认更新 |
| FR-04 导入 | 登记与托管分离、并发、Header 分类、预设快照、编辑与排序 | `tests/modules/data/test_import_pipeline.py`、`test_ingestion.py`、`test_library_sort.py`、`tests/integration/test_import_presets.py`；UI 导入／任务测试 |
| FR-04/11 删除 | 确认范围、部分清理、固定身份、共享路径与外部原件保护 | `tests/modules/data/test_service.py`、`test_calibration.py`；UI LibraryTrashDialog |
| FR-05 预览 | 100 px 缩略图、1080 px 大图、单图自动拉伸与 RGB 白平衡；完整比较未实现 | `tests/modules/data/test_auto_stretch.py`、`test_fits_preview.py`、`test_display_previews.py`、`test_video_preview.py`；UI PhotoPreviewDialog |
| 设备与预设 | 接受时冻结快照、删除后恢复／重试、历史名称和草稿保护 | `tests/modules/data/test_equipment_snapshots.py`、`test_setups.py`；UI SettingsOrganization／Workspace |
| 校准引用 | 默认、继承／null／覆盖、跨组隔离、历史清理保护；不执行校准 | `tests/modules/data/test_calibration.py`、`test_domain_foundation.py`；UI CalibrationLibrary |
| FR-07 数据 MCP | 58 工具与 CLI 共用服务；图编辑和软件运行工具未实现 | `tests/integration/test_client_operations.py`、`test_cli_mcp_protocol.py` |
| FR-07 统一检索目标 | ⑤派生目录、Skill直达、按需混合Top10及明确关键词降级待实现，当前58数据工具保持 | 按⑤阶段（原模块文档`src/astrophotoflow/modules/workflows/README.md`，G6已拆除）、AT-33／34验证精简MCP整体迁移、Skill及真实客户端，不遗漏已有数据业务 |
| FR-08 并发 | 数据revision已有；⑤活动目标核对、简单当前控制、手改接管／明确交回及在线结果返回尚未实现 | 按AT-07～10／24验证旧写拒绝、切图暂停、不抢视图、已有运行继续；A后台完成预览归A，不串B |
| FR-10/11 来源与恢复 | 数据固定版本及既有保护保留；⑤当次运行内容、多次自动图像预览、另存方案、所选完整结果和S6显式固定结果续跑待实现 | 按⑤概要（原模块文档`src/astrophotoflow/modules/workflows/README.md`，G6已拆除）、AT-06／09／18／20／21补证据；预览不代表完整文件仍在，核对／补登记不重跑 |
| FR-12 本地上下文 | 偏好、项目背景、工作流经验与交接摘要均待实施；个人偏好历史可查看／恢复为当前，删除包括历史正文；不包含完整聊天或模型会话 | 后续按 AT-22、AT-30、AT-31 验证，暂无完成证据 |
| FR-16 节点制作 | ④设计已收敛为workspace可编辑节点库、可选测试、最近测试查询及确认更新，均待实现；Python／复合S6，导出另行规划 | 按[④概要](../../src/astrophotoflow/modules/nodes/README.md)、AT-03／29验证参数重置、变化端口、加载及执行中保护，暂无产品节点测试命令 |
| FR-13/15 交付 | 固定引擎、现有init/start/status/stop、完整网页、源码外安装和无Node重建；MCP启动、端口冲突自动选择及实际地址交接、网页公共配置、CLI／MCP重启、日志轮转与确认清理待补 | `tests/core`、`tests/packaging`、`scripts/verify_distribution.py`；新增验收见[公共概要](../../src/astrophotoflow/core/README.md) |
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

- FR-02、FR-03、FR-07～FR-12、FR-16及其他有效FR的未完成部分，按[现行需求](../requirements/README.md)与[当前路线](../archive/2026-10-29-planning/development/platform-roadmap.md)推进；使用现行AT及覆盖解释，旧需求包已删除，不对不存在的冻结清单宣称散列校验通过。
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

<a id="direct-canvas-editing"></a>
## 本地画布直接编辑候选（2026-10-30）

分支 `codex/hot-reload` 未提交候选；用户明确取消画布接管／交回，按对话指令直接使用 MCP／CLI。移除前后端 `control_token` 和素材库交接入口，保留平台认证、明确目标、内容校验、原生撤销及操作回执。

- 自动检查：主前端与 UI 包类型检查、定向生产代码 ESLint、Python 语法、OpenAPI 生成及 diff 检查通过。新增／更新回归测试涵盖直接编辑、只读不变、错误目标、过期内容、离线、切图、重复请求与 CLI／MCP schema；未运行测试套件。
- 实际运行：只更新本任务 `hot-reload` 预览，重启操作 `5d5c8336-6101-4b1c-922e-a3d6de123814` 完成。通过当前源码新启动的 stdio MCP 会话确认66个工具、`edit_canvas` schema 与页面状态不含控制标记。
- 用户指定画布：Test1 `0867fc1c-a5d3-4ccf-962d-f34414fe40c0`，单张 M45 节点10 `science` 连接现有 Auto Stretch 节点11 `image`，连线5。操作 `14b5a668-bc81-4fa9-9d84-2727b76521bd` 回执成功，重新读取实际图确认端口两侧引用同一连线且节点数量不变。未使用 Computer Use，未提交工作流执行，不代表完整图像处理或用户视觉验收通过。
- 证据位于 `.artifacts/implementation/hot-reload/` 的 `direct-canvas-mcp-schema.json`、`direct-canvas-mcp-result.json`、`direct-canvas-connected-graph.json` 及对应类型／lint／重启日志。当前聊天已缓存的旧 MCP 描述仍需宿主重连后更新；本次实际连线使用的是上述新会话。

<a id="canvas-delete-node"></a>
## 内部 MCP 删除单个节点候选（2026-10-30）

分支 `codex/hot-reload` 未提交候选。`edit_canvas` 增加 `delete_node` 与节点ID，前后端契约及 OpenAPI 同步；调用原生 `graph.remove`，沿用现有原生变更／撤销事务，不直接改文件、不删除素材、不新增工具或兼容层。

- 自动检查：主前端类型检查、定向生产代码 ESLint、Python语法、OpenAPI生成及 diff 检查通过。补充原生删除关联连线、保留来源节点、缺失／受保护节点拒绝、CLI传输和MCP schema用例；未运行测试套件。
- 真实 MCP：新版 schema 包含 `delete_node`；随机离线目标被 `CANVAS_OFFLINE` 拒绝。独立预览后端重启 `b57cbf1d-63ab-40aa-9cf7-a1d8a05bde0b` 完成；前端热更新曾触发 Vue 组件错误，用户刷新后恢复在线，不据此认定完整热更新可靠性验收通过。
- 用户明确选择仅操作后打开、最近编辑的 Test1 页面。刷新后的页面 `38b01ad9-1833-444c-86e6-e749162070d2` 内容标记与该页面此前一致。通过新 stdio MCP 会话删除 Siril Auto Stretch 节点11，操作 `43340fe5-3003-4915-bc7d-f19e2a568e79` 回执成功；重新读取实际图仅剩 M45 节点10，固定素材版本 `7009caca-13a9-4ef8-af97-4266c89d543b`、标题和位置不变，相关连线已清理。
- 回执节点ID为字符串 `"11"`，图序列化ID为数字11，均符合既有联合类型；验收脚本修正比较方式后只查询原回执和实际图，没有重发删除。保留原生撤销机制，未执行撤销恢复节点；未使用 Computer Use、未提交工作流运行、未改动另一页面或素材原件。
- 证据位于 `.artifacts/implementation/hot-reload/` 的 `delete-node-mcp-schema.json`、`delete-node-request.json`、`delete-node-mcp-result.json`、`delete-node-after-graph.json`、`delete-node-verification.json` 及对应日志。

<a id="hot-reload-review-candidate"></a>
## 热更新与本地画布编辑 Feature 集成交接（2026-10-30）

用户确认进入集成阶段，分支 `codex/hot-reload`，完整基点 `2a6053eb3e8351156d7fb2b4b1ed208e6e628bc0`。准确待审提交及最终预览对应版本以交接 Brief 和 `.artifacts/implementation/hot-reload/review-handoff.json` 为准；交接后冻结，不推送或自行合并。

- 最终范围：workspace 感知的前端 Vite 开发更新；已安装 Bundle 声明的 SDK Python 适配器及清单／操作／节点 JSON 热加载，安装／更新／卸载后刷新能力；保留网页安装计划确认，按用户要求取消实际调用繁忙拒绝和在途旧实现保护。平台任意后端 Python 不自动重载；当前未提供 Node.js 适配器加载器。
- 开发中追加：本地新工作流不自动打开模板；修正严格 JSON UUID 回执校验；隔离 Windows Bundle 子进程程序搜索路径，实际 Siril `--version` 返回1.4.4；Git上报的分阶段真实百分比；Windows状态替换短暂占用最多5次／50ms重试，进度耗尽只记日志，最终结果保存失败明确需核对。
- 节点与画布：隐藏原生 Comfy 节点入口，保留 Data 与按 Bundle 名分类的扩展；Data 支持绝对路径导入为托管固定引用；内部 MCP／CLI 直接按用户指令编辑，不设接管标记，保留认证、目标／内容检查、原生撤销及操作回执，新增 `delete_node`。原生节点仍注册以便旧图加载，不承诺端口／参数自动迁移或正式运行闭环。
- 已执行：主前端、UI包与Vite构建类型检查，定向生产代码lint、Python语法、OpenAPI生成、文档链接及diff检查；其中构建类早期记录须按源码指纹区分。独立临时文件6项状态写入检查通过。真实新MCP会话已确认无接管schema、离线拒绝、连线、删除并保留M45固定引用；随后按用户指令给当前 Markarian's Chain 数据节点12添加自动拉伸节点13并连接连线6，`targetbg`由0.25调至0.40，实际图均已核对，未执行完整工作流。
- 未验证／已知问题：测试套件、完整Bundle更新版本切换、自动热加载可靠性、路径导入真实文件、原生撤销实际恢复和完整科学处理仍交Manager按范围验证；Vue热更新曾出现组件错误，刷新后恢复。当前聊天旧MCP工具schema需宿主重连；实际验收使用绑定本workspace的新stdio会话。预览多页面可有不同草稿，不自动同步；平台目录固定发布版本，不自动发现GitHub最新版本。
- 跨仓库依赖：`MaojieXu/AstroPhotoFlow-Siril`，Bundle `0.1.2-dev.1`，tag `v0.1.2-dev.1`，commit `12fd2d1d55daeadf7acb3972385d5c2bfcb52d4d`，软件Siril `1.4.4`。平台目录、安装锁及实际checkout一致且checkout干净，本轮未提交Bundle仓库。
- 本机配置：本轮经用户明确授权将全局 `astrophotoflow` MCP 注册切到本Feature源码和 `hot-reload` workspace；原注册备份在 `.artifacts/implementation/hot-reload/mcp-registration-before-20261030-024945.toml`。这是本机配置变化，不属于Git提交；集成／清理时由Manager决定保留或恢复，不据此修改正常dev或默认workspace。


<a id="hot-reload-integration"></a>
## 热更新与本地画布编辑本地集成验证（2026-10-30）

用户授权独立审查、必要验证、最小修复及本地合并dev；不推送、不清理Feature空间。原候选`ef56e0cef8a66f86f9d8331b41e330f8238aedf3`，基点`2a6053eb3e8351156d7fb2b4b1ed208e6e628bc0`；Manager源码修复提交`52da83199a86e09ce38354503e25f99e4c2ca18a`。最终范围以上方Feature交接及用户本轮Brief为准，保留已明确取消的占用／接管限制，不恢复旧要求。

- 独立审查：Reviewer不继承开发聊天历史，只读审查全部变更；发现并修复三项P2：重载后采用未经加载的新哈希会漏掉连续编辑；卸载后仅注销LiteGraph而搜索目录残留；开发入口裸Python未采用uv项目环境。修复增量复审未发现阻塞合并问题，Reviewer未修改代码或运行测试。
- 后端回归：软件、节点、工作流、interfaces、CLI／MCP协议／客户端、原生Bundle热加载及Python架构检查首轮113项通过；修复后相关14项复测通过，包含新增的受控Bundle版本替换用例。按唯一用例汇总114项，未执行全仓测试套件。连续编辑与失效目录回归均先在原实现复现失败，再在修复后通过。
- 前端回归：UI包35文件273项通过；受影响原生前端8文件101项经修复复测全部通过，另有1项Vite同源代理测试通过。修正新增测试与共享清理顺序冲突，并使用仓库既有本地HTTP代理集成测试模式，避免真实外网请求；没有关闭网络保护。前端回归按唯一用例汇总375项。
- 受控版本切换：fixture从Bundle `0.1.2-dev.1`切至`0.1.2-dev.2`，覆盖安装目录及锁记录替换、Python适配器切换、操作默认值与原生目录刷新、无需重启、卸载保留原件和工作流。checkout及程序版本检测使用受控替身；不等同跨两个真实发布版本升级。Siril实际依赖仍为`0.1.2-dev.1`／`12fd2d1d55daeadf7acb3972385d5c2bfcb52d4d`，未修改Bundle仓库或发布标签。
- 合成数据浏览器运行：在独立验收workspace、独立32788／32790服务和32789 Vite中，用Chrome无界面浏览器真实从绝对路径导入合成PNG，得到托管固定素材引用，核对原件字节不变；原生键盘撤销／重做恢复科学引用；通过画布编辑桥删除节点后原生撤销恢复节点和引用。4项检查通过，页面错误0。未操作Feature既有图或真实素材，未提交完整科学处理工作流。
- 静态与构建：修复源码定向ESLint无错误；测试文件不在该ESLint配置范围，另由Vitest及所属类型项目验证。Vite build类型检查通过；前端依赖边界0错误、13条data/workspace循环警告。完整原生类型检查及前端生产构建通过，`build-manifest.json`记录源码`52da83199a86e09ce38354503e25f99e4c2ca18a`。首次构建因类型编译桥`C malloc failed`失败；停止本轮临时验收实例后，以进程级`GOMAXPROCS=2`、`GOMEMLIMIT=2GiB`、`NODE_OPTIONS=--max-old-space-size=4096`串行重试通过，未改项目依赖或编译检查。构建仍有非阻塞资源／动态导入／插件耗时警告。
- 证据：完整日志、浏览器脚本／结果／截图位于Feature Worktree `C:/Users/Administrator/.codex/worktrees/dbc5/AstroPhotoFlow/.artifacts/manager-integration/hot-reload/`，主要为`python-tests.log`、`python-fixes.log`、`ui-tests.log`、`native-frontend-tests.log`、`frontend-fixes-final.log`、`browser-smoke.json`、`final-frontend-build-retry.log`、`build-typecheck.log`、`frontend-boundaries.log`。初始失败日志一并保留。临时验收实例已准确停止，证据和数据保留。
- 交付边界：仅本地Git集成；正常dev运行实例、默认workspace、Feature原预览及全局MCP注册未迁移或重启。旧MCP schema仍需宿主重连；全局注册仍指Feature的本机状态及原配置备份继续保留。长期热加载可靠性、完整科学处理／输出保存及用户视觉验收未因此认定完成。


<a id="siril-sdk-v2-integration"></a>
## Siril全量候选与SDK v2本地集成（2026-10-30）

用户授权整理待审提交、独立审查、必要验证、最小修复及本地合并。原平台候选`0f53b719584ec68a8dd277c27713fde84e084a7c`基于`2a6053eb`，在Feature分支整合当前dev `4d17208c`并保留热加载、直接画布编辑及已取消的占用限制。平台最终功能源码`e322d0744db82d26fb1b138e0818b75d1fdcbbe1`；后续仅补本记录及现行文档。私有Bundle原候选`68509bdf`，最终源码／本地开发tag `v0.2.0-dev.1`固定到`3f0f2a64c8b24cc8ca940d945139304cf871efed`，Bundle管理checkout本地dev合并为`ff6f63fe9d866cf34e3aa612157511ee81d9e89c`，合并树与待审源码一致；未推送或发布远端tag。

- 范围：固定Siril 1.4.4，199索引项保留完整覆盖依据；160操作／节点，会话、IO及重复命令按已确认的映射处理，非脚本／GUI限制明确说明。SDK v2提供具名输入、多输出、分析、进度及取消，保留SDK v1。构造计划与原生加载不替代全部节点真实运行验收。
- 独立审查：两名不继承开发聊天历史的只读Reviewer分别审查Bundle命令／科学语义和平台SDK／结果接入，均不修改文件或运行测试。Bundle六项P2已修复：ICC intent枚举、limit参数、profile通道、register畸变文件语法、seqstat TSV解析和stat CFA／main组合误报。修复时误改的REGISTER通道已恢复整数0..2并补回归；最终复审无阻塞。平台及后续增量复审无阻塞。
- Manager验证修复：去掉可变目录对象共享缓存；显示阈值支持严格JSON往返；明确排除一维字节ICCProfile附属HDU的科学帧数误判；结果扩展复用已有同名扩展以支持TS热替换；160节点目录改为请求内按包批量描述，读取从回归中的960次降至每包有界读取，保留跨请求读取现状；持久化调用／输出JSON以JSON模型边界恢复UUID、时间及路径，未知状态只查询而不重放。结果组件两处样式lint同步修正。上述行为均补充定向回归，关键缺陷先复现失败后通过。
- 自动回归：平台软件／节点／工作流／数据／interfaces、CLI／MCP、客户端、原生热加载及架构首轮547项中539通过、8失败；修复后相关29、7、139、45、24项分批复测通过，新增目录隔离、阈值往返、ICC、批量目录及持久记录／恢复共6项用例。按唯一用例汇总553项，未运行全仓测试。独立Bundle39项通过；UI包36文件276项通过；原生桥接14文件68项通过。完整原生类型检查未排除任何错误文件，生产构建通过；测试扩展签名问题修复后重试通过。定向生产代码ESLint无错误；前端依赖边界0错误、13条循环警告。
- 原生及真实CLI：使用实际Siril程序版本检测及固定ComfyUI 0.42.0 API注册160节点，全部节点信息可序列化。CLI矩阵41组正常处理通过，随后ICC赋值→转换、固定有序组、序列／单图校准、FFT两输出→逆变换共7组通过；FFT像素往返容差`2e-5`，原件hash不变。矩阵覆盖图像运算、序列、注册、叠加、多输出和分析，不等于160节点逐一通过。最初ICC脚本夹具使用不存在设置项，已改用真实ICC前置链；由真实ICC输出发现的附属HDU问题已修复。
- 明确保留的失败／依赖：当前Windows `seqprofile`生成DAT后进入Siril自身Python／plot准备并以`0xC0000005`退出，未计为运行通过；StarNet未配置程序时返回真实缺依赖错误。未自动补装外部依赖、未宣称联网目录、星表／SPCC、视频编码器或任意Python脚本组合已验收。Bundle使用说明单列当前限制。
- 实际取消：独立父子进程探查确认仅停止观测到的所属进程树，保留另建的无关进程；丢失句柄维持unknown。该探查不是160种Siril计算的逐项取消验收。
- 独立网页／端到端：通过当前网页确认安装本地固定tag／SHA，160节点实际加载。真实原生队列完成统计、512桶直方图、RGB拆分及三路下游统计共6次节点调用，结果归属同一工作流。通用分析查看器显示直方图，计数之和与128×128像素数一致，页面错误0。重启后6条已完成调用仍可查询，完整输出查看器可用，素材库仅含合成输入。节点目录本机单次观测811ms（160节点），没有把超时调大作为修复。
- 最终预览：`http://127.0.0.1:32888`，服务32890；workspace为Feature内`.artifacts/manager-integration/siril/preview`，由进程级`ASTROPHOTOFLOW_BUNDLE_CATALOG`采用干净tag快照，默认目录／默认workspace／全局MCP／正常dev未改变。已同步最终资源，`build-manifest.json`对应`e322d0744db82d26fb1b138e0818b75d1fdcbbe1`；仅本地可用的合成图保存为`workflows/Manager-Siril-SDK2.json`。包内默认发布目录仍为旧版0.1.2-dev.1，未指向尚未推送的GitHub tag。
- 证据：Feature Worktree `C:/Users/Administrator/.codex/worktrees/bfe6/AstroPhotoFlow/.artifacts/manager-integration/siril/`保留完整日志、脚本、失败记录、原生记录和截图，主要为`platform-tests.log`、`platform-final.log`、`records-after.log`、`catalog-after.log`、`bundle-final.log`、`ui-tests.log`、`native-frontend-tests.log`、`native-probe.log`、`runtime-matrix/report.json`、`runtime-matrix/focused-report.json`、`cancellation-probe.json`、`browser-acceptance.json`、`completed-native-history.json`、`final-preview-verification.json`、`final-frontend-build-retry.log`和`final-assets.log`。Feature空间及必要运行数据保留。

<a id="environment-bootstrap-feature"></a>
## 环境与workspace准备拆分（2026-10-30，Manager集成验证）

- 实现：core拆分runtime准备与空workspace创建；固定开发入口默认只准备本地依赖／目录，显式构建、启停，输出阶段回执。保留私有runtime，包缓存及同基点本地网页可复用。
- 静态：8个修改Python文件语法与文档链接检查通过；引擎归档生成成功，前端源码未变。实现验证使用基点`b625045c388953ac9dc4b28ec5d1a318385ac239`网页及该基点上的工作区改动；最终交接提交与预览版本见Feature Brief。
- 实际准备：本机依赖已经存在时，空workspace首次准备1.511秒、再次准备1.378秒；重复调用跳过依赖安装，无构建／CPU安装／服务启动。这不是冷缓存首装耗时。runtime及已运行实例复用、仅本Feature重启通过；5项HTTP就绪与代理workspace身份核对通过。
- 预览：网页33088、Vite33089、服务33090；workspace为本Feature的`.artifacts/workspaces/environment-bootstrap`。默认配置哈希不变，正常dev、其他Feature与全局MCP未修改。
- 边界：已编写workspace无安装、准备幂等／中断、依赖失效、错误产物、运行中保护及CRLF回归用例，未执行测试套件或综合验收。冷缓存首装、多Worktree共享缓存及Linux／WSL尚待验证。更新Vite时短时限首屏探测曾超时，现有进程完成编译后HTTP核对通过，未用重启掩盖。
- 证据：本Feature`.artifacts/logs/environment-bootstrap/`中的`implementation-verification.json`、`dev-prepare-first.json`、`dev-prepare-final-repeat.json`、`dev-preview-repeat.json`、`readiness-current.json`，完整阶段日志由`.artifacts/dev-prepare.json`指向。

- Quickstart补充：根README提供clone dev后的无Agent命令；Windows PowerShell 5.1入口复用或在项目内准备工具，固定Node／uv归档校验，Python安装显式禁止注册。已有工具复用、本地Node解压及pnpm准备路径通过；完整构建／启动命令在已有Python与依赖缓存条件下66.985秒完成，热更新入口转发核对通过。全新无缓存机器首装尚未验收；新增离线缺失／校验失败及兼容工具复用回归用例未执行。检查实例已停止，原Feature预览保留。证据为同目录的quickstart-verification.json、quickstart-build.log、bootstrap-existing.log、bootstrap-managed-tools.log、quickstart-watch.log。

- Manager集成审查：基点`b625045c388953ac9dc4b28ec5d1a318385ac239`，原始候选`242b6133257fb3d9230d82527caaf7c032536125`。独立上下文只读Reviewer确认并复审了未知控制状态提前拒绝、同HEAD网页实际内容比较两项修复；网页同步同时删除目标web目录内已淘汰的文件，防止旧hash资源导致持续误拒绝。最终复审无新增可确认缺陷。
- Manager自动验证：工作台、环境准备、引擎构建及CLI客户端契约共64项通过，包括新增未知／启动中／停止中保护、同SHA内容变更／新增／删除及真实网页同步回归。原损坏归档测试因继承Codex PowerShell 7模块路径失败，已在测试子进程清除`PSMODULEPATH`，恢复PowerShell 5.1默认模块后通过；未为此改bootstrap产品行为。
- Manager实际验证：固定Quickstart入口离线复用已存在依赖2.848秒，不构建／安装runtime／启停服务；独立空workspace CLI创建0.505秒，runtime与网页未创建、默认配置哈希不变。耗时仅代表本机已有工具和缓存条件。原候选完整构建与33088预览证据仍有效，管理入口修复不涉及前端源码，未重复全量构建或功能验收。未推送、不清理Feature空间。
- Manager证据：本Feature`.artifacts/manager-integration/environment-bootstrap/targeted-tests-final.log`、`prepare-smoke.log`与`empty-workspace-smoke.json`。全新无缓存机器首装、多Worktree共享缓存并发、Linux／WSL仍未验收。

<a id="feature-full-preview-preparation"></a>
## Feature完整准备与页面展示（2026-10-30，Feature实现检查）

- 实现：Feature交接默认通过bootstrap传入`--build --start`，低等级准备仍显式保留。缓存按命令行、环境变量、本地目录选择并贯穿工具和依赖阶段；bootstrap开始即写入未完成回执，参数校验失败也覆盖旧成功状态。调用标识、参数、起止时间及包含工具阶段的耗时进入同一回执，阶段日志按调用标识隔离。页面打开及实际展示由Agent分别确认，脚本不自动打开系统浏览器。
- 定向排查：本空间`.artifacts/toolchains`为指向`.artifacts/python`的Junction，Node／pnpm／uv和Python安装混放导致uv目录扫描警告。开发入口改用独立`.artifacts/managed-python`，未删除或搬迁既有工具／解释器。旧回执在成功启动后仍显示初次依赖准备的内容，实际写回来源未能归因；新实现以调用标识、参数和时间区分调用，bootstrap要求子进程返回对应标识的最终回执。
- 实际构建／启动：平台基点`a53b32131862435cf19a3ad190560ca846563295`加本轮未提交变更，本Feature独立workspace `C:/Users/Administrator/.codex/worktrees/64b7/AstroPhotoFlow/.artifacts/workspaces/agent-i18n-bundle-cicd`。通过core准确停止该实例后，固定入口完整执行成功；调用`af99f27c271b4d53b0fd173eaf229ad8`，bootstrap 0.435秒、完整构建含类型检查34.747秒、runtime核对复用0.538秒、workspace 1.283秒、启动11.530秒，磁盘回执总耗时49.622秒。Python及前端依赖复用，runtime复用；这不是冷缓存首装耗时，也不包含停止旧实例或页面展示时间。
- 页面展示：浏览器实际打开`http://127.0.0.1:32618/#/workflows`，确认越过加载页并渲染素材侧栏、工作流画布及运行控件，捕获的控制台error为空。服务端32620；没有操作真实素材或执行科学处理。CSS公共路径修正并补入既有GitHub SVG后，两项缺失资源构建警告消失；仍有上游SVG样式警告，不扩展为全量前端清理。
- 已编写未执行：包装测试新增缓存参数两种形式及环境变量优先级、工具失败回执、参数失败替换旧成功、构建失败中止、完整流程顺序／启动失败、托管Python目录隔离；更新兼容工具复用测试以核对统一回执。Python／PowerShell语法检查及Git空白检查通过，未执行测试套件、综合验收或Manager独立审查。新版本冷缓存首装及冷runtime、离线失败自动回归留待集成验证；本轮实际验证覆盖已有依赖与私有runtime复用。
- 证据：本Feature`.artifacts/dev-prepare.json`和`.artifacts/logs/dev-prepare/af99f27c271b4d53b0fd173eaf229ad8/`、`.artifacts/feature-preview.png`、`.artifacts/preview-resources.json`。预览保持运行，未提交、推送、合并或操作main，未修改默认workspace／全局MCP／正常dev。

<a id="workspace-bilingual-feature"></a>
## Workspace中英切换（2026-10-30，Feature实现与独立预览）

- 源码版本：平台Base／HEAD均为`a53b32131862435cf19a3ad190560ca846563295`，私有Bundle Base／HEAD均为`ff6f63fe9d866cf34e3aa612157511ee81d9e89c`，均在`codex/agent-i18n-bundle-cicd`上有本轮未提交修改；保留前一项完整准备流程修改。Bundle候选声明`0.2.0-dev.2`，无新提交或开发tag，不将其冒充原HEAD对应的已发布版本。
- 实现：只注册English／简体中文；沿用原生`Comfy.Locale`、浏览器首次偏好及保存机制，旧中文地区标签归并zh，其余不支持标签归并en。core只读原生workspace设置；新增认证语言查询，经AssetClient及同源白名单消费。UI包提供574条双语消息并注入宿主翻译函数，不反向依赖宿主单例。错误以稳定消息键与参数在HTTP边界展示，保留错误码、请求ID、字段路径及原始诊断，不改历史运行事实。OpenAPI已通过现有脚本生成。
- Bundle：独立展示资源通过可选manifest声明加载，中英文各160项，参数和端口名称集合与真实操作声明一致，编写时已实际生成并通过Pydantic静态校验；生成脚本同时维护双语资源，翻译文件纳入原生目录变化观察。执行定义和科学参数未新增展示字段，节点内容标记与操作令牌计算保持原有输入；自定义用户节点名称不被Bundle展示名覆盖。中英搜索使用两套展示文案及稳定标识，旧Bundle缺译保留原文。
- 构建：UI包和原生应用完整类型检查、引擎打包及Vite生产构建通过。最终调用`fd4e6cb796154397a958d1c44f44372e`，构建32.234秒、workspace同步1.050秒、双服务启动11.634秒，最终磁盘回执总耗时46.947秒；依赖及私有runtime复用。预览`http://127.0.0.1:32618`，服务32620，workspace为本Feature的`.artifacts/workspaces/agent-i18n-bundle-cicd`；网页清单记录平台基点SHA，源码脏状态另记，不声称是已提交发布产物。
- 实际页面：菜单确认仅两个语言选项，素材侧栏／设置／原生控件即时更新，刷新后English保留，往返后恢复中文。切换修复前发现PrimeVue Toast未注入、原生下拉框选中标签缓存、关闭表单在标题翻译后仍聚焦三项实际问题，均做最小修复并重建；最终刷新及往返期间捕获的浏览器控制台error为0。未执行科学处理或编辑素材／图。
- 实际只读联调：独立stdio MCP连接按workspace保存值分别返回中英文说明，各69个工具，实际输入schema一致；静态核对工具名、函数签名一致。相同不存在素材的404错误保留`RESOURCE_NOT_FOUND`及字段列表，消息随语言改变且各自保留请求ID。两次语言下两个在线页面的page／workflow／graph ID及content_token完全一致，软件package_token一致。软件详情客户端的严格Python校验曾拒绝JSON路径和UUID，已改为严格JSON契约解析，实际只读详情查询恢复。
- 已编写未执行：core语言规范化、缺失／损坏／不可读文件、认证API、插值与诊断保留；MCP双语名称／schema／签名、展示投影与JSON路径／UUID；Bundle缺译回退、展示变更不改变操作令牌、参数映射及160项完整性；UI语言反应性、0／1／多项计数、资源键／插值对称；原生下拉文案更新不发值变更及关闭表单不聚焦。上游类型检查暴露的fr／ko／zh-TW引用及相关测试夹具已同步到中英规则。未运行测试套件、Manager独立审查或综合验收。
- 待验证边界：当前预览安装的是旧Bundle `0.1.2-dev.1`／`12fd2d1d55daeadf7acb3972385d5c2bfcb52d4d`，缺译按原文展示。新Bundle候选尚未提交、固定tag或安装，160项新资源的真实安装、原生显示／参数提示及跨版本升级留待获准固定候选后的集成验证；不绕过干净tag／SHA安装规则。首次浏览器／旧设置迁移及全部表单逐项验收亦不从基本页面检查推定通过。
- 证据：本Feature`.artifacts/dev-prepare.json`与对应run_id阶段目录，`.artifacts/mcp-languages.json`、`.artifacts/i18n-live-en.json`、`.artifacts/i18n-live-zh.json`、`.artifacts/i18n-live-comparison.json`、`.artifacts/i18n-preview-en.png`、`.artifacts/i18n-preview-zh.png`、`.artifacts/i18n-final-browser-errors.json`。初次浏览器错误保存在`.artifacts/i18n-initial-browser-errors.json`，类型构建失败日志保留于`69e79ff7cd414976acb140be5f69344a`目录。两个仓库均未提交、推送、合并或发布；默认workspace、全局MCP和正常dev未修改。


## Bundle 安装快照及后台错误语言修复（2026-10-30，Feature）

- 用户实际安装 `v0.2.0-dev.1` 失败后定向定位：commit `3f0f2a64c8b24cc8ca940d945139304cf871efed` 的 `reference/assessments.json` 原始 Git blob 使用 LF；元数据专用检出未带入完整目录的 Git 属性，在 `core.autocrlf=true` 下得到 4,990 处 CRLF。现有确认快照与完整检出逐字节比较误报；不是远端 tag 或参考内容改变。两个官方开发版本的四份参考文件核对后，仅该文件有字节差异，CRLF/LF 规范化后均与所选提交一致。
- 修复：新快照规范化 CRLF，安装比较兼容既有缓存快照的 CRLF/LF 差异；其余内容、文件集合、tag、commit、manifest、操作、节点和翻译校验仍保留。无须删除缓存或重新解释 latest。
- 错误：后台动作和确认失败按 workspace 语言生成消息；嵌套 ApiError 原因使用原有消息键及参数递归本地化，避免英文外层包含中文平台原因。安装状态保存本次本地化原因，外层响应和状态均保留诊断字段。原始程序日志及已保存历史失败记录不重写。
- 定向回归用例已编写：换行等价／实际内容变化拒绝、中英安装失败状态、后台 pending/result 双重错误及诊断保留、嵌套原因本地化。未执行测试套件或综合安装验收，留待 Manager 集成验证。8 个涉及 Python 文件的语法解析通过；实际缓存证据及两种语言消息见 `.artifacts/bundle-install-fix-evidence.json`。

- 构建与真实观察：调用 `7732686a9b194a63b6d6420d970fcd26` 完成类型检查／生产构建及双服务启动，构建 77.358 秒、启动 26.681 秒、总计 107.234 秒。预览32618、服务32620保持本 Feature workspace。用户重新确认安装后，实际 `v0.2.0-dev.1`／`3f0f2a64c8b24cc8ca940d945139304cf871efed` 安装完成，状态 completed、last_error=null，原生热加载 ready 且160节点；网页已显示完整 Siril 节点目录。该观察仅覆盖本次目标安装，不替代测试套件及综合版本切换验收。截图 `.artifacts/bundle-install-fixed.png`。


## 平台错误双语补齐（2026-10-30，Feature实现）

- 平台分支 `codex/agent-i18n-bundle-cicd`，Base／HEAD `a53b32131862435cf19a3ad190560ca846563295`，本轮未提交。保留此前完整准备、中英切换及官方版本选择修改；本轮不修改或重新发布 Siril Bundle。
- core新增统一错误构造和异常表达，所有新增提示使用明确消息键及参数。ApiError保留具体原因和诊断字段；平台自有字段指导通过内部消息键本地化，公开 ErrorDetail 仍为 code／message／fields，HTTP请求标识不变。无消息键的外部旧异常使用调用位置指定的提示，原文进入诊断，不按错误码猜测业务分支。
- 覆盖确认过期／状态冲突／无待确认动作、原生页面桥接、画布未知回执、同源代理、安装／卸载、软件执行与观察／结果记录、节点写入、素材内容检查、来源枚举、导入／上传和查看器准备失败。退出码使用插值，Siril日志和外部异常保留原文；已有落盘错误不重译，输出登记读取时保留历史诊断字段。不改数据库结构、执行／取消状态或重试行为。
- 定向用例已编写：双语消息与插值完整性、错误构造位置检查、嵌套原因及字段指导、未知外部异常、确认过期／冲突不启动任务、桥接／代理／MCP错误、画布未知状态、非零退出与原始日志、观察／结果记录失败、素材检查、导入及历史回执。旧导入异常注入夹具补充明确消息键。测试套件及综合验收未执行，留待 Manager。
- 静态验证：177个Python源码／测试文件编译，平台入口导入成功；424条消息中英插值集合对称，新增错误构造静态扫描无缺失消息键或直接字面错误对象；Git空白检查通过。证据 `.artifacts/platform-error-localization-check.json`。类型检查／构建及独立页面结果见本节后续回执。

- 最终构建／展示：回执 `fac2ea3df3ea440a818ee20ceed2cfcf`，类型检查和生产构建通过；构建29.681秒、启动11.445秒，总耗时44.149秒。预览 `http://127.0.0.1:32618/#/workflows?apf_panel=software`、服务32620，私有runtime复用。浏览器实际加载工作台和软件包侧栏，Siril `0.2.0-dev.2` 就绪，捕获控制台error为空；截图 `.artifacts/platform-error-localization-preview.png`。未切换用户语言、执行工作流或操作素材；未提交、推送、合并平台或重新发布Bundle。页面加载不代替异常分支的Manager验收。


## Bundle 官方版本管理与待审交接（2026-10-30，Feature）

- 实现：认证版本查询、按提交缓存的官方Git元数据、数字版本排序、正式／开发两个最新标记、兼容状态及固定选择令牌；每包一行单下拉、显式安装计划确认、升级／回退、刷新与失败保留旧列表。旧安装请求仍使用固定目录，program version与Bundle version分开；语言切换只更新展示。两个历史实验标签不提供安装。
- 实际观察：官方远端列表发现两个既有开发版本；选择0.2.0-dev.1的160项元数据，未提前检出完整程序。安装暴露CRLF／LF快照误判，修复后目标版本真实安装成功并热加载160节点。随后按用户单独授权发布双语Bundle `v0.2.0-dev.2`／`5d16fb6fc10b4ee57de428d6eba522c918b1b441`，远端接口识别为最新兼容开发版；当前独立预览已安装该提交并就绪。发布到Feature分支和开发tag，未合并Bundle dev，不代表正式稳定发布。
- 定向用例已编写未执行：正式／开发混排、dev.9／dev.10、两个最新标记、正式优先、兼容禁用、旧安装与未列版本、失败保留缓存、批量仅取声明元数据、移动tag拒绝及固定目标不随新tag改变；前端刷新／语言切换保持选择和安装目标。综合安装／回退与异常验收由Manager组织，已有单次真实安装观察不能代替这些测试。
- 待审交付包含本聊天完整准备流程、平台／Agent／Bundle双语与官方版本选择以及错误覆盖修复。平台保持本地待审，不推送、不合并；Siril沿用此前已授权发布的准确提交，不再次发布。最终平台Commit及同提交构建回执见聊天Brief，避免在提交内容内自引用提交SHA。


<a id="agent-i18n-bundle-integration"></a>
## 完整准备、Workspace中英切换与官方Bundle版本管理集成（2026-10-30，Manager）

- 准确候选：平台原候选 `1e47a035d42564034985aa9f480015e2e108f35b`，基点 `a53b32131862435cf19a3ad190560ca846563295`；Manager最终功能源码 `30d6d947562d220f8629b0bc7b2591bc3219c538`，其后仅补验证记录与现状文档。Bundle候选保持 `5d16fb6fc10b4ee57de428d6eba522c918b1b441`，基点 `ff6f63fe9d866cf34e3aa612157511ee81d9e89c`，Bundle `0.2.0-dev.2`／既有tag `v0.2.0-dev.2`／Siril `1.4.4`；本轮不发布tag、PyPI或正式版。
- 独立只读审查：三个不继承开发聊天历史的Reviewer分别检查语言与错误、官方版本与Bundle、准备流程。修复PS5.1对子回执UTF-8的读取、Bundle刷新后的旧翻译残留及双语整快照调用、官方发现缺失workspace受管Git路径、单个缺失或损坏manifest遮蔽全部版本。增量复审无剩余阻塞。
- 真实安装发现并修复：回退dev.1成功后恢复dev.2遇Windows目录rename错误5，原版保留且动作明确failed；只对错误5/32/33同步有界重试，最多6次、累计等待1.55秒，不增加事务异步取消窗口。新增暂时／持久占用、激活失败恢复和原件保护回归；独立复审通过。永久占用仍明确失败，不能把有限重试视为任何外部占用都可解除。
- 自动验证：首轮平台707项中695通过、7失败、5跳过；旧语言断言、取消注入签名、更新夹具和PS终端长路径断言按当前契约修正并复测。按唯一当前用例汇总712通过、5跳过；最终完整软件模块96项通过。新增安装锁回归先复现失败后通过，安装文件23项通过。跳过项为显式环境／维护窗口选择的5个真实进程或Siril集成用例，未记为通过。独立Bundle41项通过；UI包37文件286项通过；原生受影响21文件共311项经首轮及失败文件复测全部通过（包含双语往返图序列化、旧Bundle缺译回原文）。未运行全仓测试。
- 最终构建／准备：UI包及完整原生应用类型检查、生产构建通过；网页清单对应 `30d6d947562d220f8629b0bc7b2591bc3219c538`。固定入口回执 `7472c38d3cb14194840c3a64f5cdfd8d`，依赖与私有runtime复用，完整准备47.394秒；不是冷机器首装基准。静态网页32618／服务32620仅属于Feature。
- 实际网页与MCP：最终静态网页English→简体中文→English并恢复原语言，原生图序列化SHA保持不变，160节点双语，浏览器pageerror为空。两个绑定本workspace的新stdio MCP会话：69工具说明随语言变化，输入schema完全一致；160节点执行定义保持一致，帮助说明随语言变化。未修改全局MCP、默认workspace、正常dev配置或真实原始素材。
- 真实升级／回退：通过网页单下拉与原生确认，完成dev.2恢复、dev.1回退、dev.2再次升级，各次固定tag／commit并达到160节点ready；dev.1无翻译时返回原文，dev.2恢复双语。服务PID `110752`、网页PID `31936`全程未变。官方列表排除历史v0.1.0／v0.1.1，dev.2为最新兼容开发版；选择／刷新／语言切换不自动安装、tag移动与失败缓存保留由定向回归覆盖。
- 限制：未验收全新无缓存机器、冷CPU runtime、Linux／WSL、真实GitHub凭据失效／断网全过程或所有160节点科学处理。5个显式跳过用例与全面用户验收仍未完成；构建保留非阻塞上游告警。
- 清理授权：通过后普通推送两个dev，远端包含候选后删除Feature workspace、私有runtime、分支和Worktree及其内部日志数据，不额外归档副本；本节已提交证据摘要留在Git。完整运行日志原在Feature `.artifacts/manager-integration/i18n/`，按用户要求随空间删除，历史日志路径不代表仍存在。


<a id="database-mcp-data-export-integration"></a>

## 数据库＋MCP优化与Data完整结果导出集成（2026-10-30，Git Manager）

- 授权与版本：用户确认独立审查、必要测试、最小修复，通过后本地合并、普通推送dev并删除本Feature空间和归档原Chat。平台Base `711bd850b122ca64e1f147c645ba6fc0015c42ab`，原候选 `55484461b2f9cbccfe404a3b9f9f58d903f3ce71`，分支 `codex/database-mcp-optimization`。产品修复提交 `1925d394301a7bfe6e77776c8ae43460e82b0632`；准确前端构建、私有双服务和下述实际队列验证对应此SHA。其后仅补充Siril集成测试夹具及本验证记录，不再修改产品源码。
- 最终范围：仅两个公开MCP工具 `data_management`／`node_canvas_management`；已知操作直调，陌生操作按需发现和读取定义。递归检查→分组／疑义→明确确认后批量受理→聚合等待，保留来源变化、防重复、部分失败、取消恢复与项目关联独立重试。独立项目管理与固定引用；Data互斥science／images输入、science单输出；执行和预览不自动入库，用户选择完整成员后保存素材库或本机。FITS／XISF／TIFF／PNG／JPEG精度组合、原样复制默认、显式数值转换、不覆盖和失败不重跑上游。未重写数据库、未修改独立Bundle、未实现Skill管理／反馈或项目原生图生命周期联动。
- 独立只读审查：三位Reviewer分别覆盖导入／项目、科学数据与格式导出、MCP／原生UI；不继承开发Chat历史、不改代码、不代替测试。修复后原Reviewer复审均未发现剩余可确认缺陷。修复包括：项目引用限定任务实际发布且包含本组完整成员的版本，不追随current；按既有失败后追加语义保留该固定版本成员顺序；归档及后台异常明确失败，避免永久running；FITS应用已确认颜色布局，interleaved转planar同步重映射轴与WCS字段；RAW display同样拒绝隐式显影；导出JSON回执恢复严格嵌套UUID；Data绑定复用原生DTO map及resolveInput，支持旁路和子图上下文而保留结果目标校验。
- 缺陷证据：六条新增回归先在候选上失败后通过，覆盖无头标记planar FITS（宽3静默错轴及宽7失败）、interleaved通道轴／WCS、RAW display、项目版本漂移和归档后重试。复审补充前序成员登记失败后重试成功的真实恢复回归。新增旁路及取消旁路后绑定变化与图序列化不变用例。既有UI两处仅改为从公开入口进入设备管理，保留数字类型和失败时不得串项目行的断言；旧Data同步直通断言改为科学引用契约校验，真实异步Data由队列验证。Siril旧条件测试夹具补齐SDK v2 operation／hidden／准确commit／完整参数及成员输出目录，保留关键结果断言；独立复审确认无断言弱化。
- 后端验证：`tests/modules/data tests/modules/workflows tests/interfaces tests/integration tests/architecture`最终完整运行 **583 passed／5 skipped**（265.76秒）；另真实stdio整夜导入 **1 passed**，启用私有CPU解释器及已核对Bundle源码的两项Siril测试 **2 passed**。按测试身份去重并用后者替换两个条件跳过，最终 **586 passed／3 skipped**。剩余跳过为完整Bundle安装编辑移除热加载及M1生命周期／启动失败排空的显式维护窗口用例，不计为通过。合成截断FITS与现有ORM环排序告警保留。一次并行回归误用默认pytest临时目录导致初始化冲突，改用各自独立basetemp后重跑；最终计数仅来自独立目录成功结果。
- 前端验证：UI包 **37文件286 passed**；受影响原生桥接／侧栏及executionUtil、ExecutableNodeDTO **18文件122 passed**（115项成功及CanvasDataWidget最终7项成功合并，无失败）。UI和原生类型检查及完整生产构建通过，保留非阻塞上游打包告警；Git空白检查通过。构建后通过固定bootstrap仅重启本Feature，最终回执completed／ready=true、dirty=false，网页32688、服务32690；回执run `e7f8b8f251c747ab832a95c16e57ae6a`，交接不使用旧候选清单。浏览器实际看到素材库、画布、项目独立入口和项目页，不只HTTP探活。
- 真实stdio MCP：独立新stdio进程绑定测试服务，仅2工具，schema合计 **513 B**。递归两份合成FITS，扫描后入库为0，按确认组提交，聚合完成2成员，项目固定引用成功，重复request_id不新增任务／素材。实测本机暖环境：扫描0.214秒、首次提交0.228秒、聚合等待0.216秒、定义读取0.006秒；其他已知调用约0.18–0.37秒。不是大规模冷环境性能结论，且固定组提交由测试明确确认，不假装真实用户已批准任意来源。
- 真实原生队列：在准确修复双服务运行合成 `EmptyImage→Data.images→Data.science` 两次，每次2个24×32 RGB float32完整成员。第二次只缓存上游IMAGE，两个Data均生成新run引用；workflow、input_bindings和成员数一致，前后未自动入库。随后选完整成员导出TIFF，回读形状24×32×3、float32及像素一致；显式保存另一个成员后库内仅增加1项，相同request_id再提交不重复入库。运行ID `92f3c974-f92d-480e-9891-d50005373ea3`／`e8d01b4c-89f6-4e2d-9f5d-966bafc9cc43`。
- 真实Siril：独立临时目录中的干净Bundle dev `8310d4da2e68b2c3434fee22ca3ee100e8eb6dae`，与已发布 `5d16fb6fc10b4ee57de428d6eba522c918b1b441` 产品树一致，Bundle0.2.0-dev.2／Siril1.4.4；未改原Bundle仓库。两份32×32浮点合成输入经Data物化与科学引用解析交真实AutoStretch，完成2输出、顺序固定、尺寸与有限像素检查通过，外部原件及Data实际输入哈希均未改变；原生v3 schema／独立aiohttp会话检查通过。该验证不等于全160节点验收，也未声称已在Feature网页安装Bundle。
- 限制：未完成用户整体验收、大规模整夜真实素材／冷缓存／长期可靠性、Linux／WSL、所有科学节点、复杂TIFF／多图XISF／RAW开发或完整工作流保存重载视觉闭环。IMAGE仅灰度／RGB浮点批次，float16固定转float32，无IMAGE下游输出；本机选择器仅Windows，不覆盖已存在文件。旧宿主缓存的扁平MCP schema需重连，新stdio已验证两域入口；不修改全局注册或默认指针。正常dev配置哈希保持原基线，main与其他Feature不变。
- 清理口径：普通推送成功且远端dev包含最终候选后，删除919e Feature workspace、私有runtime、依赖缓存、合成导入／导出与运行证据、分支及Worktree，不额外备份。Git内本节及回归源码继续保留。完整日志原在该Feature `.artifacts/reports/database-mcp`，按授权随空间删除；历史日志路径不表示仍存在。当前Git Manager及a09c Node UI Feature保留。


<a id="node-ui-bundle-integration"></a>

## 2026-10-31 Siril 节点展示、开发绑定与自动结果集成审查

- 原待审平台 `c139271125f49584313ef883c7250062e14cc85e`（基点 `711bd850b122ca64e1f147c645ba6fc0015c42ab`），Bundle `cdf952c14ae160e86add8dcc2142b16c39719936`（基点 `8310d4da2e68b2c3434fee22ca3ee100e8eb6dae`）。平台在 Feature 内整合已集成 Data/MCP 的 dev `974347a3d14379c25ab06e16b54fb8423b22629b`；Data runtime、导出及新显示控件同时保留，OpenAPI 按合并后代码生成。
- 三个独立、未继承开发聊天的只读 Reviewer 分别审查自动队列、Bundle 开发来源与序列、显示及 Data 兼容；修复后复审通过。修复：生成超时／无法启动后维持失败状态；格式声明加入实际开发依赖；单帧压缩描述与实际文件一致且不覆盖多帧成员；删除待运行自动项后按原生队列及历史核对归属；未收到 prompt 回执时标失败；快速完成不会被提交返回覆盖为失败；连接 science/images 的 Data 不强制另填素材引用。不增加切图后的全局暂停，切图只停止旧图后续提交。
- 测试夹具修复：Bundle 命令参数引号、预览有效来源字段、Vue i18n 部分 mock、真实原尺寸选项事件；已有 MCP 导入测试改为对共享测试库基线核对增量，仍验证检查不入库、仅新增两项、重复提交不重复。两项安装日志断言受 Data 迁移测试的进程日志配置影响，分进程分组执行通过，不修改产品日志行为。
- 平台 Python 最终去重汇总 **709 passed、3 skipped**（712 个用例）。Data 全组 510 passed；其他后端／接口／架构／集成组修复后按定向重测替换结果，开启原生/Siril 环境的三个用例均通过。未启用的三个用例是：原生安装编辑卸载热加载综合用例、workspace 生命周期配置采用、启动失败时排空活动导入；不计为通过。额外实际 CPU 引擎自动目标／手动上游阻断 **2 passed**。Bundle 全组 **51 passed**。UI 包 **37 文件、287 passed**；原生桥接 **21 文件、99 passed**。合成截断 FITS、既有 ORM 环、JUnit record_property 警告保留；定向实现 ESLint 无错误，测试文件不在既有 lint 配置内。
- 产品构建／预览固定为平台 `2a1b98cdb9dd26c39d79886525a567e1a7456b63`，配套 Bundle `bd55166c50fb40e40205b90b37a1459c742f9724`。bootstrap 回执 `f7db1ffb08914087be8675dc6d1b9a90`，completed/ready=true、dirty=false；构建 31.904 秒、双服务启动 12.037 秒，缓存复用总计 47.356 秒，不是冷准备。UI／原生类型检查、引擎归档和生产构建通过；网页清单及双服务实际端口为 32689／32691。后续仅更新验证文档，不改变已验证产品代码。
- 实际原生自动目标：合成 96×64 RGB FITS → Data → Auto Stretch → MTF 与 Stat 两分支；prompt `6834e2f5-56a4-4557-9c68-5362f661eac5`、`d5f34a44-bc0a-4ef2-b38e-620de1c4bdeb` 均完成。每次三个软件调用、共享上游恰好一次，Stat 分析可读取，第二次修改 targetbg 使用新运行与签名；不可覆盖计算快照含两个目标和全部签名，原件 SHA256 不变。独立 CPU fixture 还验证 Data IMAGE 两成员→真实 Siril 1.4.4，尺寸、有限数值、输入及原件哈希保持。
- 真实隔离 Chromium 页面显示工作台、素材侧栏及画布，节点库可打开，pageerror 为空；为避免用户草稿意外计算设置提交拦截，实际未发生提交。该观察只确认页面展示，不代表全部交互验收。
- 160 节点、9 一级／32 二级分类、131 自动／29 手动及稳定 UUID／端口经测试与只读核对；旧 Bundle/旧分类兼容由回归覆盖。未将本轮结果解释为 160 操作逐项科学验收。完整双语往返、所有成员/显示选项的手工组合、RBF 高采样、StarNet/外部依赖、跨重启运行恢复仍未全面验收。
- 本轮不发布新 Bundle 版本或 tag；manifest 仍为 `0.2.0-dev.2`，已发布 tag 对应 `5d16fb6fc10b4ee57de428d6eba522c918b1b441`，不得混称为候选。原安装副本不覆盖。正常 dev workspace、全局 MCP、main 和其他 Feature 保持；完整瞬时日志、合成数据与证据位于本 Feature 私有 .artifacts，按用户授权清理，不额外保留副本。Git 中本记录和回归源码继续保留。

- 实际源码绑定复验通过：只改变 `reference/formats.json` 的内容指纹会触发生成与实现缓存失效，恢复原字节后回到准确原指纹；解除绑定后旧安装 `5d16fb6fc10b4ee57de428d6eba522c918b1b441` 就绪，重新绑定后 160 节点全部可用。manifest／操作／节点／双语／适配器／程序与安装锁哈希保持，不覆盖原安装。21 个外部操作配置及可编辑安装路径未引用本 Feature；清理前还须核对远端包含候选及实际进程停止。

<a id="equipment-ui-review-fixes"></a>

## 2026-11-01 设备管理手动验收问题

用户截图发现双行文字挤压、滤镜图标语义不准确及筛选菜单观感不一致。保留现有双行布局，EquipmentCards增加专用文字容器，equipmentCompact为名称设置14px/20px、副标题12px/18px、间距2px；fields将filter的漏斗图标改为circle-dot圆形镜片示意，不推断滤镜波段。

已执行：根`pnpm typecheck`通过。未执行测试套件；CSS排版尚未完成浏览器视觉验证。固定`dev_frontend.py`入口（含指定私有runtime再次核对）报告目标workspace stopped，本环境访问32588出现套接字权限错误；未启停服务，未声称用户当前静态页面已更新。筛选Portal弹层位置需实测，单行／分组布局属于待选方案。本轮只修改上述三个UI文件与相关任务／验证记录，保留其他未提交内容；无提交、推送或合并。

### 方案A：设备类别紧凑无搜索单选

用户确认方案A后，宿主LibrarySidebarTab改注入现有SingleSelect；LibrarySelect显式保留searchable=true默认，仅设备类别关闭搜索并启用compact。紧凑样式直接作用Portal内容：padding4px、选项32px、字号12px/18px；宽180px、最小160px、最大200px且受视口限制，沿用语义颜色及右侧勾选。其他LibrarySelect继续搜索。SingleSelect内部适配Reka禁止空字符串选项的限制，公开筛选值仍为原空字符串；新增相机→全部设备→相机回归用例及Storybook密度控件，未执行测试套件。

已执行：根pnpm typecheck与宿主vue-tsc --noEmit均通过；三个原生组件／测试／story文件oxfmt完成；diff --check通过。首次pnpm格式化入口遇到本地存储访问错误，随后直接使用已安装oxfmt成功，未安装依赖。

固定dev_frontend.py在受限环境误报stopped；提升权限读取实际私有runtime后，成功以32589启动Vite并代理32588。已请求右侧打开http://localhost:32589/#/workflows（queued），不据此宣称实际渲染或视觉验证通过。未重启现有双服务、未改静态32588构建、共享dev或独立Bundle；无提交、合并或发布。


<a id="telescope-accessories-b"></a>

## 2026-11-01 望远镜内置附件方案B：Feature预览

用户确认设备仅保留camera/telescope/filter，望远镜specs维护类型化optical_accessories（稳定id、name、有限正数factor）；组合成员optical_accessory_id选择或null不使用，预设optical_accessory_selection为null继承、{accessory_id:null}不用、{accessory_id:UUID}指定。PATCH省略不修改，可显式恢复继承。后端统一派生焦距、校验附件归属、拒绝删除仍被引用的附件并提示先调整当前选择。原生焦距未知保持未知，1×附件有实际名称；导入选择快照不被通用设备快照覆盖。取消旧类别及重复有效焦距手填，不加旧库迁移。

已执行：后端改动源与受影响测试语法编译、改动源及新增用例Ruff；OpenAPI与Hey API生成、97项MCP／CLI离线生成；UI及宿主类型编译、完整前端构建、diff --check，均通过。首次生成后UI三处类型错误已修，固定构建包含重新检查。首次CLI生成在受限进程未返回，停止后在允许本地子进程的环境重新生成成功，未访问业务workspace。新pytest及UI回归用例只编写未运行，未进行综合或真实科学验收。

固定bootstrap --offline --build --start在全新optics-b workspace／runtime成功，回执03ec331ffe9a42afab965c1a7243e6d1，completed/ready，139.181秒；依赖复用，前端构建74.341秒、runtime准备16.155秒、workspace2.126秒、双服务启动45.09秒。按实际回执网页32689／服务32691（未沿用请求端口猜测地址）。随后固定dev_frontend入口启动32692热更新，代理新32689。最后仅表格CSS将四列最小宽度降至520px并移除末列固定宽度，热更新预览采用此最终源码，已通过的类型检查不重复运行。

通过新workspace本机HTTP API创建明确标注的3个示例设备、1个减焦组合及3个预设，实际响应有效焦距384.0mm（480×0.8）；记录在.artifacts/reports/optics-b/seed.json。浏览器实际观察到四列表格、384mm摘要、组合附件候选与预设继承／不用／指定选项。页面呈现不等于完整保存/删除/键盘/缩放验收；后续浏览器关闭表单时控制调用有超时，未据此宣称全交互验证通过。新预览http://localhost:32692/#/workflows标签保留。

保留原modernization-current设备、素材、数据库及运行实例；未改正常dev／默认workspace／全局MCP／独立Bundle。未提交、合并、推送或发布。


<a id="device-form-simplification-b"></a>

## 2026-11-01 设备字段精简及分区表单（方案B）

用户要求保留现有数据并同步更新。当前设备Create/Patch/Out、ORM和CRUD删除serial_number，当前TelescopeSpecs删除aperture_mm，CameraSpecs删除sensor_mode；cfa_pattern字段／枚举不改，UI统一“像素排列”。历史SnapshotBase及独立CameraSnapshotSpecs／TelescopeSnapshotSpecs保留旧事实只读解释；文件原始科学头不修改。表单统一分区栅格、标签及附件列；设备类型三项无搜索。同步修复新注册望远镜保存时附件列表未随动态字段提交的问题。

已完成生成：新初始baseline、OpenAPI／代理目录、Hey API六份生成文件、97项MCP／CLI。已执行后端源码／脚本／用例语法编译、改动源与新增用例Ruff、UI及宿主类型检查、完整前端构建、diff检查。首次构建发现EquipmentSetupManager遗留serial_number请求字段，修复后重新完整构建通过，日志.artifacts/reports/device-form-b/build.log。必要pytest和UI回归用例只编写未运行，不宣称综合验收通过。

当前数据库更新：固定入口停止准确optics-b双服务（回执caf21c7afb2d47ac8f5ab31054835e34），SQLite完整备份到.artifacts/backups/device-form-b/before-simplification.sqlite3，SHA256=3b826ade8c8faa07987ad2eb653e7b2cd6d0ab8ebdada7f0658872b32c615f71。先运行simplify_device_fields.py只读计划，再显式--apply；只清2条当前设备specs并删除serial列，无mono推导，本轮未改任何组合内设备。6个设备全部保留，所有其他表及历史JSON原文前后哈希一致。独立对照备份确认ID、名称、型号、备注、其他spec、revision与时间均不变；integrity_check=ok、foreign_key_check=0。记录在data-preservation-plan.json、data-preservation-applied.json、independent-preservation.json。脚本为显式离线整理入口，不接入启动自动转换；本轮不清空或重建用户库。

恢复：固定bootstrap用已通过构建的.artifacts/build/frontend和原workspace／runtime恢复双服务，回执a9e535cc9ae54cfba2b372aad56b1668，completed/ready，20.997秒；实际网页32689／服务32691。API只读200、设备总数6，当前响应不含退役字段（api-preview.json）。旧32692热更新仍代理同workspace。

浏览器实际呈现6个设备、分区相机表单及“像素排列”、设备类型三项无搜索、望远镜仅原生焦距及同宽附件栅格。打开未保存新建表单并切换类型、添加一行附件用于预览，未保存或新增设备；截图.artifacts/reports/device-form-b/preview.png，新预览http://127.0.0.1:32689/#/workflows。此为页面及窄范围手动呈现观察，不等于保存、删除、完整键盘或缩放回归。页面原生草稿有既有缺失节点提示，本轮未修改图、安装软件或操作真实素材。

正常dev、默认workspace、全局MCP、旧modernization-current和独立Bundle未改；保留其他未提交内容，无提交、推送、合并或发布。


<a id="single-device-setups-and-presets"></a>

## 2026-11-01 单设备组合、滤镜全显及精简预设

用户确认：相机、望远镜各0–1台，注册与组合内来源合计；多滤镜完整显示；像素排列无搜索；预设直接继承组合硬件及附件，只保留滤镜、曝光、温度、ISO／Gain＋Offset与常规模式。前端所有加入／替换／内联改类路径与后端同一写事务校验同步。删除指定滤镜后当前预设明确不使用。历史选择／参数与当前编辑契约独立，保留旧快照读写事实，不改历史JSON。

已执行：新初始baseline、OpenAPI／路由、Hey API六份生成物及97项MCP／CLI生成；UI与宿主类型检查及完整前端构建通过（.artifacts/reports/setup-preset-b/build.log）。第一次类型检查发现旧测试接口引用，更新后完整构建包含重新检查。后端源码／相关脚本／新增测试Ruff与语法编译、root两份协议／导入integration fixture语法编译、diff检查通过。新增数量／回滚／0／模式／滤镜删除／历史／离线保留用例并适配受影响旧fixture，未运行测试套件或综合验收。

数据库：在线预检无冲突；固定入口停止准确私有实例，SQLite备份.artifacts/backups/setup-preset-b/before-simplification.sqlite3，SHA256=eedd0b512a6bd02e9f2b16725a9c6fd2117a411856b696ca28787b60089b43e3。显式执行simplify_capture_presets.py --apply，删除当前预设三个退役列并收紧选择表kind=filter；0个现有预设，无参数行转换、无设备或组合删除。事务审计及独立对比21张表所有保留列数据完全相同：6设备、1组合、5成员、0预设；integrity_check=ok、FK问题0。记录data-plan-online.json、data-applied.json、backup.json、independent-preservation.json。

固定恢复最初回执d3ee744f14934857b99dde778a8bf99a后发现预设删除影响摘要Python修复落盘晚于启动约1秒；仅再次按固定入口停止／恢复私有服务加载最终冻结源码，不重复前端构建或数据更新。最终回执cc1010fa3c5b496cb495c064bd41da1a，completed/ready，26.703秒，网页32689／服务32691。API三项只读200，设备6／组合1／预设0（api-preview.json）。

浏览器实际观察：当前组合全量滤镜R/B/G可见；预设仅组合、滤镜、曝光、温度、模式与对应数值，无相机／望远镜／附件／名称前缀编辑；常规、未设置、ISO、增益均可选，未保存草稿Gain=0和Offset=0保持显示。截图filters-preview.png及preset-preview.png，预览http://127.0.0.1:32689/#/workflows。仅操作本Agent新标签内未保存草稿，没有创建预设或改变当前组合；此观察不代替保存／删除／并发／缩放／科学处理验收。

正常dev、默认workspace、全局MCP、旧modernization-current及独立Bundle未改。保留其他未提交内容，无提交、推送、合并或发布。


<a id="filter-free-text-channel"></a>

## 2026-11-01 滤镜自由文本Channel与标签

用户明确Channel只能填写、不能选择。FilterSpecs新增nullable string channel，清除首尾空白、空白为null；无枚举、选项、自动推断、强制大写或全局滤镜目录。继续使用现有specs JSON，不新增SQL表／列，初始baseline无需DDL变化。旧设备JSON与历史快照不补值，当前新字段可随真实选用资料冻结。保留原名、可选带宽、原始FITS FILTER及预设自动名称的既有语义。

filterLabels.ts统一生成组合标签、候选及只读表单预览。组合显示通道＋可选带宽，未知明确显示并附原名；组合与预设候选保留实际名字，保存设备／成员ID，不按通道去重。表格完整显示全部滤镜，保留名字提示。排序在SQL中依首个成员通道／数值带宽、完整原名摘要、组合名／ID进行，未知在后；不在Python展开全库。

已完成OpenAPI／路由、Hey API六文件和97项MCP／CLI离线生成。UI typecheck、包含宿主typecheck的完整前端构建通过（.artifacts/reports/filter-channel/build.log）。后端语法编译、改动源及新增test_filter_channels.py Ruff、diff检查通过。新用例覆盖自由文本、未知／不推断、nullable清空不丢带宽、旧快照缺省不新增字段、冻结与原名、数值带宽排序；UI用例覆盖纯文本无select、标签、同通道成员身份以及相关旧fixture。按Feature流程未执行pytest／Vitest套件，不能将编译当作这些用例通过。

数据库保护：固定入口停准确optics-b（abd6c0b3b2c24f3d8ca901c7430c3758），SQLite备份.artifacts/backups/filter-channel/before-channel.sqlite3，SHA256=b44fa505c54052ea17e0a6e821cc2bcb17f1988de9ed4c4237126f1532d1b851。无需任何转换或通道回填。恢复后独立比对21张表所有行和sqlite_master schema完全一致：6设备、1组合、5成员、0预设；integrity_check=ok、FK问题0（data-preservation.json）。API显示4片旧滤镜Channel均null，组合滤镜排序asc／desc均200（api-preview.json）；这不代替有通道样本的排序用例执行。

固定入口用已构建静态网页及原workspace／runtime恢复，回执d5a7df785e814251a5b5e1b248ec64b8，completed/ready，37.023秒；网页32689／服务32691。浏览器实际观察组合旧标签为“未指定通道 · 原名”，新建滤镜只有Channel文本框；在未保存草稿填写Channel=Ha／带宽7，标签预览为Ha 7nm，截图.artifacts/reports/filter-channel/preview.png。没有保存该示例或更改当前设备。预览http://127.0.0.1:32689/#/workflows标签保留。

必要后续验收：Channel保存／清空、注册与内联、同通道多片、排序、快照及跨入口刷新。正常dev、默认workspace、全局MCP、旧modernization-current、独立Bundle及原始科学文件未改。保留其他未提交内容，未提交、合并、推送或发布。


<a id="local-review-freeze"></a>

## 2026-11-01 累计候选本地待审封存

用户明确授权本地提交，不推送、不合并。平台现代化、设备模型／表单精简、单设备组合与精简预设、滤镜自由文本Channel为同一未提交工作区累计候选，本次整体封存，不将Channel误报为可独立挑选的小提交。独立Siril候选为Bundle 0.2.0-dev.2／Siril 1.4.4／SDK v2，分支codex/modernization，基点f4f11b34587f989fb026607b483b740ee3b74cac，本地待审824a1910773a95287e567bc369c3ed2b27e3aed3；未修改app二进制或移动开发tag。平台发布目录仍固定既有tag v0.2.0-dev.2及5d16fb6fc10b4ee57de428d6eba522c918b1b441，与开发候选不同。

本轮仅核对Git范围、既有准备回执及检查证据，执行暂存差异检查；Bundle七个测试文件仅去除多余末尾空行。没有重新运行测试套件、构建、科学处理、数据库转换或重启服务。最新Channel类型／构建及保留数据证据见上一条；更早现代化测试不代表最新设备改动已回归。

当前预览32689／服务32691使用optics-b私有空间，准备回执d5a7df785e814251a5b5e1b248ec64b8，completed/ready，37.023秒。静态网页build-manifest记录旧Base bbb6f4a9f872fc1b79defa6dddf849247b5099d6：它是本次提交前脏源码构建，不是提交后重新构建。提交整理期间平台应用源码未改，仅补交接文档；不要将清洁提交SHA冒充网页内嵌版本。回执、截图、完整构建日志和SQLite备份位于本Feature的.artifacts，受Git忽略且不会随源码提交传输。

独立审查、设备／预设／Channel新增回归、真实保存清空与快照、跨入口刷新、数字带宽排序及完整集成验收留给Manager。全部160节点、真实用户天文素材、长期热加载、Linux／WSL及seqprofile已知限制仍未据本轮宣称通过。交接后冻结两个待审版本；继续修改须重新提交并更新Brief。

封存暂存检查发现累计候选的既有空白问题：官方原文有行尾空格（按快照要求保持字节），排除官方资料后自研文件仍有行尾空格／EOF空行，完整记录`.artifacts/reports/filter-channel/review-diff-check.log`。本次不借封存改写应用源码；此检查未通过，交由Manager审查时处理，不能以此前窄范围diff通过替代全量暂存检查。


<a id="modernization-equipment-channel-integration"></a>

## 2026-11-01 现代化、设备精简与滤镜 Channel 集成验证

用户一次授权独立审查、必要测试/最小修复、通过后合并并普通推送两个仓库 dev，随后删除本 Feature 全部私有空间并归档原 Chat；不修改 main、不发布 tag、不迁移或额外备份运行数据。原平台候选 679be0cf93b5dabbd25e59ca6375777f5277b111（基点 bbb6f4a9f872fc1b79defa6dddf849247b5099d6）、Bundle 824a1910773a95287e567bc369c3ed2b27e3aed3（基点 f4f11b34587f989fb026607b483b740ee3b74cac）作为累计重构整体审查，未单独挑选 Channel。

三个独立上下文 Reviewer 只读核查设备/数据库/UI、原生画布/具体调用、Bundle 拆分，修复后复审通过。最小修复：PSF 选区调用传入 RuntimeOptions；Data 已检查成员保存完整 ResolvedAssetInput，并经 Data→Data/软件调用持久保留来源身份、成员顺序、资料 revision、capture_snapshot、value_sources 和有效校准；可空 classification 正确处理；PresetEquipmentSelection 序列化区分继承 {} 与明确禁用 {filter:null}。过时设备、多相机、名称选择器、预设 revision 及原生请求 mock 测试按最终契约修正，未删除有效业务断言；新增实际 Channel 保存、清空、设备 revision=2→3 后历史冻结、PSF 默认/自定义选区和来源冻结回归。已清理观察到的自研行尾空白/EOF 空行，官方文档和上游快照原文不改，不能将其全量 diff --check 写为通过。

准确构建/验证平台源码提交：1bd7ffc2f0c4501c52bb138315cc547c4b5ebdea（产品修复 d7bdf6524d9482b6dd21cdc9fc8b900776ad1a04）；Bundle 产品修复：83c79cf813df4a35c64dc4a1f7da932902a710cd。后续集成记录提交仅更新文档，不改变上述应用源码。Bundle 0.2.0-dev.2、Siril 1.4.4、SDK v2 配套开发源码绑定；发布目录仍为 v0.2.0-dev.2 / 5d16fb6fc10b4ee57de428d6eba522c918b1b441，不把本候选视为已发布安装版本。

### 自动检查与实际运行

- 平台完整 pytest 首轮 983 passed / 10 failed / 16 skipped（1009）；10 个失败为预设冻结期望取错分支，修正后整个快照文件 32 passed，含新增非1 revision。受影响 data/software/MCP/native/architecture 范围最终 783 passed / 1 skipped。按 JUnit classname+name，以后续定向结果覆盖同名首轮项，累计唯一 1012 项：1006 passed、6 skipped、0 unresolved failed；不是声称单次全套全绿。新增来源 7 项、最新设备 37 项、真实科学及原生测试均纳入该去重统计。
- Bundle 作者 tests 全部 58 passed；自研 UI 81 files / 526 passed；宿主桥接 24 files / 117 passed。根完整构建含 UI 与宿主类型检查通过；修复范围 Ruff 通过；OpenAPI 与 SDK 重新生成无漂移。前端依赖边界检查 289 modules / 1224 dependencies，0 violation。
- 浏览器 optics-b：9 个唯一场景全部通过（默认7项 + 显式原生队列/配置重启2项），覆盖真实手填 Channel 保存、清空不改名称与带宽、页面/画布、合成上传与原件、原生保存重载执行、配置恢复。modernization-current 配套候选：自动结果、未保存草稿执行、真实科学结果查看/所选成员入库及本机导出、原生保存/撤销/切图/内容冲突/关闭页面，共5项通过；软件安装专项未重新执行，不冒充已验证候选发布安装。
- 真实 Siril 校准、注册/堆叠/拒绝图、单帧序列分析、压缩、直接进程取消、缺少 StarNet 依赖六项通过；seqprofile 首次父退出0但捕获的 Python 子进程仍在途，平台如实返回 unknown/active=true。核对原调用进程身份并确认稍后全退出，未把原 unknown 改成 completed 或重发该调用；测试仅为该已知情形增加有界同调用查询/保留原事实。定向 seqprofile 新合成用例通过，未来同一延迟分支可记 xfail，不能当作科学成功。真实原生 interrupt→所属 Siril 进程停止、历史 interrupted、原件不变回归1项通过；真实 CPU runtime 原生 category/schema 两项通过。
- 浏览器科学 prompt 4423b76c-bc96-4511-b371-7cf5730ba557，软件 call 16757919-ed54-5dd3-8697-96f9f1b9a6c7；实际调用记录的 source_input 含固定 dataset/member 0、1，原件哈希不变、完整输出与显式保存/导出通过。
- 最终固定 bootstrap 回执 12514a06c20a4397b3a2b784169f3de1：HEAD=1bd7ffc2f0c4501c52bb138315cc547c4b5ebdea、dirty=false、completed/ready=true；总71.142秒，build52.46秒、start12.40秒（复用依赖/runtime，非冷机）。网页32689实际HTTP build-manifest为同SHA，代理健康确认optics-b与0001_baseline。另一个私有科学实例32588/32590绑定Bundle83c79cf，ready。前述浏览器验证对应产品相同源码，最终提交只额外修正测试与空白。

### 数据与尚未验证的边界

SQLite 旧备份 SHA256 b44fa505c54052ea17e0a6e821cc2bcb17f1988de9ed4c4237126f1532d1b851 已复核；当前21表 schema一致、integrity_check=ok、无外键违规。六台原设备记录及历史素材等保留。不能把旧备份与当前整库写成逐行一致：原组合 revision1→2，三个成员移除、其余成员顺序变化的 updated_at=2026-11-02T00:45:03Z，早于交接清单生成01:02:59Z及Manager测试开始01:08:29Z；本轮不恢复/覆盖交接前现状。所有设备/预设历史不变语义以本次合成回归与实际新记录验证，浏览器新增合成记录也不冒充原库未变化。

六个 pytest opt-in 未运行：Bundle 实际安装编辑移除热加载、另一独立原生草稿测试、旧平台workspace生命周期、启动失败时真实导入排空、另一独立两成员autostretch复制安装测试、官方MCP reload重连。相近浏览器/科学场景不能直接记作这些测试通过。全部160操作逐项科学正确性、用户真实素材、长期热加载/跨发布升级、Linux/WSL仍未完整验收；seqprofile延迟子进程边界保留。新0001_baseline明确不自动迁移旧数据库；正常dev实例/默认workspace/全局MCP未重启或改写，不在本次集成时升级它们。

完整瞬态日志、JUnit、浏览器记录和备份曾在本Feature .artifacts/reports/manager-integration及modernization/g7中；按用户清理授权随私有空间删除，不迁移保留副本。本节、测试及源码通过Git保留；最终远端SHA、停止/删除和原Chat归档结果以Git Manager交付报告为准。

<a id="three-step-feature-handoff"></a>

## 2026-11-01 Feature 三步交接流程文档

按用户确认，将开发流程改为三个用户动作：创建 Feature、要求整理交付、确认集成。Manager 完成准备后主动发送开发指令并交接准确 Chat/host 标识；Feature 整理本地待审提交后主动回传完整冻结 Brief，并在原 Feature Chat 展示发送结果。发送失败明确报告，回传不代表集成授权；用户确认后 Manager 才组织审查、必要验证、普通推送、私有空间清理及原 Chat 归档。根 AGENTS 的交接时序改为引用该流程，保留原有隔离和发布边界。

已核对三份用户 Prompt 及 Manager 自动发送模板，AGENTS/开发流程内24个本地文档链接目标存在，Git diff --check通过。本轮仅文档变更，不执行应用构建、测试套件或实际 Chat 派发。


<a id="file-ownership-siril-decoupling-integration"></a>

## 文件归属与平台 Siril 残留清理：Manager 集成验证（2026-11-01）

用户已一次授权独立审查、必要测试与最小修复，通过后合并及普通推送两个仓库 dev，再清理本 Feature 私有空间并归档原 Chat。最终范围是源码、生成物、安装副本与缓存归属；原 equipment-management-final 未新增设备功能。

- 平台基点 `f8c613633148e365839bcc0c1c627a7c42e266ca`，原候选 `9c2f7f244febdd99bd957a40d6013b90b59f72fd`。Manager 修复提交 `fe642105a725fda1ce3b7830980c2c374da6cccb` 仅涉及测试：合成参数恢复 [0,1] 边界、示例符合字典契约、预览 mock 保持 metadata 一致，并增加 HTTP→Python 客户端→FastMCP 非 Siril 包名/版本/assessment 保真回归；产品代码未追加修改。
- Bundle 基点 `570504cd593d923726ac76b9775a812e371fdc03`，原候选 `a6f5ad0f3eafceb44018ac4b99dc7b9f5b9c3786`，生成规范化提交 `7c75f46931a2aa52b86d06e43ab295f8fad850cf`。实际源码绑定将十份 preview JSON 的 output/max_edge 字段顺序对齐生成器，逐份解析比较语义完全一致。未改版本、程序或发布 tag。
- 两位独立上下文只读 Reviewer 分别审查公共契约/命令来源/打包及预览/缓存/前端/Bundle；原候选均无可确认新增缺陷，测试修复及生成规范化均复审通过。

自动验证：

- 初轮平台软件、数据、应用、客户端及架构 786 项：779 通过、7 失败（新测试夹具问题）；修复后软件模块完整 131 项通过，包含新增跨接口用例。按 JUnit classname/name 合并初轮与最终复测，覆盖该范围 787 项均通过。
- 补充 HTTP/MCP、打包及 MCP 发现/双语回归：36 通过、1 跳过；合计唯一平台测试 **823 通过、1 跳过，无未解决失败**。跳过的是显式 opt-in 的官方 reload/reconnect 测试，不记为通过。并非一次全项目套件运行。
- Bundle 最终提交 tests：60 通过。前端命令目录 1 项、原生 BundlePreviewWidget/bundlePreviewDisplay 9 项通过。
- 固定 bootstrap 完整构建含 UI 包和宿主类型检查通过；定向 Ruff、Git diff --check 通过。无产品代码变更后未重复接口生成。
- 标准隔离构建本地 wheel，执行 scripts/verify_distribution.py 的 check_wheel：资源完整、网页字节一致、固定引擎校验通过，旧 vendor/siril-*.json 不存在。私有目标目录 --no-deps 安装 wheel 后从该目录导入并查询 199 条通用命令通过；依赖复用本 Feature 开发环境，不冒称全新机器或独立依赖安装验收。首次 no-isolation 构建因 venv 无 setuptools 失败，改用声明后端的标准隔离构建成功，未修改依赖锁。

真实运行观察：

- 构建/服务源码 `fe642105a725fda1ce3b7830980c2c374da6cccb`；构建启动回执 `8a0fa1ccbd5a4d56b2f2f84419dee8e4`，109.875 秒（构建 69.554 秒、启动 31.443 秒）。生成规范化后按固定 stop/start 刷新成功回执 `692fb67a3eaf42a395a1a00c8f310797`，21.134 秒，completed/ready=true，平台及 Bundle dirty=false；Bundle HEAD 为 `7c75f46931a2aa52b86d06e43ab295f8fad850cf`、指纹 `6cbc788a54a1ade971b4ee3727e70607fcc073eadebca969b4442e93c37f3e1c`。重复 start 曾被运行中保护拒绝，随后正确 stop/start，未绕过保护。
- 本 Feature workspace/runtime 均为 equipment-management-final 私有路径；网页 33588、领域服务 33590。HTTP build-manifest 与上述平台 SHA 一致，浏览器实际显示素材库、空画布和运行控件。只确认页面加载，不等同功能/用户验收。
- 实际 HTTP 与 AssetClient 查询 199 条命令、assessment 字典及错版本 404 通过；真实 CLI→本 workspace 新 stdio MCP→HTTP 查询 199 条命令通过，未更改全局 MCP。
- 最后追加的验证文档不改变上述已验证应用源码；最终集成提交与远端 SHA 以 Manager 交付报告为准。

限制与未执行项：未执行真实 Siril 科学处理、十种 live 预览的全部真实交互、全项目浏览器综合验收、sdist 无 Node 重建、全新无缓存安装或跨平台验证；这些不因测试/构建通过而宣称完成。bootstrap 首次 Python 解释器/导入路径问题仍在原 Brief 的已知限制内，本轮用进程级 venv/PYTHONPATH，不扩大修复范围。平台固定发布目录仍指向 v0.2.0-dev.2 / `5d16fb6fc10b4ee57de428d6eba522c918b1b441`，本轮配套开发 Bundle 并非新发布版本。

完整临时日志曾在本 Feature `.artifacts/reports/ownership-*` 与 `.artifacts/logs/dev-prepare`；按本次授权，交付后随私有 workspace/runtime/Worktree 删除，不另行备份。已提交的本条记录和源码继续由 Git 保留。

<a id="bootstrap-first-python-import-fix"></a>

## 首次 bootstrap 的 Python 导入修复（2026-11-02）

本轮实现并验证，未提交、合并或推送。基点 `56c376ed2ca784a18acbbd2e8ba39a778533f8a7`。首次准备由系统 Python 执行，uv 创建 venv 后父进程不会自动切换；旧入口在父进程直接导入软件模块，连无 Bundle 绑定也会失败。本轮将该阶段放入固定内部脚本 `scripts/dev_bundle_sources.py`，只由已准备的本 Worktree venv Python 执行，沿用原绑定/解除/状态读取能力和 JSON 结果，接入 `bundle-sources` 阶段日志；异常和生成失败阻止后续启动。公共准备参数与全局环境配置不变。

- `tests/packaging/test_dev_prepare.py`：**34 通过**，含新增的私有 Python/参数传递、子进程失败、生成失败、非法 JSON 及无绑定/绑定/解除/已有绑定读取场景。两个真实无 pip venv 的子进程回归中，启动解释器无法导入平台，仅私有解释器安装合成软件模块，用于验证解释器隔离与传输；实际平台导入由下述完整准备验证。首次沙箱运行有一个既有 PowerShell 授权限制失败，正常执行上下文复测及最终整文件均通过，未改全局执行策略。
- 既有 `tests/modules/software/test_development_sources.py`：**6 通过**，覆盖真实绑定、恢复安装来源、生成失败恢复和缓存/指纹行为。
- 两份产品脚本 Ruff 通过；测试文件与基点比较无新增 lint 问题，保留既有 1 条 I001 和 3 条 PLW1510。差异空白检查通过。
- 在独立临时 detached Worktree 中，未预置 venv、PYTHONPATH 或虚拟环境 PATH；先确认系统 Python 无法导入 AstroPhotoFlow，然后**第一次单次**执行固定 bootstrap `--build --start`。全程未人工续跑、未补 PYTHONPATH。回执 `dd575df835b445e9b3d2c2477d4d467b`，completed/ready=true；233.776 秒，其中构建 101.295 秒、私有 runtime 22.599 秒、Bundle 子进程 0.390 秒、启动 64.406 秒。包含 UI/宿主类型检查和完整前端构建。使用既有共享包缓存，不等同无缓存机器首装。
- 临时网页 33788、领域服务 33790，浏览器实际显示素材库、画布和运行控件；构建清单记录上述基点，回执 dirty=true，使用本轮未提交脚本，不冒称已提交版本。页面加载观察不替代科学处理或完整产品验收。
- 再次普通准备（不要求重新构建/启动）回执 `c74a5c826f9e4a099e4db046711c1746`，12.370 秒，Python/前端依赖均复用，没有 build/runtime/start 阶段。验收结束通过固定入口停止临时双服务，33788/33789/33790 无监听。
- 正常 dev workspace 配置及全局 MCP 配置哈希前后不变；未修改独立 Siril Bundle、默认 workspace、Git 信任或重复启动保护。
- 本任务临时 Worktree、私有 runtime 和依赖已安全删除，链接目标及共享包缓存保留；主工作区的未提交修复和上述独立证据保留。

证据：`.artifacts/reports/bootstrap-import-tests-final.xml`、`bootstrap-import-first-run.json`、`bootstrap-import-repeat.json`、`bootstrap-first-run.log` 和 `bootstrap-import-fix/first-run-logs`。全新无缓存机器、Linux/WSL、首次安装实际 Siril Bundle 不在本轮验收中；绑定/解除的入口传输及既有软件行为分别由上述回归覆盖。


### 准备权限与 pnpm 缓存最小修复（2026-11-02）

针对76d2准备中的Git元数据写入、受限网络和共享npm缓存权限卡点：开发流程要求在已知权限边界下直接通过工具审批入口执行对应操作，不修改全局安全设置；bootstrap在工具准备前用自动关闭删除的临时文件检查所选缓存及npm日志目录，失败明确提示路径且不改用其他缓存；固定pnpm安装增加--prefer-offline，保留--offline严格离线语义。本轮只运行一次准备入口定向回归：36通过（6.39秒），PowerShell语法与差异空白检查通过；未重复完整构建/启动，未改变正常dev、全局MCP、ACL或独立Bundle，未提交/合并/推送。此前首次Python导入修复继续保留。

### 准备流程 P0：内部 browser 与前端产物复用（2026-11-02）

本轮最小改动仅更新开发流程与准备Prompt：Manager先核对已有同基点产物及前端输入/工具/环境，匹配时使用已有`--frontend-assets ... --start`，省略`--build`，无法确认才完整构建；产物继续复制到本Feature私有workspace。固定使用Codex内部browser直接打开回执`preview.web_url`，空浏览器列表不触发桌面应用枚举或Brave回退，入口不可用如实报告未确认。既有bootstrap及产物校验入口不变，未新增缓存系统。一次文档规则/相对链接及空白检查通过，未重跑构建、启动或测试套件，未测量复用后的实际耗时；修改未提交、未推送。
# 前端产物自动复用与主仓库缓存（2026-11-02）

普通构建记录输入与产物指纹；准备入口按基点、工具、输入及产物校验后复用主仓库前端，Worktree默认使用主仓库包缓存。准备与记录定向测试38项通过，Windows绝对Git指针缓存选择单项通过；普通前端构建及类型检查通过，主仓库产物指纹校验通过。真实新Worktree端到端耗时尚未验证，修改尚未提交，现有已提交dev不会自动包含本修复。
