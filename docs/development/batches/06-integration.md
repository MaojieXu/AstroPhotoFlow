# M6任务卡：综合验收与交付核对

本文件落实[近期总计划M6](../implementation-plan.md#m6)，所有结果均待实际候选执行。文件路径相对仓库根，N＝计划新增，M＝修改既有，R＝只复用；前置卡创建的文件在本卡按M/R处理，不表示今天已存在。环境/工具与可恢复的共享runtime维护窗口唯一按[验证环境](../implementation-plan.md#validation-environment)；各M用户操作/反馈/批准唯一按[人工验收门](../implementation-plan.md#acceptance-gates)。本轮不运行构建、服务、软件或业务测试。

<a id="b61"></a>

## B61：首个真实双入口闭环与既有行为回归

状态：未开工；待确认总计划/前置，满足后才Ready。

1. **目标与分支**：`codex/first-loop-acceptance`。对同一五模块候选取得网页与真实外部Agent两种入口的科学闭环证据，关闭M2～M4后置联调项；不重做各模块实现。覆盖A61-1～4、V01～V18近期组合，真实软件/网页/MCP与单元证据分列。

2. **必须读**：[范围](../../requirements/README.md#2-范围与交付边界)、[真实处理](../../requirements/README.md#scenario-processing)、[结束与接续](../../requirements/README.md#scenario-continuity)、[五模块数据权威](../../architecture/data-models/README.md#authority)、[⑤运行事实](../../architecture/data-models/05-workflows.md#execution-projection)、[④验证设计](../../api/platform-contracts.md#verification-design)的V01～18及F-WORKSPACE/F-SCIENCE/F-RUN/F-CONTROL。具体数据/运行/取消/原生/协议行为按④第12～16节及本卡复用的前置任务卡，不另定义失败码或签名。

3. **前置与Ready阻塞**：B57已集成；B11～B57相关自动验证、独立审查和G01～G10证据齐备；M1～M4自身能力分别批准（M3/M4同轮分别记录），M5已获用户人工批准。B31准确软件/版本/来源/操作/许可/输入与科学预期、B56模型/后端/固定查询规模已锁定。验证环境已获准且原dev可按原版本入口恢复；未知占用、原型失败、关键选择未定不得以mock/skip/空回调代替。B62依本卡技术集成，不要求M6先作最终批准。

4. **文件与职责/依赖**：

| 文件 | 操作与责任 | 依赖 |
|---|---|---|
| `tests/integration/test_platform_workflow.py` | R/M：B12起逐卡落位；复用真实集成，仅新接线失败定点补回归 | 首包/引擎、关页观察、取消/补登记/重启；不复制58协议全量断言 |
| `tests/browser/platform-workflows.mjs` | R/M：B13起唯一跨模块浏览器脚本；复用/修正真实目标、运行、预览、保存、接管/交回 | 同候选QA实际地址与测试数据 |
| `tests/integration/test_cli_mcp_protocol.py` | R：B57已完成真实stdio/三入口/58/schema/映射/error/ImageContent断言主责 | 同候选MCP进程环境 |
| `tests/browser/native-web.mjs` | R：B51已同步schema常量的原生/素材基础回归 | 不能代替真实科学运行 |
| `tests/modules/data/test_ingestion.py` | R：受影响的上传/目录/任务回归 | 既有测试夹具 |
| `tests/modules/data/test_import_pipeline.py` | R：完整归位/快照/恢复回归 | 同上 |
| `tests/modules/data/test_equipment_snapshots.py` | R：历史设备接收快照 | 同上 |
| `tests/modules/data/test_calibration.py` | R：固定校准/继承/null/覆盖 | 同上 |
| `tests/modules/data/test_service.py` | R：认证/公开移除/回收站/保护 | B57真实公开链与既有保护 |
| `tests/modules/data/test_display_previews.py` | R：素材显示/原件/活动生成保护 | 不冒运行预览证据 |
| `docs/development/test-matrix.md` | M：记录本候选各层结果与未通过项 | B61技术结果与M6最终批准分开 |
| `.artifacts/implementation/B61/` | N：普通运行证据目录 | 候选/差异/版本/输入/观察/限制，无新证据框架 |

实际集成缺陷回到原Batch已经列明的源文件做最小修复，不预设新增业务文件；先记录失败/归属，禁止借综合验收扩大软件、视频或完整恢复范围。

5. **函数与调用链**：本卡无新增公开函数/类、DTO或辅助框架。复用已落位的准确签名，必要时只修观察到的集成错误。链为：网页或真实MCP客户端→共享HTTP/本机控制→原生薄桥接/⑤→②③④公开入口→原生引擎真实调用→完整输出/自动预览→用户选择→②登记。未知先查同run/prompt/call/task，不重新执行来掩盖未知。

6. **实施顺序**：核对候选/未提交差异、B57/M5批准和G证据→按总计划验证环境准备W1/W2/首包→执行下表同候选真实集成→用户执行M6操作→分类反馈并最小纠正→仅复验受影响项→独立审查→交B62。保留实际归档digest、marker、加载token、版本和输入hash；候选环境不能重指原dev editable解释器或迁移正常dev库。原版本恢复条件不足时先阻塞窗口，不能先普通init覆盖。

7. **禁止边界**：不以CPU演示/mock或历史发行代真实科学软件；不使用正常dev素材作为写入目标；不以重跑、删除history或自动重试抹除未知/部分事实；不新建协议断言框架、综合数据测试副本或业务SQL；未批准不标M6完成，不自动提交/推送/合并/发布。

8. **精确验证**：未来前置文件真实落位后，项目根PowerShell，按总计划固定环境执行：

```powershell
uv run --locked --no-sync pytest tests/integration/test_platform_workflow.py tests/integration/test_cli_mcp_protocol.py -q
node tests/browser/platform-workflows.mjs
pnpm test:browser
```

`APF_WEB_URL`来自本次真实start回执；MCP只选同一QA配置。直接受本候选影响且尚无同候选证据的数据行为才补：

```powershell
uv run --locked --no-sync pytest tests/modules/data/test_ingestion.py tests/modules/data/test_import_pipeline.py tests/modules/data/test_equipment_snapshots.py tests/modules/data/test_calibration.py tests/modules/data/test_service.py tests/modules/data/test_display_previews.py -q
```

| 输入/操作 | 可判定预期 |
|---|---|
| B31准确完整科学输入、版本/HDU/有序范围，网页一遍、真实外部客户端一遍 | 固定素材→标准节点→唯一原生图→首软件真实处理→多轮自动预览→只选一个完整输出入库；原件hash不变，图/输入/参数/软件/输出可核（A61-1，V04/07/09/12/13/16/17/18） |
| A/B同node ID；A运行切B；手改撤权、新客户端读取、明确交回 | 旧目标新写/新提交暂停，已受理继续；A结果归A不抢B视图；读/重连不复权，手改后Agent安静（A61-2，V10/11/16/18） |
| B53/B54既有可复现屏障：保存失败、提交回包丢失、同run重复/异内容、history清除/重启 | 保存失败零投递；同候选只查既有事实、异内容409；无证据unknown、不重提，SQLite必要事实保留（V12/14） |
| A执行B排队只取消B；送达但仍运行/未知→实际退出；完整结果登记归位后断连 | 不误停A，请求/移队/实际停止独立；unknown仍占用；固定OutputLocator/task续查补关联，不多资产/不重算（V15/17） |
| dv2追加、纠正资料、设备快照、校准、预览/回收站、运行期间更新/重启 | 既有行为保持、dv1不扩；首次在途即清理保护；busy/unknown拒维护不延后（A61-3，V02/03/04/06/08/17） |
| QA启动/停止及窗口恢复 | 不改默认指针/全局MCP/正常dev数据；只停测试实例；用原版本入口及原环境/资源/配置恢复原dev（A61-4，V01/02） |

已有同候选B53/B54故障证据直接引用，只有新接线/代码/失败才扩大复测。各M具体用户步骤和批准记录见总计划人工验收门；真实操作不由上述自动断言代签。

9. **完成与交付证据**：近期组合均有实际结果、保护及原型真证据，相关自动验证和独立审查通过，后置项关闭或明确阻塞；阻塞闭环项未关不能声称B61通过。移交B62的 `.artifacts/implementation/B61/` 含候选+脏差异、命令/exitcode、用户反馈与修复、环境版本/hash、workflow/run/prompt/call/OutputLocator/task/asset、科学检查/截图/日志及限制。B61技术集成通过仍不等于M6最终批准。

<a id="b62"></a>

## B62：构建资源、仓库外安装与交付状态核对

状态：未开工；待确认总计划/前置，满足后才Ready。

1. **目标与分支**：`codex/first-loop-delivery-check`。使B61真实业务候选进入既有构建/发行资源链，验证仓库外wheel安装与无Node的sdist重建，回写同候选真实状态。覆盖A62-1～3、E-BOUNDARY/E-DELIVERY；完整Windows升级恢复、其他软件及Linux/WSL不前移。

2. **必须读**：[FR-14](../../requirements/README.md#fr-14-本地安全权限与隐私)、[FR-15](../../requirements/README.md#fr-15-可重复交付与维护)、[①资源数据](../../architecture/data-models/01-foundation.md#resources)、[④文件规划](../../api/platform-contracts.md#file-design)、[原生资源与双解释器](../../api/platform-contracts.md#native-design)、[验证设计](../../api/platform-contracts.md#verification-design)、[开发/构建流程](../README.md)。源码限定下表现有脚本/测试；按实际新增资源修缺口，不重建发行机制。

3. **前置与Ready阻塞**：B61技术集成/独立审查通过；B57及M5批准对本候选仍有效，所需文件和工具真实可用。B62不以尚未完成的M6最终批准阻塞自身；B62通过后才呈M6完整候选给用户。构建/安装验证及恢复环境按总计划，原dev不能用候选源码/0010入口勉强恢复。

4. **文件与职责/依赖**：

| 文件 | 操作与责任 | 依赖/边界 |
|---|---|---|
| `scripts/build_release.py` | R/M：既有锁定安装→根pnpm build→wheel/sdist；仅真实打包缺陷修正 | 不增加发行脚本 |
| `scripts/build_engine.py` | R/M：既有内容归档/发布，只有实际资源遗漏才修 | 真实vendor归档与manifest，不手写假hash |
| `scripts/verify_distribution.py` | R/M：仓库外安装及无Node重建，必要资源断言增量 | 既有smoke流程 |
| `tests/packaging/test_layout.py` | R：B51已同步0010及迁移资源 | 历史迁移不变 |
| `tests/packaging/test_engine_build.py` | R：同/变化内容发布回归 | 实际归档与散列 |
| `tests/architecture/test_import_boundaries.py` | R：实际模块/公开入口边界 | 不能只用旧data规则代表③④⑤ |
| `frontend/.dependency-cruiser.json` | R：UI/宿主依赖方向 | core不导业务、UI不反导宿主 |
| `frontend/src/platform/astrophotoflow/workflowBridge.test.ts` | R：前置B32/B51～B55已落位P-HOST | 精确命令见下 |
| `docs/api/openapi.json` | R/M：实际生成快照与B57接口核对 | `scripts/export_openapi.py`实际生成 |
| `src/astrophotoflow/client.py` | R/M：B57具名客户端一致性；只修真实差异 | 不加任意URL调用 |
| `src/astrophotoflow/comfyui/proxy.py` | R/M：准确允许路由/认证与错误保持 | 真实HTTP同源链 |
| `.agents/skills/astrophotoflow-library/SKILL.md` | R/M：B57后的三入口与客户端刷新说明核对 | 操作参考文件从真实Skill链接读取，不新造参考文档 |
| `docs/development/test-matrix.md`、`docs/development/current-context.md`、`docs/development/README.md`、`docs/development/workbench.md`、`docs/api/README.md`、`README.md` | M：按实际候选最小回写已有行为/命令/限制 | 不复制A/V表或增加交付总册 |
| `.artifacts/build/frontend/`、`.artifacts/build/engine/`、`.artifacts/build/python/`、`.artifacts/dist/` | R：使用现有输出位置 | 不写frontend/build或正常workspace |
| `.artifacts/implementation/B62/` | N：普通构建/核对证据 | 链接既有verify报告，不建证据schema |

5. **关键函数与调用链（R）**：现有准确签名为 `scripts/build_release.py::main() -> None`、`scripts/verify_distribution.py::check_wheel(path: Path) -> None`、`run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None` 和 `main() -> None`。`scripts/build_engine.py::main()`保持现有推断返回，不为规划补无意义函数。链：build_release→锁定前端/根build→引擎归档与网页→Python wheel/sdist→verify_distribution→两份wheel仓库外安装/入口/迁移/资源+无Node重建。本卡不新增函数/通用runner；业务修复回原Batch职责路径并复验B61相关行为。

6. **实施顺序**：固定B61候选/差异并核资源、0010、实际白名单包/薄适配位置→相关边界/打包/原生/UI回归→既有release脚本一次→verify脚本→核OpenAPI/代理/具名客户端/Skill/三入口/58/ImageContent→回写实际状态→必要修复/相关复验/独立审查→呈M6最终用户批准。release已含生产构建和类型检查，不先无条件重复同样build/typecheck。

7. **禁止边界**：不以单元通过代替仓库外安装；不手造OpenAPI、假散列或缺产物skip；不修改历史迁移、令牌、业务数据或正常workspace；不另建smoke/发行框架；不宣称未验软件/视频/完整升级恢复/Linux/WSL支持。生产发布、提交、推送及合并须具体授权，不由本卡自动执行。

8. **精确验证**：未来前置与产物真实可用后，项目根PowerShell按固定工具环境执行：

```powershell
uv run --locked --no-sync pytest tests/packaging/test_layout.py tests/packaging/test_engine_build.py -q
uv run --locked --no-sync pnpm check:boundaries
pnpm test
pnpm --dir frontend test:unit src/platform/astrophotoflow/workflowBridge.test.ts src/platform/workflow/persistence/composables/useWorkflowAutoSave.test.ts src/platform/workflow/management/stores/workflowStore.test.ts src/scripts/changeTracker.test.ts src/utils/executionUtil.test.ts src/services/litegraphService.lateRegistration.test.ts src/stores/nodeOutputStore.workflowSwitch.test.ts
uv run --locked --no-sync python scripts/build_release.py
uv run --locked --no-sync python scripts/verify_distribution.py
```

上述精确原生文件均已存在，P-HOST为前置后才存在；原生路径按命令完整定位。若同候选已有有效覆盖可引用，只有变化/失败才复测。输入为锁定源候选、准确平台节点包/薄适配/网页/0010及真实wheel/sdist，预期：历史迁移保持、必要资源入包且不含令牌/环境/数据；相同内容不重发布，变化内容manifest散列匹配；源码外正确导入/入口/迁移/资源；sdist带预构建网页，移除Node PATH后重建wheel并再次安装smoke。记录两份wheel与sdist散列及现有verify报告。接口有变化时追加 `uv run --locked --no-sync pytest tests/integration/test_cli_mcp_protocol.py tests/integration/test_client_operations.py tests/interfaces/comfyui/test_proxy.py -q`，预期精确三工具、58数据业务、HTTP/CLI/错误/ImageContent语义一致、无旧别名。

9. **完成与交付证据**：`.artifacts/implementation/B62/`包含同候选B61业务结果链接、构建日志、wheel/sdist与重建wheel SHA、资源清单、verify报告、源码外/无Node事实、文档回写差异、限制及独立审查。B62技术通过后用户依据总计划M6操作和完整证据明确批准；记录原话/日期/候选及反馈闭环，未获批准保持M6待验收。


<a id="manual-acceptance"></a>

## M1～M6人工操作清单

2026-10-28：M1已由用户在当前聊天确认通过并授权合入dev；最终网页、配置与重启证据见[验证矩阵](../test-matrix.md#m1-foundation)。下表M1操作保留核对用途，M2～M6仍待执行与批准；③⑤后置繁忙联调不因此提前通过。

环境按[总计划验证流程](../implementation-plan.md#validation-environment)，放行按[双状态与批准门](../implementation-plan.md#acceptance-gates)。这是未来操作表，全部实际结果／批准均待填写。模块自身能力与后置联调分别核对；验证人员执行用例的证据不能代替用户实际查看和批准，也不能冒充尚未存在的操作界面。

| 阶段/环境与入口 | 具体操作（按序执行） | 用户重点观察与通过条件 | 实际结果、失败证据和用户批准待填 |
|---|---|---|---|
| M1 / QA W1/W2；CLI和新增工作台设置UI。B11～B13、G01已自动/独立核对。 | ①W2在线，测试监听器占用W1请求端口；start W1并读实际URL。②重复start，看实例复用。③设置修改并发，查看保存/有效值；用旧token重复保存看冲突。④导入或显示预览占用时请求重启；空闲再显式重启。⑤stop后用本机CLI重启，核实际服务退出/恢复。`restart`已在M1候选实现，使用候选CLI与明确的QA workspace执行。 | 两服务健康/地址真实，W2不受影响；保存不换连接，重启才用新值；繁忙/unknown原因可见、无延后自动重启；停止实际排空。③⑤繁忙留M5联调。 | 实际待执行；保存CLI回执/exitcode、实际端口/health、配置去密差异、设置截图及两服务日志。失败按同监听器/任务复现。用户批准待填，前置/候选/日期需对应。 |
| M2 / QA W1素材库、导入、设备/校准/回收站、内容确认UI；M1所需基础已集成，B21～B24通过。 | ①用合成PNG/完整FITS单/批上传与授权目录导入；看成功/跳过/失败，独立批次再导入。②P固定dv1两成员后追加dv2。③修正资料、preset和校准inherit/null/override，查看旧接收快照。④替换reference字节，先观察后真实确认并查看新内部版本。⑤验证人员按B24卡执行完整输出检查／独立缩图／选择登记用例，用户核对完整文件、task和库内结果；正式运行结果保存UI待B54。⑥在现有QA回收站检查／移除／恢复不涉及工作流的新素材。 | 状态分开、原件hash保持；dv1成员/顺序及旧快照不改；单像元表单按既有x/y写入且不编辑不改旧值；内容接纳同Asset新版本，其他引用不隐式更新；预览不入库，仅完整所选结果登记。运行/画布保护后置M5，不用M2批准代签。 | 实际待执行；task/asset/version/dataset/revision、hash、内容观察/确认请求和409响应、清理preview、截图/日志。批准②自身能力待填，跨模块项保持待联调。 |
| M3 / 与M4同轮；QA软件页、真实包/许可、真实③调用；B31→B41→B32→B33→B42→B43集成，G02～G04通过。 | ①读准确安装计划及未就绪原因，先确认请求202没有安装。②无活动图也点真实软件页确认；用户直接输入许可。③核版本/路径/实际准备。④验证人员按B33真实公开函数用例处理完整单文件和两个有序成员，用户核对实际日志／产物。⑤验证人员发定向取消，用户核对真实停止观察；本轮不新增临时软件执行HTTP／MCP／UI按钮。配套节点可用一并核B42。 | 请求/确认/安装/节点加载分开；敏感值不回显；真实HDU/顺序和输出科学预期一致；百分比未知不造，退出/部分文件/真实停止不混。已有图更新/卸载交M5/B55。 | 实际待执行；plan UUID、真连接/按钮去密记录、版本/命令/日志、输入输出hash/参考值、call/进程停止观察和已证实限制。M3单独批准待填；不得要求M3先批准才让B41/B42完成。 |
| M4 / 与M3同轮；QA节点库/编辑器/原生画布；B41～B43/G04通过。 | ①以M3首操作的配套定义为起点，编辑名称／端口／常用及高级参数，保存独立custom。②按已证实流程冷启动／刷新后加入两张普通原生测试图；正式跨项目关联待B51。③看缺软件/许可/缺类/旧类/unknown原因。④验证人员执行B41／B43端口差异用例，用户核对重排／改名／类型／删／增的预期；不操作尚待B55的跨图确认更新入口。 | 保存/实际加载/ready可辨，registry token与JSON匹配；添加不启动处理；无测试也能保存/用，旧测试不是新内容通过；自建全部新默认和package变化默认政策分开。此轮看差异，真实图更新/在途保护B55、显式测试B53补齐。 | 实际待执行；JSON/token、实际registry/runtime、节点库/编辑器截图、失败原因/刷新条件。M4单独批准待填；M3/M4分别记录。 |
| M5 / QA项目图/运行/预览/软件维护+真实外部客户端；5A→5B→5C，G05～G10通过，M1～M4自身已批准。 | ①新图选P保存，rename/saveas/reopen，留独立方案。②P.A/Q.B同node ID，目标页交给Agent局部改图/撤销，切B、手改接管、新客户端读、明确交回。③手动按钮/快捷键/auto及Agent各触发受控入口；保存失败/异步参数/坏targets由隔离可复现case展示。④首外软连续同参重算与两轮调参、两个图像输出；关页继续，再看A后台结果不抢B。⑤A执行B排队时只取消B；核请求和真实停止。⑥选一个完整结果入库并看断连续查；软件／节点维护计划覆盖一开一闭两图；B57公共移除先看真实图影响，再确认并检查缺失节点。⑦搜索/直达/模型不可用降级、三入口/换客户端接续。 | 正确目标/草稿同步/控制真实；手改后安静，读/重连不复权；before/转换/save各一次，保存失败零投递；真实范围/重算/固定输入保护；A/B预览不串，预览只是预览，所选完整结果单次登记；unknown仍忙、维护不改在途/历史；真实客户端体验成立。 | 实际待执行；workflow/page/run/prompt/call/OutputLocator/task/asset、原件hash/预览路径、控制/保存/取消实际事实、维护逐图结果、截图/浏览器错误/领域与引擎日志。用户M5批准待填；未批准不进入依赖其范围的B61。 |
| M6 / QA首闭环与交付候选；B57集成+M5已人工批准→B61→B62。 | ①用户分别亲自用网页/真实Agent走选材→节点/图→真实处理→看多轮预览→选完整结果保存，检查科学结果及来源。②复现B61观察到的问题，检查固定组/设备/校准/预览/回收站回归与真实忙闲。③B62运行生产构建、wheel/sdist仓库外安装/无Node重建，用户核对报告/限制。④如有修复，复验受影响场景和独立审查后呈最终候选。 | 同一候选双入口真实，首软件科学效果/引用/来源可核；保护后置项关闭，不把mock/CPU/历史发行当新证据；产物实际资源/版本对应候选，未验其他软件/视频/完整升级恢复/Linux/WSL仍明确未验。 | 实际待执行；B61/B62候选/差异、命令/exitcode/日志、版本/hash/运行及资产标识、实际用户观察、verify报告与wheel/sdist SHA。M6最终批准仅B62通过后填写；任何阻塞未关或用户未批均保持待验收。 |


反馈按总计划分类：Bug修复回归、需求偏离纠正、需求变更先确认；保留原失败与候选，受影响范围复验后才请用户批准。
