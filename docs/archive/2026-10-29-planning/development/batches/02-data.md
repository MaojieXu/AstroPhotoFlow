> 历史设计参考（2026-10-29退出现行计划）。签名、状态和任务顺序可能过时；不能直接据此实施。当前任务见 [当前计划](../../../../development/implementation-plan.md)。

# M2任务卡：数据与资产管理

本文件落实[近期总计划](../implementation-plan.md#m2)，不另定义协议；公开DTO、签名和错误以④为准。文件路径均相对仓库根；N＝计划新增，M＝修改既有，R＝只复用。每卡先读根及所改作用域AGENTS。

所有卡当前未开工。只有总计划获确认、可识别dev基点及本卡真实前置具备后才Ready；Batch自动集成与Milestone用户验收分别记录。测试命令只在对应文件实际落位后执行，本轮未运行。工作目录/工具及共享runtime维护窗口按[验证环境](../implementation-plan.md#validation-environment)，用户操作/批准按[人工验收门](../implementation-plan.md#acceptance-gates)。维护窗口必须能用原版本入口恢复原dev；tmp_path单元测试无需停止dev。

<a id="b21"></a>

## B21：已有数据闭环回归与必要设备表单

状态：未开工；待确认总计划/前置，满足后才Ready。

1. **结果、分支和追踪**：`codex/data-library-completion`。现有导入/任务/项目固定引用/集合/设备校准/预览/回收站保持，设备输入按已确认简化。FR-01/04/05/14；NFR-02/03/04；AT-04/32近期；A21-1～3、V03/04。不是重建整个数据模块。

2. **必须读**：[FR-04](../../../../requirements/README.md#fr-04-数据素材与业务资料)、[②数据§2～4](../../architecture/data-models/02-data.md#2-现有模型及作用)、[API现有操作继续复用](../../api/platform-contracts.md#41-现有操作继续复用)。设备字段唯一看 `src/astrophotoflow/contracts/equipment.py`；指定UI `Workspace.vue`的specFields/editEquipment/buildPayload/performInlineFieldSave、`SettingsPage.vue`、`EquipmentSetupManager.vue`。还读实际数据 `imports.py`、`datasets.py`、`calibration.py`、`trash.py`及对应现有测试。

3. **前置及Ready**：B12；配置界面联调可等B13。未开工；确认基线后可先做已有回归/窄设备实现，不等首包/模型。新增运行来源、画布引用、活动输入清理仍明确交B51/B53/B54，不能提前关闭。

4. **文件级范围**：

| 文件 | 操作／职责 | 依赖 |
|---|---|---|
| `frontend/packages/astrophotoflow-ui/src/modules/data/workspace/Workspace.vue` | M：修改既有设备字段展示及创建/内联保存映射；其他数据逻辑复用 | 既有equipment API/DTO |
| `frontend/packages/astrophotoflow-ui/src/modules/data/workspace/SettingsPage.vue` | M：修改单像元输入和既有设备字段展示；不新建EquipmentForm | Workspace公开context |
| `frontend/packages/astrophotoflow-ui/src/modules/data/workspace/EquipmentSetupManager.vue` | M：修改组合内设备相同输入映射；保留组合快照不回写注册设备 | 既有context.specFields |
| `src/astrophotoflow/contracts/equipment.py` | R：复用全部字段/类型；本卡不新增schema | 既有x/y/光学说明 |
| `frontend/packages/astrophotoflow-ui/tests/modules/data/workspace/Workspace.regression.test.ts` | M：修改/新增单像元明确编辑与未编辑保旧值行为断言 | 既有组件夹具 |
| `frontend/packages/astrophotoflow-ui/tests/modules/data/workspace/SettingsOrganization.test.ts` | M：修改组合内设备相同语义断言 | 组合注册/inline夹具 |
| `tests/modules/data/test_equipment_snapshots.py` | R：复用历史快照回归 | 既有service/accept夹具 |
| `tests/modules/data/test_setups.py` | R：复用省略/null/0/组合/预设回归 | 既有TestClient |
| `tests/modules/data/test_calibration.py` | R：复用固定校准/继承/null/覆盖/清理保护 | 既有TestClient |
| `tests/modules/data/test_ingestion.py` | R：复用上传/授权目录/固定组/任务恢复 | 现有image/task夹具 |
| `tests/modules/data/test_import_pipeline.py` | R：复用hash/完整归位/快照/排空 | service/image/enqueue |
| `tests/modules/data/test_service.py` | R：复用移除/永久清理/auth/OpenAPI回归 | 现有service |
| `tests/modules/data/test_display_previews.py` | R：复用素材预览/原件/活动生成保护 | 现有service |
| `tests/browser/native-web.mjs` | R：复用现有真实导入/侧栏/设备入口验收；仅真实回归需要才修改 | 获准隔离workspace、现有tests/fixtures/native-web.png |

5. **关键函数与调用（M；现有内部函数）**：

```typescript
// frontend/packages/astrophotoflow-ui/src/modules/data/workspace/Workspace.vue
function editEquipment(row: RecordData): void
function buildPayload(): RecordData | undefined
async function performInlineFieldSave(row: RecordData, field: string, value: string | number | null): Promise<void>

// frontend/packages/astrophotoflow-ui/src/modules/data/workspace/EquipmentSetupManager.vue
async function saveSetup(): Promise<void>
```

返回类型说明现有推断结果，不要求为规划机械添加源码类型注解；文件内的现有 RecordData 继续使用，不另造公开类型。HTTP继续POST/PATCH `/api/v1/equipment`、组合与导入现有准确接口；UI经现有assetApi送既有EquipmentSetupCreate/Patch正文。调用链：现有编辑入口→本地draft/明确修改的spec字段→assetApi→既有设备/组合路由→刷新当前记录；设备接收快照不参与回写。本卡不新增②公开操作。

6. **实施顺序及行为**：先现有回归记录真实缺口→修改现有表单映射→针对设备输入/快照回归→真实按钮导入核对。相机一个像元尺寸输入：只有明确编辑时一次PATCH同时写现有pixel_size_x_um/y_um；未编辑不写两字段，旧x/y不相等也不自动抹平。创建同样把明确输入写两字段，不要求原生位深；旧值/类型保留。望远镜继续aperture/native/effective focal字段，减焦/增距附件及倍率写现有focal_adjustment_note文字（如“减焦镜0.8×”），不造倍率数值字段/自动计算；滤镜以名称和可选bandwidth为必要呈现。赤道仪/配件不成为导入必填，已有记录仍可访问。设备/组合变更不回写已接受快照；固定dv1成员不随dv2追加，校准缺键/null/0不改语义。

7. **禁止边界**：不删除模型/历史设备字段或类型，不顺带重构巨大Workspace，不新设备服务/控制器/表单抽象；不重写导入/版本/快照/回收站，不恢复旧capture_profile API；不把原生首帧预览当视频科学支持。只对实际观察故障定点修复，对应文件和断言先在本卡补证，不扩大范围。

8. **验证**：`uv run --locked --no-sync pytest tests/modules/data/test_equipment_snapshots.py tests/modules/data/test_setups.py tests/modules/data/test_calibration.py tests/modules/data/test_ingestion.py tests/modules/data/test_import_pipeline.py tests/modules/data/test_service.py tests/modules/data/test_display_previews.py -q`；`pnpm --dir frontend --filter @astrophotoflow/ui test tests/modules/data/workspace/Workspace.regression.test.ts tests/modules/data/workspace/SettingsOrganization.test.ts`。真实环境获准后`$env:APF_WEB_URL='<隔离实际地址>'`、`node tests/browser/native-web.mjs`。输入：两张合成FITS/PNG、一个reference与一个managed、dv1两成员/dv2追加、camera x/y旧值不同和gain=0、默认/覆盖/null校准。预期分项成功/跳过/失败准确、同批重复跳过/独立导入新身份，旧快照/dv1/原件hash不变；未编辑像元值零PATCH，编辑后双字段同值。记录固定批量/大小下现有导入/首次预览/峰值内存条件，不虚构性能门槛。

9. **交付证据**：`.artifacts/implementation/B21/`含已有回归与观察到的修复、设备前后请求/截图、快照/固定组/原件核对；M2自身验收使用这些事实。B22科学交接、B53运行固定、B54保护/来源仍待联调。

<a id="b22"></a>

## B22：固定科学输入与当前资料交接

状态：未开工；待确认总计划/前置，满足后才Ready。

1. **结果、分支和追踪**：`codex/data-scientific-inputs`。同进程解析固定资产/固定有序集合与明确HDU，交完整科学文件、当前纠正资料与有效校准；默认可复现和显式仅引用分别报告成本/结束观察。FR-01/04/09/14；NFR-02/04/07/08；AT-05/09/14～16/28/32近期；A22-1～3、V04/13。

2. **必须读**：[数据规则](../../../../requirements/README.md#5-数据与科学处理规则)、[②数据§3/4](../../architecture/data-models/02-data.md)、[②精确契约](../../api/platform-contracts.md#data-design)的“引用与选择”“内部解析结果”“项目公开读取”“科学输入与结束观察”及SOURCE_CLEANUP_ACTIVE段。指定源代码：`src/astrophotoflow/modules/data/projects.py`、`src/astrophotoflow/modules/data/common.py` 的 _asset_version_scope、`src/astrophotoflow/modules/data/models.py`、`src/astrophotoflow/modules/data/files.py`、`src/astrophotoflow/modules/data/ingestion.py` 的 _read_hash_and_copy、`src/astrophotoflow/modules/data/fits_preview.py` 的 inspect_fits、`src/astrophotoflow/modules/data/previews.py` 的现有清理准入检查。

3. **前置及Ready**：B21集成。未开工；无首包选择前置，FITS最小科学交接可独立证明。真实③输入格式/集合采用由B31/B33/G02后锁；本卡不自行承诺任意cube/slice/视频范围。

4. **文件级范围**：

| 文件 | 操作／职责 | 依赖 |
|---|---|---|
| `src/astrophotoflow/contracts/inputs.py` | N：新增InputReference/selection/内部ResolvedInputs/ReferenceObservation等本卡实际用纯DTO | common/assets/calibration契约 |
| `src/astrophotoflow/contracts/common.py` | M：修改仅新增一次JsonObject别名；保留StrictModel语义 | 标准库/Pydantic |
| `src/astrophotoflow/modules/data/science_inputs.py` | N：新增只读引用范围验证、科学解析/物化/结束观察；元数据冻结与文件工作分开 | core Database/Settings、data内部models/files/fits/ingestion |
| `src/astrophotoflow/modules/data/projects.py` | M：修改窄提取纯get_project，现有HTTP读取委托，响应不变 | Database/ProjectOut及现有_project_out |
| `src/astrophotoflow/modules/data/public.py` | M：修改显式导出4个新公开函数，保留全部已有及前置导出（含B12的data_busy） | science_inputs/projects |
| `src/astrophotoflow/modules/data/fits_preview.py` | R：复用inspect_fits，不另实现HDU判定或默认选取 | astropy既有模式 |
| `src/astrophotoflow/modules/data/files.py` | R：复用授权根/路径/格式识别规则，不放宽普通导入 | 现有范围约束 |
| `tests/modules/data/test_workflow_handoffs.py` | N：新增唯一②交接测试文件，后续B23/B24增量 | tmp_path真实FITS/当前资料/固定组 |
| `tests/modules/data/test_calibration.py` | R：复用缺键继承/null/覆盖/固定目标回归 | 既有service夹具 |
| `tests/architecture/test_import_boundaries.py` | M：修改实际新增contracts与公开入口边界断言 | AST检查，无运行依赖 |

5. **准确关键签名（④第12节；新增）**：

```python
def get_project(database: Database, project_id: UUID) -> ProjectOut: ...
def validate_input_references(database: Database, project_id: UUID, references: Sequence[InputReference]) -> None: ...
def resolve_inputs(database: Database, settings: Settings, request: ResolveInputsRequest, *, run_directory: Path) -> ResolvedInputs: ...
def observe_reference_inputs(settings: Settings, inputs: ResolvedInputs) -> list[ReferenceObservation]: ...
```

`get_project`实现在 `src/astrophotoflow/modules/data/projects.py`；其余在 `src/astrophotoflow/modules/data/science_inputs.py`，全部由 public.py 显式导出。编辑期 B52 add_data/set_data→validate_input_references：短只读会话核项目/固定身份/成员position/选择结构，不散列、不复制、不创建run目录、不承诺原件可读；实际运行 B53→resolve_inputs→短元数据冻结→真实文件核对/必要复制→ResolvedInputs，结束再 observe_reference_inputs。本卡不新增path型HTTP/MCP。

6. **实施顺序及行为**：先纯DTO/公开项目读→validate_input_references与resolve_inputs共用必要范围规则→scope/固定成员/当前资料冻结→清理状态准入→hash/科学选择→reproducible物化或reference观察→结束观察→测试/公开导出。按原DatasetMember.position展开，子集不重新编号，不全局去重改端口顺序。固定AssetVersion字节，资料取Asset当前parameters/classification/value_sources/revision；接收快照独立。校准按固定组默认再成员覆盖，缺键继承/null不使用，关联不冒充已经执行。准备前短事务复核LibraryEntryRemoval清理状态，SOURCE_CLEANUP_ACTIVE拒绝；文件散列/流式复制/解析不持写事务。托管固定内容不重复制；reference需固定则只在run_directory/inputs准备.part，核接受hash/前后观察，完整后归位。失败清本次未发布part，不降级reference；仅引用后观察changed/missing/unverified如实返回，不更新旧版本事实或重跑。

7. **禁止边界**：不从current_version_id替代固定请求，不用JPEG/显示默认HDU/首帧补位，不读取⑤ORM，不创建输入库/Protection表/来源库，不泄漏read_path到MCP，不为校准自动猜一整条科学流程；不自动accept外部变化；不为此新增依赖。

8. **验证**：新增文件落位后`uv run --locked --no-sync pytest tests/modules/data/test_workflow_handoffs.py tests/modules/data/test_calibration.py tests/architecture/test_import_boundaries.py -q`。夹具F-SCIENCE在新文件内建立，参考现有test_import_pipeline.py的image/service/enqueue和test_fits_preview.py的PrimaryHDU+ImageHDU写法，不新增共享fixture框架：两份小FITS含显式HDU、dv1至少两成员/dv2追加、P/Q项目、managed/reference、资料纠正及校准null覆盖。先直接调用validate_input_references核正确引用无写入/无文件工作、错项目/身份/成员position/选择失败；再核resolve成员/顺序/HDU/当前revision/接收快照/原件hash；错项目/错member_index/缺失/未确认变化/不支持选择分别拒绝。空间/复制已知失败不得降级；managed复制成本为0；仅引用前后变化不声称全程稳定。准备清理状态冲突必须在读取前拒绝。B53另证排队后不再次resolve采用新资料。

9. **交付证据**：`.artifacts/implementation/B22/`记录合成文件hash/HDU/版本/顺序、两类准备实际成本、失败码及无路径外发的投影断言；向B31/B33/B53交精确InputReference/ResolvedInputs，不发布不存在远程接口。V13真实软件部分仍待G02/G07。

<a id="b23"></a>

## B23：同一素材外部内容接纳

状态：未开工；待确认总计划/前置，满足后才Ready。

1. **结果、分支和追踪**：`codex/data-content-acceptance`。用户先看真实变化再确认，同一Asset新增内部内容版本，旧版本/固定引用/旧run不推进；断连先GET核对。FR-04/09/10/14；AT-05；A23-1～3、V04。

2. **必须读**：[FR-04](../../../../requirements/README.md#fr-04-数据素材与业务资料)、[②数据§3](../../architecture/data-models/02-data.md)、[②详设“确认外部内容变化”](../../api/platform-contracts.md)、[前端具名面](../../api/platform-contracts.md#前端具名客户端公开面)。指定源：`science_inputs.py`（B22新增）、`library.py`的get_asset/patch_asset/list_asset_versions、`ingestion.py:_refresh_fits_metadata`、`contracts/assets.py`、现有UI素材详情/错误展示。

3. **前置及Ready**：B22集成；共享HTTP文件须B13先于本卡集成。未开工；消费B13已确认core公共HTTP/errorSchema同一实现，不重复发明。Python具名client按[④准确签名](../../api/platform-contracts.md#python-clients)实现，不由执行模型另定名称或返回类型。B52才实现set_data，当前接纳UI不得声称自动改图。

4. **文件级范围**：

| 文件 | 操作／职责 | 依赖 |
|---|---|---|
| `src/astrophotoflow/contracts/assets.py` | M：修改新增AssetContentObservation/Accept，复用AssetOut | 既有StrictModel/UuidInput |
| `src/astrophotoflow/modules/data/science_inputs.py` | M：修改新增observe/accept，复用B22实际文件检查与hash规则 | data models/ingestion、B22 |
| `src/astrophotoflow/modules/data/public.py` | M：修改显式导出2函数，保留既有导出 | science_inputs |
| `src/astrophotoflow/modules/data/library.py` | M：修改新增两条准确HTTP路由，薄委托public/本域函数；保留旧资产/版本读取 | request settings/database、认证 |
| `src/astrophotoflow/modules/data/ingestion.py` | 只在确需内部共用处窄复用_refresh_fits_metadata/完整归位，不改普通导入语义 | 既有manual/file来源规则 |
| `src/astrophotoflow/interfaces/client/library.py` | M：修改Python具名内容observe/accept方法，准确签名见下 | AssetClient.request、真实DTO |
| `src/astrophotoflow/comfyui/proxy.py` | M：修改两条POST准确白名单 | 领域路由 |
| `docs/api/openapi.json` | M：修改实际生成快照 | 实际路由 |
| `frontend/packages/astrophotoflow-ui/src/modules/data/api/contracts.ts` | M：修改仅新增内容观察/接纳Zod/类型 | ④唯一DTO |
| `frontend/packages/astrophotoflow-ui/src/modules/data/api/client.ts` | M：修改新增2个具名TS方法，消费core HTTP同一实现/错误fields | 已确认FetchApi公共归属 |
| `frontend/packages/astrophotoflow-ui/src/modules/data/index.ts` | M：修改必要DTO/具名操作导出 | 实际消费者 |
| `frontend/packages/astrophotoflow-ui/src/modules/data/workspace/Workspace.vue` | M：修改素材详情操作/观察状态/明确确认/刷新同Asset | 具名client，不读原生Store |
| `frontend/packages/astrophotoflow-ui/src/modules/data/workspace/WorkspaceRecords.vue` | 仅若详情入口位于此处作按钮/观察展示，不重组列表 | Workspace现有context |
| `tests/modules/data/test_workflow_handoffs.py` | M：修改新增reference/managed接纳/冲突/旧引用事实断言 | B22实际文件夹具 |
| `tests/integration/test_client_operations.py` | M：修改新具名HTTP方法/真实错误结构 | 实际client/DTO |
| `frontend/packages/astrophotoflow-ui/tests/modules/data/api/client.test.ts` | M：修改新TS方法路径/响应/fields断言 | 现有fetch测试 |
| `tests/browser/platform-workflows.mjs` | M：修改新增内容观察/明确确认UI场景，复用唯一文件 | 获准隔离workspace |

5. **准确关键签名（④第12/10节）**：

```python
def observe_asset_content(database: Database, settings: Settings, asset_id: UUID) -> AssetContentObservation: ...
def accept_asset_content(database: Database, settings: Settings, asset_id: UUID, body: AssetContentAccept) -> AssetOut: ...
```

```python
def observe_asset_content(self, asset_id: str) -> AssetContentObservation: ...
def accept_asset_content(self, asset_id: str, body: AssetContentAccept) -> AssetOut: ...
```

后两方法在 `src/astrophotoflow/interfaces/client/library.py` 的 LibraryOperations；返回按对应DTO校验。

```typescript
observeAssetContent(assetId: string): Promise<AssetContentObservation>
acceptAssetContent(assetId: string, body: AssetContentAccept): Promise<AssetOut>
```

TS AssetOut沿现有assetSchema对应资产输出，不复制另一份字段。HTTP POST `/api/v1/library/assets/{asset_id}/content-observation`→200；POST同路径`/content-accept`→201 AssetOut。确认正文只有AssetContentAccept，不接path或confirmed:true。链：UI观察→真实当前版本/revision/hash→用户确认→accept→新版本/当前revision→刷新Asset；画布set_data另B52。

6. **实施顺序及行为**：DTO→真实观察→接纳准备/短提交→HTTP/代理/OpenAPI/具名client→UI→测试。观察开始固定base_version/revision，长读在事务外；读取中变化409，不自动重读。接纳再核同一观察hash和资料revision；reference沿原授权位置记录，managed在data/staging准备并归位新对象，不覆盖旧对象。短写再次核current/revision，插同asset_id下一内容版本、revision+1；人工资料/来源/设备及capture快照保留，非人工按现有刷新规则。旧body409 REVISION_CONFLICT、再次变化409 SOURCE_CHANGED、unchanged接纳422；断连先GET Asset/versions，不重POST。旧project/dataset/node/run固定引用零推进。

7. **禁止边界**：不新建内容审批/任务表，不增加“替换旧版本”选项，不猜路径/存储模式/旧字节可恢复，不批量更新所有引用，不把GET/打开链接当确认，不改58 MCP注册；不吞部分文件事实或承诺文件+SQLite原子回滚。

8. **验证**：新增代码后`uv run --locked --no-sync pytest tests/modules/data/test_workflow_handoffs.py tests/integration/test_client_operations.py tests/modules/data/test_service.py tests/interfaces/comfyui/test_proxy.py -q`；`pnpm --dir frontend --filter @astrophotoflow/ui test tests/modules/data/api/client.test.ts`；获准隔离实例再`node tests/browser/platform-workflows.mjs`。在F-SCIENCE的reference及managed真实修改Header/像素：观察changed，确认201且同Asset/新version/revision+1；重复旧确认409且版本数不增；观察后再变409；旧版本hash/旧组成员/旧运行夹具不变；manual修正保留。无真实⑤实现时不得伪造运行联调证据，旧run断言由B53/B61补。原件缺失/格式不支持清楚失败，path不出响应。

9. **交付证据**：`.artifacts/implementation/B23/`含两存储模式前后hash/版本/revision、409回执及UI确认截图；将“接纳不改图，set_data仅选节点”交B52，M2仅关闭自身V04子范围。

<a id="b24"></a>

## B24：完整输出检查、纯文件预览、登记及移除范围

状态：未开工；待确认总计划/前置，满足后才Ready。

1. **结果、分支和追踪**：`codex/data-output-and-protection`。检查完整文件、生成独立JPEG，复用既有Task登记用户选中的完整结果并续查同任务；提供只读的准确移除范围。FR-04/05/10/11/14，NFR-02/04/08，AT-17/18/20/32近期，A24-1～4、V16/17。M2只验②自身；画布/运行/来源/清理保护由B53/B54/B57实际接通。

2. **必须读**：[FR-10](../../../../requirements/README.md#fr-10-运行事实逐节点预览与所选结果保存)、[FR-11](../../../../requirements/README.md#fr-11-方案保存重跑与存储边界)、[②数据§5](../../architecture/data-models/02-data.md)、[②详设](../../api/platform-contracts.md#data-design)的CheckedOutput、纯文件预览、所选结果登记、普通移除与活动输入清理段。指定源代码：`src/astrophotoflow/modules/data/ingestion.py` 的 process_task/_register_asset/_create_asset_content/_read_hash_and_copy，`src/astrophotoflow/modules/data/imports.py` 的 _task_out，`src/astrophotoflow/modules/data/trash.py` 的既有scope/移除/实际unlink路径，以及下表renderer。

3. **前置及Ready**：B22集成；本卡以真实受控文件独立验证，不等首软件或⑤。用户已确认普通移除新公开链在B57一次切换，本卡只落实纯scope读取，不提前替换旧DELETE、不发布空工作流影响。B53在第一次受理运行前新增ActiveRunInputUse并接actual unlink guard；B57才实现remove_library_items、app两闭包、LibraryRemovalPreview/Apply及HTTP/client/MCP公开请求切换，不增过渡工具或兼容分支，不能以空回调通过。本卡不得把后续链标为已完成。

4. **文件级范围**：

| 文件 | 操作／职责 | 依赖 |
|---|---|---|
| `src/astrophotoflow/contracts/inputs.py` | M：补本卡真实消费的CheckedOutput/OutputRegistration/ScienceFormat；ActiveRunInputUse留B53 | B22纯契约、既有CfaPattern |
| `src/astrophotoflow/contracts/trash.py` | M：仅增加LibraryRemovalScope；Preview/Apply不放此文件 | 既有LibraryEntriesRemove；④字段唯一 |
| `src/astrophotoflow/modules/data/science_inputs.py` | M：实现check_output/render_output_preview；纯文件能力不写Preview/Asset行 | 完整文件、受控run_directory、既有renderer |
| `src/astrophotoflow/modules/data/ingestion.py` | M：实现register_output/get_output_registration；R：process_task原任务管线 | AssetTask/Item/AssetVersion、既有staging/objects/断点事实 |
| `src/astrophotoflow/modules/data/imports.py` | M：新输出任务公开序列化不得泄漏内部source_path | 实际输出任务身份；普通上传/授权目录语义保持 |
| `src/astrophotoflow/modules/data/trash.py` | M：仅提取preview_library_removal纯scope读取；现有移除写SQL/handler保持 | 同域既有selection范围解释；B57以后统一接写链 |
| `src/astrophotoflow/modules/data/public.py` | M：显式导出本卡6个函数；其中process_task为现有实现的公开复用 | 同域实现；保留已有及前卡导出 |
| `src/astrophotoflow/modules/data/fits_preview.py` | R：inspect_fits/create_preview显示算法 | FITS现有支持 |
| `src/astrophotoflow/modules/data/video_preview.py` | R：现有静态首帧renderer | 不新增视频科学执行能力 |
| `tests/modules/data/test_workflow_handoffs.py` | M：检查/纯预览/登记续查/移除scope断言 | B22真实文件夹具 |
| `tests/modules/data/test_import_pipeline.py` | M/R：归位后中断、同任务恢复、不重复资产、普通导入门禁回归 | 可暂停原任务阶段 |
| `tests/modules/data/test_service.py` | M/R：公开任务序列化、既有认证/清理/共享路径/活动Task保护 | 现有service夹具 |
| `tests/modules/data/test_display_previews.py` | R：素材显示缓存/生成保护 | 纯文件输出不改素材Preview |

5. **准确关键签名（④第12节）**：

```python
def check_output(settings: Settings, *, run_directory: Path, path: Path, expected_format: ScienceFormat) -> CheckedOutput: ...
def render_output_preview(checked: CheckedOutput, destination: Path, *, selection: ScienceSelection | None = None, max_edge: int, cfa_pattern: CfaPattern | None = None) -> None: ...
def register_output(database: Database, settings: Settings, *, task_id: UUID, output: CheckedOutput, name: str | None) -> OutputRegistration: ...
def get_output_registration(database: Database, settings: Settings, task_id: UUID) -> OutputRegistration: ...
def process_task(database: Database, settings: Settings, task_id: str, workers: tuple[ThreadPoolExecutor, ThreadPoolExecutor] | None = None) -> None: ...
def preview_library_removal(database: Database, body: LibraryEntriesRemove) -> LibraryRemovalScope: ...
```

前两函数在science_inputs.py；中间三函数在ingestion.py；最后一个在trash.py，全部经public.py。调用链：B54已核对OutputLocator/manifest→check_output→render或用户明确选择后register_output→仅created=True由装配沿共享files/previews线程池执行原process_task→get_output_registration续查。只读移除范围独立为B57的真实影响消费者准备；`remove_library_items(...)` 的完整签名继续见④，本卡不实现、不导出其新写链，也不保留一条提前新增的重复移除SQL。LibraryRemovalPreview/Apply唯一由B57在 `src/astrophotoflow/contracts/workflows.py` 落位。

6. **实施顺序及行为**：先CheckedOutput/检查→纯预览→同Task登记/查询及原任务执行→公开序列化→纯移除scope→测试。check读完整文件并核运行允许范围/格式，不修改源、登记或生成预览；⑤负责manifest身份及路径一致。render只写⑤指定JPEG并拒绝源路径，复用现有FITS/XISF/RAW/常规图/视频静态显示；省略selection沿真实selected_hdu，显式HDU不替换。不支持布局、依赖缺失与缩图失败按④分别返回，不另猜HDU。

同task_id、受控源hash/size及有效name复用同任务，created=False只查询、不调度；内容/name不同409，checked_at不参与意图比较。name=None沿既有stem/文件名，显式值沿check_name。已核对完整输出不再套普通扩展名导入门禁；解析/预览分别unsupported，用户选择不推断final。归位后中断先核现有最终文件；恢复用原interrupted/resume/retry，源缺失不删已成功托管内容。

preview_library_removal只读既有selection及固定版本范围，dataset移除不等于删除成员asset，不写移除记录、读⑤ORM或调用远程HTTP。本卡只标记现有清理preview与实际每资产unlink的准确交接位置；B53首次运行前才接同write Session的活动输入读取及复核。B57按用户确认一次替换普通移除公开链，不由本卡提前抽写helper。

7. **禁止边界**：不自动登记未选文件，不按中间/最终/扩展名限制保存；不为预览先建资产、不复制显示算法或增加view根；不新建来源表、保护表、SaveReceipt或回执历史；不改普通导入门禁、校准/活动Task/共享路径保护；不造空影响/保护回调，不承诺跨系统strict exactly-once，不因补登记重跑科学处理。

8. **验证**：本卡新增能力落位后，从仓库根执行 `uv run --locked --no-sync pytest tests/modules/data/test_workflow_handoffs.py tests/modules/data/test_import_pipeline.py tests/modules/data/test_service.py tests/modules/data/test_display_previews.py -q`。输入为受控work内两HDU FITS、常规图、other完整文件，以及损坏/缺失/越界/仅预览路径；check拒非法，render返回None并写JPEG，科学hash及Asset/Preview行数不变。分别验省略/显式HDU、不支持布局且不重试其他HDU。选一个完整输出→同Task查询/归位后中断恢复→只有一份managed内容；源与未选文件不变，metadata/preview失败不抹除content available。scope用asset/dataset/fixed-version选择核准确稳定身份/版本/data_token；直接读取前后移除记录/文件零变更。既有校准/Task/共享路径回归保持。本卡不增加verify_impact写事务测试来提前实现B57；真实run活动占用及unlink时序由B53/B54补证。

9. **完成及交付证据**：`.artifacts/implementation/B24/`记录完整文件/字节核对、JPEG、同task阶段/资产身份、只读scope结果及原清理插点。六函数相称测试及独立审查通过后才可判本卡集成完成；向B53交准确清理插点，向B54交check/render/register/query，向B57交scope及④签名。M2用户只批准②真实文件、登记和既有保护；V16/17画布、来源、活动输入及新普通移除链仍保留待M5。
