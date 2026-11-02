> 历史设计参考（2026-10-29退出现行计划）。签名、状态和任务顺序可能过时；不能直接据此实施。当前任务见 [当前计划](../../../../development/implementation-plan.md)。

# M5任务卡：工作流、执行与Agent交互

本文件落实[近期总计划M5](../implementation-plan.md#m5)。N＝本卡新增，M＝修改既有或前置卡创建的文件，R＝只复用，D＝删除旧注册；路径均相对仓库根。当前新增功能均未实施，先读根与所改作用域AGENTS；公开DTO/错误/协议唯一按④，不复制字段表。共享HTTP复用B13同一实现，业务只经公开入口，原生单例只在宿主。

各卡状态统一未开工；总计划确认、可识别dev基点及真实前置满足后才Ready。B53/B54内部小步只作实施/审查顺序，整卡通过后集成，不增加Batch或分支。Batch集成与用户M5批准分别记录；环境/工具及原dev可恢复的共享runtime维护窗口按[验证环境](../implementation-plan.md#validation-environment)，用户操作/反馈/批准按[人工验收门](../implementation-plan.md#acceptance-gates)。tmp_path单元无需停dev，本轮不操作环境。

<a id="b51"></a>

## B51 — 原生项目图与最终文件联动

状态：未开工；待确认总计划/前置，满足后才Ready。

**1. 目标与可观察结果。** 分支`codex/workflow-native-files`。项目图列表/读取指向唯一原生JSON；新图选项目并实际保存后关联，save/rename/saveas/delete均经过最终userdata guard；另存独立ID，删除只清关联和专属预览，运行/已存素材保留。覆盖A51-1～4 / V09 / G05。

**2. 必读依据。** [FR-01/02、场景3.2](../../../../requirements/README.md#scenario-canvas)、[⑤数据设计](../../architecture/data-models/05-workflows.md)、[模型与public](../../api/platform-contracts.md#workflows-design)、[实际文件钩子/首次关联](../../api/platform-contracts.md#native-design)。重点读④“models.py与保存事实”“public.py完整签名”“托管图实际文件guard”“首次保存、项目关联与交给Agent”。R：[原生保存](../../../../../frontend/src/platform/workflow/core/services/workflowService.ts)、[Store另存](../../../../../frontend/src/platform/workflow/management/stores/workflowStore.ts)、[ComfyWorkflow](../../../../../frontend/src/platform/workflow/management/stores/comfyWorkflow.ts)、[UserFile](../../../../../frontend/src/stores/userFileStore.ts)。

**3. 前置。** B13/B21/B42集成，复用B32已验证的同socket定向回包；M3/M4交叉能力同轮分别验收。运行期依赖只为现有两个服务/SQLite/本机原生文件；此卡不要求③科学处理。新图首次未托管保存不得先要求不存在的SQL控制token。

**4. 文件表。**

| 路径 | N/M/R与职责 | 依赖/边界 |
|---|---|---|
| `src/astrophotoflow/contracts/workflows.py` | M（B32已创建）：加入当前Workflow/文件permit/首次关联类型 | 仅contracts，单向引用③④组合类型；不复制原生图schema |
| `src/astrophotoflow/modules/workflows/models.py` | N：Workflow、WorkflowRun、WorkflowPreview三个已定模型 | core Base；无第二当前图字段/历史编辑表 |
| `src/astrophotoflow/core/database/alembic/env.py` | M：显式装配⑤模型元数据 | core导入业务的既定唯一例外 |
| `src/astrophotoflow/core/database/alembic/versions/0010_workflow_records.py` | N：三个模型迁移 | down_revision为0009，不改旧迁移 |
| `src/astrophotoflow/core/database/schema.py` | M：SCHEMA_REVISION改为0010 | 对等版本返回与精确比较必须同迁移目标同步 |
| `src/astrophotoflow/modules/workflows/public.py`、`src/astrophotoflow/modules/workflows/routes.py` | N：list/get、关联/文件准入业务；薄公开/内部路由适配 | data.public.get_project；文件bytes读取按原生userdata范围，路由不写ORM |
| `src/astrophotoflow/interfaces/http/app.py`、`src/astrophotoflow/interfaces/comfyui.py`、`src/astrophotoflow/comfyui/proxy.py` | M：装配pages/permits和page read、file-check/finished、有限代理 | 前者不写⑤ORM；适配不承载业务；双解释器局部依赖边界 |
| `engine/ComfyUI/app/user_manager.py`、`frontend/src/scripts/api.ts` | M：实际save/move/delete前后钩子及每请求token | 原生临时文件/os.replace、非托管userdata行为保留 |
| `frontend/src/platform/astrophotoflow/software/confirmation.ts`、`frontend/src/platform/astrophotoflow/sidebar/NativeShell.vue` | M：先save/关联，安装/卸载同一薄桥接 | Store/画布操作仅此宿主；真实handoff由B52完整加入 |
| `frontend/src/platform/workflow/core/services/workflowService.ts`、`frontend/src/platform/workflow/management/stores/workflowStore.ts` | M：保存结果和首次关联联动 | 保留原提示/草稿/UUID/saveas，不另建文件操作 |
| `src/astrophotoflow/interfaces/client/workflows.py` | N：list_workflows/get_workflow具名HTTP方法 | 由根`src/astrophotoflow/client.py`（M）组合，无SQL |
| `frontend/packages/astrophotoflow-ui/src/modules/workflows/WorkflowPanel.vue`、`frontend/packages/astrophotoflow-ui/src/modules/workflows/api/contracts.ts`、`frontend/packages/astrophotoflow-ui/src/modules/workflows/api/client.ts`、`frontend/packages/astrophotoflow-ui/src/modules/workflows/index.ts` | N：项目图列表/读取/保存状态，Zod/具名client/组件公开 | 原生JSON只校验对象；首次保存/项目选择由宿主回调组合 |
| `frontend/packages/astrophotoflow-ui/src/index.ts` | M：导出上述真实入口 | 不从包外导入内部src |
| `frontend/packages/astrophotoflow-ui/src/core/client.ts` | R（B13窄移后）：共用FetchApi/错误/请求能力 | 不再反向依赖data客户端或新造一层 |
| `tests/modules/workflows/test_service.py` | N：真实SQLite/关联/最终文件事实 | 所属⑤可查本模块ORM |
| `tests/modules/data/test_service.py`、`tests/modules/data/test_domain_foundation.py`、`tests/packaging/test_layout.py`、`tests/architecture/test_import_boundaries.py` | M：升级/metadata/资源精确列表和边界回归 | 不新增重复schema测试文件；test_layout精确列表加入0010 |
| `frontend/src/platform/astrophotoflow/workflowBridge.test.ts`、`tests/browser/platform-workflows.mjs` | M（B32创建后）：文件操作/首次保存真实链 | 单一P-HOST/P-BROWSER，后续增量 |
| `tests/browser/native-web.mjs` | M：将实际迁移版本断言同步到0010并保持原生/数据基础流程 | 使用同一获准隔离候选，不迁移正常dev库 |
| `docs/api/openapi.json`、`docs/api/README.md` | M：实际新增HTTP与生成快照 | 不手写未来API进“已实现”说明 |

**5. 关键完整签名与调用链。** 均为拟实现契约：

```python
PageCall = Callable[[PageCommand], Awaitable[PageResult]]
def list_workflows(database: Database, project_id: UUID, *, limit: int = 50, offset: int = 0) -> WorkflowPage: ...
async def get_workflow(database: Database, settings: Settings, workflow_id: UUID, *, page: PageObservation | None = None, page_command: PageCall | None = None) -> WorkflowDetail: ...
async def associate_saved_workflow(database: Database, settings: Settings, body: AssociateSavedWorkflow, page_command: PageCall, *, page: PageObservation) -> AssociateWorkflowResult: ...
def authorize_file_write(database: Database, settings: Settings, body: FileWriteRequest, *, pages: dict[UUID, PageObservation], permits: dict[str, FileWritePermit]) -> FileWritePermit: ...
def check_file_write(database: Database, settings: Settings, body: NativeFileCheck, *, pages: dict[UUID, PageObservation], permits: dict[str, FileWritePermit]) -> FileWritePermit | None: ...
def finish_file_write(database: Database, settings: Settings, body: NativeFileFinished, *, permits: dict[str, FileWritePermit]) -> FileWriteResult: ...
async def guard_file(request: "Request", operation: Literal["save", "move", "delete"], path: str, destination: str | None, content: bytes | None) -> FileWritePermit | None: ...
async def file_finished(permit: FileWritePermit, result: NativeFileResult) -> FileWriteResult: ...
```

```typescript
export function registerNativeFileHooks(
  before: (operation: 'save' | 'move' | 'delete', path: string, destination?: string, content?: string) => Promise<string | undefined>,
  after: (writeToken: string | undefined, result: FileWriteResult) => Promise<void>
): () => void
```

公开面完整映射：GET `/projects/{project_id}/workflows`→list_workflows；GET `/workflows/{workflow_id}`→get_workflow；内部associate_workflow→associate_saved_workflow；authorize_file→authorize_file_write；内部file-check/finished→同名领域函数。Python与TS客户端只落本卡下面的两个真实GET；不提前暴露edit/run。保存链复用实际`saveWorkflow(workflow: ComfyWorkflow): Promise<boolean>`→prepareForSave→Store→ComfyWorkflow.save→UserFile.save→storeUserData。另存复用`saveAs(existingWorkflow: ComfyWorkflow, path: string): ComfyWorkflow`生成新UUID。首次关联先真实page read，再读真实文件bytes核ID/path/hash，最后短事务建关联，人工控制。

本卡客户端准确公开面（Python在 `src/astrophotoflow/interfaces/client/workflows.py` 的WorkflowOperations，根AssetClient组合；TS在本模块api/client.ts）：

```python
def list_workflows(self, project_id: UUID, *, limit: int = 50, offset: int = 0) -> WorkflowPage: ...
def get_workflow(self, workflow_id: UUID) -> WorkflowDetail: ...
```

```typescript
export interface WorkflowsClient {
  listWorkflows(projectId: string, options?: { limit?: number; offset?: number }): Promise<WorkflowPage>
  getWorkflow(workflowId: string): Promise<WorkflowDetail>
}
export function createWorkflowsClient(fetchApi: FetchApi): WorkflowsClient
```

**6. 有序小步。** ①模型/0010/env/schema常量/迁移测试；②list/get+首次关联，补真实page read：未托管首次save无permit先走原生保存，成功后associate一次；B52再handoff，不要求尚不存在的control_token；③托管后的save/rename/saveas/delete才经api before token→原生最终guard→原生写→finish，finish更新关联，不再双发associate；④项目图UI/client/代理/OpenAPI和G05。SQLite事务不跨page read/HTTP/文件等待；写成但关联失败分别报告，阻止后续run。重复同图关联只读，不授权。

**7. 禁止/保持。** 不写第二图、不用instanceId、不建临时图控制生命周期或持久permit；非托管userdata不强绑APF；缺token不能绕过已托管路径；失败不删文件假报回滚，不重放保存。B52前不加可调用handoff旁路。

**8. 测试/验收。** F-GRAPHS两图同节点ID，新图/缺依赖JSON/saveas新ID；0009含真实数据升级0010后既有行不变；错误项目/bytes/hash/token409；文件成功关联失败分开显示且零run；删除清专属预览不删运行/素材。拟新增文件创建后运行：

```powershell
uv run --locked --no-sync pytest tests/modules/workflows/test_service.py tests/modules/data/test_service.py tests/modules/data/test_domain_foundation.py tests/packaging/test_layout.py tests/architecture/test_import_boundaries.py -q
pnpm --dir frontend test:unit src/platform/astrophotoflow/workflowBridge.test.ts src/platform/workflow/core/services/workflowService.test.ts src/platform/workflow/management/stores/workflowStore.test.ts src/platform/workflow/persistence/composables/useWorkflowAutoSave.test.ts
node tests/browser/platform-workflows.mjs
pnpm test:browser
```

浏览器仅新隔离workspace，沿`APF_WEB_URL`选择实例；新脚本沿已有native-web脚本同一环境变量模式。G05必须从真实快捷/自动/另存/改名/删除操作观察最终guard；不能用按钮Mock代签。

**9. 完成/Ready与证据。** Ready前置：上游集成和G05原型通过，真实首次关联/read接缝已验证；没有新增公开签名缺口。卡集成证据置`.artifacts/implementation/B51/`：候选/差异、迁移前后行事实、save/association分别结果、实际ID/path/hash（脱敏）、测试命令/结果及限制。G05失败保持待前置，不造关联或自动换图。未通过用户M5验收不记Milestone完成。

<a id="b52"></a>

## B52 — 在线局部编辑、明确交回与安静接续

状态：未开工；待确认总计划/前置，满足后才Ready。

**1. 目标。** `codex/workflow-online-editing`。用户明确目标页“交给Agent”后，Agent可读取真实当前画布、按原生ID局部编辑/保存/明确替换；手动编辑即接管，切图暂停旧目标新写，多页同ID不串；拖入/显式set_data使用固定科学引用。A52-1～4 / V04/10/11 / G06。

**2. 必读。** [需求FR-02/07/08、场景3.2](../../../../requirements/README.md#scenario-canvas)、[⑤数据](../../architecture/data-models/05-workflows.md)、[局部操作/完整签名](../../api/platform-contracts.md#workflows-design)、[页面/首次交回/共享控制](../../api/platform-contracts.md#native-design)。精确读④“局部编辑和页面交接”“宿主与UI入口”“固定消息路线”“真实交回”“共享图控制”。R：[ChangeTracker](../../../../../frontend/src/scripts/changeTracker.ts)、[原生API](../../../../../frontend/src/scripts/api.ts)、[素材Workspace](../../../../../frontend/packages/astrophotoflow-ui/src/modules/data/workspace/Workspace.vue)。

**3. 前置。** B23/B43/B51；B22已定`validate_input_references`真实落位；B32原生WS薄桥接；真实页面在线。没有页面时读取保存图/控制事实，不伪造actual current_graph。

**4. 文件表。**

| 路径 | M/R与职责 | 依赖/边界 |
|---|---|---|
| `src/astrophotoflow/contracts/workflows.py` | M：页面/Guard/EditOp/EditResult/Save/Replace/AgentContext既定类型 | 原生JSON不复制；无新Target/控制实体 |
| `src/astrophotoflow/modules/workflows/public.py`、`src/astrophotoflow/modules/workflows/routes.py` | M：context/page事件/edit/save/replace及有限错误 | ②④公开能力、PageCall；无data ORM/import interfaces |
| `src/astrophotoflow/interfaces/http/app.py`、`src/astrophotoflow/interfaces/comfyui.py`、`engine/ComfyUI/server.py` | M：同socket定向命令/回包、真实socket page观察 | 仅有限apf.*，当前pages/等待回包内存，不建连接服务 |
| `frontend/src/platform/astrophotoflow/software/confirmation.ts`、`frontend/src/platform/astrophotoflow/sidebar/NativeShell.vue`、`frontend/src/scripts/api.ts` | M：实际本地图操作/真实交回/撤销/支持列表/连接生命周期 | 原生Store及LiteGraph实际操作；包外单例只在宿主 |
| `frontend/src/scripts/changeTracker.ts`、`frontend/src/platform/workflow/core/services/workflowService.ts` | M：真实手改/undo/redo与切图观察 | 不以所有graphChanged都当人工，保原生历史 |
| `frontend/packages/astrophotoflow-ui/src/modules/workflows/WorkflowPanel.vue`、`frontend/packages/astrophotoflow-ui/src/modules/workflows/api/contracts.ts`、`frontend/packages/astrophotoflow-ui/src/modules/workflows/api/client.ts`、`frontend/packages/astrophotoflow-ui/src/modules/workflows/index.ts`、`frontend/packages/astrophotoflow-ui/src/index.ts` | M：当前目标/同步/控制可见，真实具名client与交给Agent按钮回调 | 无自填human/confirmed/恢复控制能力 |
| `frontend/packages/astrophotoflow-ui/src/modules/data/workspace/Workspace.vue`、`frontend/src/platform/astrophotoflow/sidebar/LibrarySidebarTab.vue` | M：公开宿主接缝的拖入/选择事件 | 不在data UI导入画布或生成内部path |
| `src/astrophotoflow/interfaces/client/workflows.py`、`src/astrophotoflow/comfyui/proxy.py`、`docs/api/openapi.json` | M：相应具名方法/代理/实际快照 | 无临时MCP注册 |
| `tests/modules/workflows/test_service.py`、`frontend/src/platform/astrophotoflow/workflowBridge.test.ts`、`tests/browser/platform-workflows.mjs` | M：多页、迟到、部分应用、人工接管与真实按钮 | 同一P文件增量 |

**5. 关键签名/公开面。**

```python
async def get_agent_context(database: Database, page: PageObservation | None, page_command: PageCall) -> AgentContext: ...
def apply_page_event(database: Database, page: PageObservation, action: Literal['open', 'state', 'changed', 'handoff']) -> AgentContext: ...
async def edit_workflow(database: Database, settings: Settings, body: EditRequest, page_command: PageCall) -> EditResult: ...
async def save_workflow(database: Database, settings: Settings, guard: WorkflowGuard, page_command: PageCall) -> SaveResult: ...
async def replace_workflow(database: Database, settings: Settings, body: ReplaceRequest, page_command: PageCall) -> ReplaceResult: ...
async def page_command(client: "AsyncClient", command: PageCommand) -> PageResult: ...
# data.public由B22实现，编辑期只读校验，不准备科学文件
def validate_input_references(database: Database, project_id: UUID, references: Sequence[InputReference]) -> None: ...
```

```typescript
export function installWorkflowBridge(client: WorkflowsClient): () => void
export function giveToAgent(projectId?: string): Promise<AgentContext>
export function noteManualChange(): void
export function applyLocalEdits(body: EditRequest): Promise<EditResult>
export function saveCurrentCanvas(guard: WorkflowGuard): Promise<SaveResult>
```

GET `/workflows/agent-context`先于动态ID路由；POST `/workflows/{workflow_id}/edits|save|replace`→上述领域函数。两个客户端本卡新增以下四个真实成员；签名见[④客户端](../../api/platform-contracts.md#python-clients)与⑤入口，不能从旧TS名称猜Python名。PageCommand实际命令经同socket，结果核相同page/command关联；get_context/get_workflow在线时先发read取本次真实图，缓存PageObservation只定位/断连判断。内部page事件只派发四动作，不对外提供handoff工具。

```python
def get_agent_context(self) -> AgentContext: ...
def edit_workflow(self, body: EditRequest) -> EditResult: ...
def save_workflow(self, guard: WorkflowGuard) -> SaveResult: ...
def replace_workflow(self, body: ReplaceRequest) -> ReplaceResult: ...
```

```typescript
getAgentContext(): Promise<AgentContext>
edit(body: EditRequest): Promise<EditResult>
save(guard: WorkflowGuard): Promise<SaveResult>
replace(body: ReplaceRequest): Promise<ReplaceResult>
```

**6. 四步。** ①真实页面/活动目标/read和当前控制：首次handoff沿B51保存/关联成功后进行；②add_data/set_data在改图前调用②validate_input_references，短read_session只核项目/固定版本/逐成员映射scope/选择结构，不hash/copy/mkdir/Preview/建run或返回path；其余支持的add_node/set_parameter/connect/disconnect/remove/move/undo/redo逐项原生应用并返回真实新ID，首次失败即停，保存结果单列；③真正manual事务先本地失效旧权后发changed，Agent/控件准备实际来源不误判，切图不接管但暂停旧写；④拖入/set_data/明确replace/UI和G06迟到/断连。所有操作在实际应用前核target/content/control，不自动重绑最新页；实际运行仍resolve_inputs。

**7. 保持/禁止。** 不新增编辑DSL/第二撤销栈/服务器草稿/永久画布回执；缩放/平移/查看/切页签不接管；read/重连/换客户端不恢复已撤销控制；不在读取时自选页；不重放已部分应用批次；现有组追加不推进固定引用；外部接纳只由显式set_data更新指定实例。不把②resolve_inputs当编辑期验证去创建run文件。

**8. 测试/验收。** A/B两个网页同节点12：绑定A后切B→A后续写/提交拒绝B不变；参数/布局/undo接管，缩放/切页不接管；允许状态跨客户端读可续，撤销后新客户端也拒；op0加节点成功、op1不支持、op2不执行，真实ID和保存状态准确；断连未知先read无重放；P项目不能set_data到Q私有素材/错误固定成员，明确set_data仅换选中节点。文件创建后：

```powershell
uv run --locked --no-sync pytest tests/modules/workflows/test_service.py tests/modules/data/test_workflow_handoffs.py tests/integration/test_client_operations.py tests/interfaces/comfyui/test_proxy.py -q
pnpm --dir frontend test:unit src/platform/astrophotoflow/workflowBridge.test.ts src/scripts/changeTracker.test.ts src/platform/workflow/core/services/workflowService.test.ts
node tests/browser/platform-workflows.mjs
```

G06须真实同socket命令/结果/确认来源和迟到；B53再补嵌套prepare不自锁。手动变更后不唤醒Agent；真实客户端下次读最新目标由B57联调，不能在此代签任意模型遵守。

**9. Ready/完成。** validate_input_references由B22实现，本卡消费上文精确签名；上游/G06仍为实施阻塞，原型失败保持待前置。完成证据记录A/B目标、token失效事实、部分op结果、真实按钮来源、测试及限制；整卡集成后仍留M5用户验收。

<a id="b53"></a>

## B53 — 统一受控运行、显式测试与首次运行保护

状态：未开工；待确认总计划/前置，满足后才Ready。

**1. 目标。** `codex/workflow-controlled-runs`。人工按钮/快捷键/自动队列/Agent进入同一run受理；每轮控件准备、graphToPrompt、原生保存各一次，保存成功/长准备后重核才唯一原生提交；真实科学文件/资料/软件/定义固定；完整get/list和显式节点测试可查询。首次运行即保护忙闲/清理/固定实现。A53-1～5 / V02/07/12/13/14/17 / G06/G07，真实调用沿G02/G04。

**2. 必读。** [FR-09/10/16及科学规则](../../../../requirements/README.md#4-功能需求)、[⑤数据](../../architecture/data-models/05-workflows.md)、[运行顺序](../../api/platform-contracts.md#workflows-design)、[入队guard/token/长准备/科学端口](../../api/platform-contracts.md#native-design)、[②活动输入边界](../../api/platform-contracts.md#data-design)。精确读④“单次运行固定顺序”“最终范围guard”“私有执行token”“显式节点测试”“长准备生命周期”“科学端口实际封装”“活动输入与永久清理”。R：[原生队列调用](../../../../../frontend/src/scripts/app.ts)、[转换](../../../../../frontend/src/utils/executionUtil.ts)、[原生最终入队](../../../../../engine/ComfyUI/server.py)、[原生执行](../../../../../engine/ComfyUI/execution.py)、[CurrentNodeContext](../../../../../engine/ComfyUI/comfy_execution/utils.py)、[真实unlink](../../../../../src/astrophotoflow/modules/data/trash.py)。

**3. 前置。** B24/B33/B42/B52集成；G02真实首软件/格式/有序集合/停止定位、G04真实当前registry通过。只对已关联的明确在线目标创建新run；已受理Task不因页面关闭停止。原生单引擎队列仍唯一调度器。G06嵌套准备与G07动态控件/范围/缓存原型失败即阻塞入口集成。

**4. 文件表。**

| 路径 | N/M/R与职责 | 依赖/边界 |
|---|---|---|
| `src/astrophotoflow/contracts/workflows.py`、`src/astrophotoflow/contracts/inputs.py` | M：既定RunContext/RunDetail/NativeCall/Validation/ActiveRunInputUse | 不造第二输入/执行投影schema；公开去path/token |
| `src/astrophotoflow/modules/workflows/public.py`、`src/astrophotoflow/modules/workflows/routes.py` | M：唯一受理/准备/实际调用/get/list/test及保护投影 | 只消费data/software/nodes public；必要共享私有prepare随submit/test两个真调用者提取 |
| `src/astrophotoflow/interfaces/http/app.py`、`src/astrophotoflow/interfaces/comfyui.py` | M：当前preparations生命周期、固定native callables、human内部来源、prompt-check/call | app只装配，不写⑤ORM；适配仅固定HTTP/WS/原生投影，双解释器依赖隔离 |
| `engine/ComfyUI/server.py`、`engine/ComfyUI/execution.py` | M：validate后put前guard、token敏感/hidden/异常脱敏 | 不改引擎调度/普通取消响应；用原生CurrentNodeContext实际定位 |
| `src/astrophotoflow/core/workbench.py` | M：仅G07证实需要的科学缓存启动参数及维护接缝 | 已有`--cache-none`候选，未证明不标通过；无新缓存体系 |
| `src/astrophotoflow/modules/data/trash.py`、`src/astrophotoflow/modules/data/science_inputs.py` | M：本次unlink写Session调用active_input_usage；解析先拒cleanup_active | 复用现有回收站校准/导入/预览/共享路径规则；data不导入⑤ |
| `src/astrophotoflow/modules/data/public.py` | M：保留B24导出，必要实际callback接缝 | 不新增Protection表/输入登记API |
| `src/astrophotoflow/modules/software/public.py`、`src/astrophotoflow/interfaces/http/app.py` | M：既有maintain_package段组合⑤固定实现使用 | queued/preparing及binding_unknown也阻止已存在的包维护；B55新增卸载/更新沿同一保护，不只看③句柄 |
| `frontend/src/platform/astrophotoflow/software/confirmation.ts`、`frontend/src/scripts/app.ts` | M：prepareRun/check/submitNativeRun，托管分支唯一投递 | 复用现有控件顺序/Store保存/原生queued job与afterQueued；非托管路径保留 |
| `frontend/packages/astrophotoflow-ui/src/modules/workflows/WorkflowPanel.vue`、`frontend/packages/astrophotoflow-ui/src/modules/workflows/api/contracts.ts`、`frontend/packages/astrophotoflow-ui/src/modules/workflows/api/client.ts`、`frontend/packages/astrophotoflow-ui/src/modules/workflows/index.ts` | M：run真实受理/查询/准备/错误与显式测试展示 | 不以202显示完成；UI人工运行走宿主回调 |
| `frontend/packages/astrophotoflow-ui/src/modules/nodes/NodeEditor.vue`、`src/astrophotoflow/modules/nodes/routes.py` | M：显式节点测试接同次run；最近测试取⑤ | 不增④执行器，测试不是保存/ready门禁 |
| `src/astrophotoflow/interfaces/client/workflows.py`、`src/astrophotoflow/interfaces/client/nodes.py`、`src/astrophotoflow/interfaces/cli/commands.py`、`src/astrophotoflow/comfyui/proxy.py` | M：具名run/test、CLI只读、代理 | CLI不直接SQL；无临时MCP |
| `tests/modules/workflows/test_runs.py` | N：固定受理/范围/未知/保护/显式测试 | mocks只证明局部，不代签G07 |
| `tests/integration/test_platform_workflow.py` | M（B12已创建）：真实科学输入/软件/引擎与首次保护 | 同一跨模块集成文件增量 |
| `tests/modules/workflows/test_service.py`、`tests/modules/data/test_workflow_handoffs.py`、`tests/modules/data/test_service.py`、`tests/core/test_workbench.py`、`frontend/src/platform/astrophotoflow/workflowBridge.test.ts`、`tests/browser/platform-workflows.mjs`、`docs/api/openapi.json` | M：现有P文件/保护/维护/宿主/浏览器/实际快照增量 | 一卡内全部必需保护先接通才集成 |

**5. 完整关键签名/公开映射。**

```python
PageCall = Callable[[PageCommand], Awaitable[PageResult]]
SubmitPrompt = Callable[[NativePromptRequest], Awaitable[NativePromptReply]]
ObservePrompt = Callable[[UUID], Awaitable[JsonObject]]
async def submit_run(database: Database, settings: Settings, body: RunSubmit, page_command: PageCall, post_prompt: SubmitPrompt, *, origin: Literal['human', 'agent'], preparations: dict[UUID, Task[None]]) -> RunDetail: ...
async def test_node(database: Database, settings: Settings, body: NodeTestCreate, page_command: PageCall, post_prompt: SubmitPrompt, *, origin: Literal['human', 'agent'], preparations: dict[UUID, Task[None]]) -> RunDetail: ...
async def execute_node(database: Database, settings: Settings, body: NativeNodeCall) -> NativeNodeResult: ...
async def get_run(database: Database, settings: Settings, run_id: UUID, query_prompt: ObservePrompt) -> RunDetail: ...
def list_runs(database: Database, workflow_id: UUID, *, limit: int = 50, offset: int = 0) -> RunPage: ...
def latest_node_test(database: Database, definition_id: UUID) -> NodeTestResult | None: ...
def check_native_prompt(database: Database, body: NativePromptCheck) -> None: ...
def workflows_busy(database: Database) -> BusyState: ...
def find_active_input_usage(session: Session, asset_version_ids: Sequence[UUID], read_paths: Sequence[Path]) -> list[ActiveRunInputUse]: ...
async def get_implementation_usage(database: Database, settings: Settings, query_prompt: ObservePrompt, *, package_ids: list[str], definition_ids: list[UUID]) -> list[RunImplementationUse]: ...
# app内闭包，只委托⑤，路径definition_id必须与body一致
async def submit_node_test(body: NodeTestCreate) -> RunDetail: ...
# interfaces/comfyui.py，领域/引擎两侧薄适配
async def post_prompt(client: "AsyncClient", request: NativePromptRequest) -> NativePromptReply: ...
async def query_prompt(client: "AsyncClient", prompt_id: str) -> dict[str, JsonValue]: ...
async def guard_prompt(server: "PromptServer", request: NativePromptRequest, outputs_to_execute: list[str], node_errors: dict[str, JsonValue], *, validation_error: JsonValue = None) -> None: ...
async def execute_node(execution_token: str, scientific_values: dict[str, ScientificValue | list[ScientificValue]], parameter_values: dict[str, JsonValue]) -> NativeNodeResult: ...
```

```typescript
export function prepareRun(runId: string, guard: WorkflowGuard, options: NativeRunOptions): Promise<NativePreparedCanvas>
export function checkRunCanvas(guard: WorkflowGuard): Promise<AgentContext>
export function submitNativeRun(options: NativeRunOptions | NodeTestCreate): Promise<RunDetail>
```

POST `/workflows/{workflow_id}/runs`→submit_run(origin='agent')返回202；内部真实页面submit_run→同函数origin='human'；POST `/nodes/{definition_id}/test`→submit_node_test/test_node，显式测试先登记run再编辑；GET `/runs/{run_id}`/`/workflows/{workflow_id}/runs`→get/list；内部prompt-check→check_native_prompt成功204、call→execute_node。节点详情最近测试读latest_node_test。客户端完整增量如下；NodeOperations.test_node及NodesClient.test只接同一显式测试链。CLI `apf runs get RUN_ID`和`apf runs list --workflow WORKFLOW_ID --limit N --offset N`只用具名client。ObservePrompt的UUID由app在绑定query_prompt时转str；不修改契约/创造新类型。

```python
def submit_run(self, body: RunSubmit) -> RunDetail: ...
def get_run(self, run_id: UUID) -> RunDetail: ...
def list_workflow_runs(self, workflow_id: UUID, *, limit: int = 50, offset: int = 0) -> RunPage: ...
def test_node(self, body: NodeTestCreate) -> RunDetail: ...
```

```typescript
submitRun(body: RunSubmit): Promise<RunDetail>
getRun(runId: string): Promise<RunDetail>
listRuns(workflowId: string, options?: { limit?: number; offset?: number }): Promise<RunPage>
test(body: NodeTestCreate): Promise<RunDetail>
```

前三个分别属于WorkflowOperations/WorkflowsClient，最后一个属于NodeOperations/NodesClient；现有工厂随接口增量，不新增客户端层。app在实际maintenance段读取get_implementation_usage，data的 `app.state.active_input_usage` 直接绑定find_active_input_usage；清理preview、初次事务及每资产unlink前最后write Session均调用同一函数，不能另开连接读取。ActiveRunInputUse只在此卡首次运行消费者出现时新增到contracts/inputs.py。

**6. 四步整卡集成。** ①run_id短事务preparing：同ID同请求只查，异内容409；真实preparations Task字典由app持有/排空。**同步接**workflows_busy、active_input_usage和get_implementation_usage到维护/实际unlink：未固定范围或binding未知阻塞，不能先开放运行再补。②固定RunContext/UUID prompt/private token并提交前写入；engine在原生validate之后queue.put之前guard，读取已有上下文立即判断，外层不持事务/跨请求锁等待回调；实际节点从CurrentNodeContext取prompt/node/list，核固定binding/实际入边，资产从本run固定输入取，上游仅当前run manifest locator，真实scalar采用值入同run，调用③并检查完整输出。③宿主复用app.ts现有beforeQueued/promoted一次、graphToPrompt一次、既有saveWorkflow一次；长准备后check只读，再领域唯一post_prompt，托管分支不调用api.queuePrompt第二次；202后查询到本轮真实受理/未知/失败才开始下一batch。④完整HTTP/CLI/UI/显式test与G06/G07证据，所有入口与保护同卡集成。

缓存首选验证原生现有`--cache-none`（现有cli_args.py/main.py），以连续同参真实③调用证明；不能把run_id写无效_meta冒充失效。若原型不能证明需求，保持待前置，由强模型处理，不让执行Agent创造缓存抽象。私有token放SENSITIVE_EXTRA_DATA_KEYS并仅新增APF_EXECUTION_TOKEN hidden；在execution_error格式化current_inputs前剔除该hidden，实测queue/history/WS异常/日志/图均不含字面token。

人工节点测试的精确接线：NodeEditor按钮由NativeShell传入宿主回调（`(body: NodeTestCreate) => Promise<RunDetail>`），宿主调用`submitNativeRun(body)`发既有`apf.page action=submit_run`；内部按NodeTestCreate分派`test_node(origin=human)`，普通RunSubmit才分派`submit_run(origin=human)`。公开NodesClient.test／nodes/test仍为agent来源，不用于GUI测试。验收人工接管后仍可显式测试、run记录node_test和最近测试，且agent_allowed保持false；重复同run_id不再次编辑。只扩同一函数既定的两种请求载荷，不加桥接函数、第二执行器或新事件。

**7. 禁止/保持。** 不新执行器/第二队列/第二转换器/自由执行参数或path；不把所有节点设终点；不在排队后resolve当前资料/重新物化；保存false/association不全/切图/控制失效/async语义不明→零投递，图草稿保留；未知不重投/重call；既有非托管原生行为保持；测试失败不阻定义保存；B53首次preparing/queued固定实现即接维护保护，B55新增卸载/更新必须复用，不能到B55才首次补保护。

**8. 测试/验收。** F-DYNAMIC s0→beforeQueued s1→afterQueued s2：保存/RunContext/prompt为s1，各一次，s2只下一编辑；async serialize等待手改/切图阻止；保存失败零/prompt；一好一坏目标→全拒且queue无该prompt；same run重试只查/不同内容409；大文件准备受理202不持事务；响应前真实call仍可关联；同参两次真实处理；准备/queued与unlink竞态不删源；call顶层失败仍active/unknown挡维护；显式节点测试重复请求不重复改图。新P文件创建后：

```powershell
uv run --locked --no-sync pytest tests/modules/workflows/test_runs.py tests/modules/workflows/test_service.py tests/modules/data/test_workflow_handoffs.py tests/modules/data/test_service.py tests/core/test_workbench.py tests/integration/test_platform_workflow.py -q
pnpm --dir frontend test:unit src/platform/astrophotoflow/workflowBridge.test.ts src/utils/executionUtil.test.ts src/scripts/changeTracker.test.ts
node tests/browser/platform-workflows.mjs
```

G06须在真实同socket提交处理中仍能接嵌套prepare结果、无自锁。G07须真实首软件、HDU/有序集合/原件hash/重新处理/范围核对；Mock只能证明次数/局部错误。GET run须在history清除/重启缺证据时保留持久事实/unknown，查询不执行。

**9. Ready/证据。** 上游和G02/G04/G06/G07均是阻塞；缓存方案/动态控件语义须原型锁定。当前关键公开签名已齐，内部仅允许为两个真调用者提取必要共享实现，不预设计helper套件。完成证据：候选、实际软件/原生版本、输入hash/顺序/HDU、run/prompt/call关联、准备成本、恰一次链路、guard拒绝时零入队、token脱敏和清理竞态；B53自动/独立审查通过后整卡集成，M5实际验收仍待后续。

<a id="b54"></a>

## B54 — 无网页运行事实、取消、预览、所选保存与移除联调

状态：未开工；待确认总计划/前置，满足后才Ready。

**1. 目标。** `codex/workflow-results-and-cancel`。无网页仍更新真实运行/调用/产物；定向取消不误伤、送达与实际停止分开；每个实际完成图像输出压缩预览归原图；用户所选完整成员固定同task登记/反查；提供内部真实find_input_usage供公共移除发布时使用，永久清理保持B53保护。A54-1～6 / V02/14/15/16/17的内部部分；A54-5公共移除链由B57关闭 / G08；普通移除公共HTTP/client/MCP按用户确认在B57一次切换，不在本卡提前改变现有行为。

**2. 必读。** [FR-09/10、结果选择](../../../../requirements/README.md#scenario-continuity)、[⑤数据](../../architecture/data-models/05-workflows.md)、[run/输出/预览public](../../api/platform-contracts.md#workflows-design)、[无网页事件及取消专节](../../api/platform-contracts.md#native-design)、[②登记/移除闭合](../../api/platform-contracts.md#data-design)。精确读④“所选结果登记/查询”“从所选完整结果反查运行”“无浏览器运行观察”“定向取消与实际停止”。R：[取消helper](../../../../../engine/ComfyUI/comfy_execution/jobs.py)、[原生目标中断](../../../../../engine/ComfyUI/execution.py)、[原生预览消费](../../../../../frontend/src/stores/nodeOutputStore.ts)、[现有归图ChangeTracker](../../../../../frontend/src/scripts/changeTracker.ts)、[任务序列化](../../../../../src/astrophotoflow/modules/data/imports.py)。

**3. 前置。** B24+B53；首软件G02已证明真实停止/恢复定位。完整模型和来源事实仍归⑤/②/③各自；B53已经接好永久unlink/固定实现与忙闲，此卡增量回归，不重新做一套保护。原生事件失败不得阻塞引擎；关闭页面仅失去新画布操作，不停已受理任务。

**4. 文件表。**

| 路径 | M/R与职责 | 依赖/边界 |
|---|---|---|
| `src/astrophotoflow/contracts/workflows.py` | M：既定NativeExecutionEvent/CancelResult/预览/OutputSave；LibraryRemovalScope复用B24，Preview/Apply只在B57新增 | 不建事件/取消任务/保存回执实体 |
| `src/astrophotoflow/modules/workflows/public.py`、`src/astrophotoflow/modules/workflows/routes.py` | M：事件/cancel/预览/所选保存/反查/影响；增量完善既有get_run/get_usage | ③inspect/cancel、②check/render/register/query；无跨模块私有ORM |
| `src/astrophotoflow/interfaces/comfyui.py`、`src/astrophotoflow/interfaces/http/app.py` | M：有限异步事件转发、typed定向取消/观察、固定callback和输出任务调度 | 不添第二socket/事件队列；app只组合 |
| `engine/ComfyUI/server.py` | M：send_sync非阻塞观察hook/有限内部取消route注册 | 不修改既有public取消bool或helper逻辑 |
| `src/astrophotoflow/modules/data/trash.py`、`src/astrophotoflow/modules/data/routes.py` | R：回归B53实际unlink保护；公共removal-preview/DELETE改装配留B57同卡发布 | 不注入空消费者、不提前改现有普通移除请求语义 |
| `src/astrophotoflow/modules/data/ingestion.py`、`src/astrophotoflow/modules/data/imports.py`、`src/astrophotoflow/modules/data/public.py` | R，若B24观察到缺口仅M窄修：真实同task/阶段、路径脱敏 | 不重写导入/增来源表，不先登记做预览 |
| `frontend/src/platform/astrophotoflow/software/confirmation.ts`、`frontend/src/scripts/app.ts`、`frontend/src/scripts/changeTracker.ts`、`frontend/src/stores/nodeOutputStore.ts` | M：prompt→run→workflow显示/事件归图 | B同节点ID不接A的onExecuted，不抢视图；缓存回放非新处理 |
| `frontend/packages/astrophotoflow-ui/src/modules/workflows/WorkflowPanel.vue`、`frontend/packages/astrophotoflow-ui/src/modules/workflows/api/contracts.ts`、`frontend/packages/astrophotoflow-ui/src/modules/workflows/api/client.ts` | M：实际进度/取消/多次预览/选择完整结果/保存事实 | 不把HTTP200或202变完成，名称省略合法 |
| `frontend/packages/astrophotoflow-ui/src/modules/data/workspace/Workspace.vue` | M：已保存素材来源只读回查 | ②不读⑤ORM，宿主组合回查运行；普通移除新字段/UI留B57 |
| `src/astrophotoflow/interfaces/client/workflows.py`、`src/astrophotoflow/comfyui/proxy.py`、`docs/api/openapi.json` | M：run结果具名方法/图像与实际API | 现有library客户端普通移除请求不在此提前改 |
| `tests/interfaces/comfyui/test_cancel.py` | N：typed内部取消route/适配，复用原native helper的行为 | 不复制第二个取消分类器 |
| `tests/modules/workflows/test_runs.py`、`tests/modules/data/test_workflow_handoffs.py`、`tests/modules/data/test_service.py`、`tests/integration/test_platform_workflow.py`、`frontend/src/platform/astrophotoflow/workflowBridge.test.ts`、`tests/browser/platform-workflows.mjs` | M：事件/取消/保存/清理竞态/跨图UI | 同一P文件集中，不复制每层全部case |

**5. 完整关键签名/映射。**

```python
async def apply_native_event(database: Database, settings: Settings, body: NativeExecutionEvent) -> None: ...
CancelPrompt = Callable[[UUID], Awaitable[NativeCancelResult]]
ObservePromptState = Callable[[UUID], Awaitable[NativePromptObservation]]
async def cancel_run(database: Database, settings: Settings, run_id: UUID, cancel_prompt: CancelPrompt, observe_prompt_state: ObservePromptState) -> CancelResult: ...
def list_previews(database: Database, run_id: UUID) -> list[PreviewSummary]: ...
def read_preview(database: Database, settings: Settings, run_id: UUID, preview_id: UUID) -> tuple[bytes, str]: ...
async def save_output(database: Database, settings: Settings, run_id: UUID, body: SaveOutput) -> OutputSaveResult: ...
def find_saved_output(database: Database, asset_version_id: UUID) -> OutputLocator | None: ...
def find_input_usage(database: Database, settings: Settings, pages: Sequence[PageObservation], scope: LibraryRemovalScope) -> list[WorkflowImpact]: ...
# interfaces/comfyui.py
def observe_native_event(server: "PromptServer", event: NativeExecutionEvent) -> None: ...
async def forward_native_event(server: "PromptServer", event: NativeExecutionEvent) -> None: ...
def cancel_native_prompt(server: "PromptServer", prompt_id: UUID) -> NativeCancelResult: ...
async def receive_prompt_cancel(server: "PromptServer", request: "Request") -> "Response": ...
async def cancel_prompt(client: "AsyncClient", prompt_id: UUID) -> NativeCancelResult: ...
async def observe_prompt_state(client: "AsyncClient", prompt_id: UUID) -> NativePromptObservation: ...
```

```typescript
export function receiveExecuted(message: ExecutedWsMessage): void
```

内部POST `/internal/native/event`→apply_native_event成功204；POST `/runs/{run_id}/cancel`→cancel_run返回200真实CancelResult；GET `/runs/{run_id}/previews`及`/{preview_id}`→list/read（image/jpeg）；POST `/runs/{run_id}/outputs/save`→save_output；GET `/runs/outputs/by-asset-version/{asset_version_id}`→find_saved_output（先于动态runs路由）。客户端按下列准确增量实现，来源回查findSavedOutput已在④固定，不新造方法或恢复API。find_input_usage仅真实同进程公开查询，给B57公共移除组合消费，不新增临时HTTP/工具。

```python
def cancel_run(self, run_id: UUID) -> CancelResult: ...
def list_run_previews(self, run_id: UUID) -> list[PreviewSummary]: ...
def read_run_preview(self, run_id: UUID, preview_id: UUID) -> bytes: ...
def save_run_output(self, run_id: UUID, body: SaveOutput) -> OutputSaveResult: ...
def find_saved_output(self, asset_version_id: UUID) -> OutputLocator | None: ...
```

```typescript
cancelRun(runId: string): Promise<CancelResult>
listPreviews(runId: string): Promise<PreviewSummary[]>
readPreview(runId: string, previewId: string): Promise<Blob>
saveOutput(runId: string, body: SaveOutput): Promise<OutputSaveResult>
findSavedOutput(assetVersionId: string): Promise<OutputLocator | null>
```

以上为WorkflowOperations/WorkflowsClient的真实成员。read_run_preview沿原read_display_preview的JPEG检查/bytes返回模式，错误沿同一ServiceApiError；不复制错误处理器。

**6. 四步整卡集成。** ①send_sync只把有真实prompt_id且已登记托管运行的有限事件安排到原生loop，立即返回；领域按prompt关联真实run，不用最后运行猜，终态不被迟到progress倒退。GET使用已保存prompt/query和③inspect实际active补事实，unknown结果与实际占用分开。②cancel先短写requested并与新call准入同边界；按run所有starting/running/unknown calls定向发一次native typed取消和③cancel（互不因另一失败而跳过），事务外等待再聚合；dequeued/interrupt_sent只来动作回执，GET jobs+queue只观察，不伪造动作；任一actual running→running，有未决且无running→unknown，真正停止才stopped。③actual完成图像输出→②check_output/render_output_preview→唯一`workspace/output/apf-previews/{run_id}/{preview_id}.jpg`，原生ui.images/view和HTTP读同文件；用户明确选择一个locator后⑤短事务先固定唯一task，②register/query同task，仅registration.created=True由app用现有workers调process_task，公开path脱敏；源保留至②内容完成/明确失败，成功托管副本不受旧源丢失影响。④find_input_usage真实读取保存图/已知页面，按B24版本范围和所选成员返回精确WorkflowImpact供B57消费；实际unlink前保护继续回归；本卡run/UI/代理/client联调并接完整①忙闲。普通移除公共preview/DELETE/fingerprint和请求模型保持到统一发布卡，不用空回调提前声称支持。

**7. 禁止/保持。** 不持久化逐帧事件/进度、不重放事件或自动重跑科学处理；不按preview证明完整文件可保存；不复制第二份JPEG、不登记未选输出；不把顶层failed或空句柄当闲；现有校准/活动导入/预览/共享路径保护保留；已完成自然run不因后来cancel改成cancelled；普通移除不变永久unlink或停止运行；data/⑤各自权威。

**8. 测试/验收。** A运行B排队，取消B不误停A；native移队后GET404仍保留正面dequeued；单纯GET404不证明移队；call不可停/失联/仍running与native终态分开；准备取消不能凭无prompt即stopped。两轮参数×两个输出/成员预览归locator，A后台完成B同ID不串；关闭网页仍终态/预览、history清除仍查已存事实。并发选择同完整成员/断连/归位后中断始终同task/asset，未选不登记；普通导入/同Asset外部新版本来源null。内部find_input_usage精确匹配固定版本/成员、同节点ID跨图不串、图变化反映最新影响；真实unlink前新run保护字节。公共DELETE旧确认409/缺字段422的联调归统一发布卡。执行：

```powershell
uv run --locked --no-sync pytest tests/modules/workflows/test_runs.py tests/modules/data/test_workflow_handoffs.py tests/modules/data/test_service.py tests/modules/data/test_display_previews.py tests/interfaces/comfyui/test_cancel.py tests/integration/test_platform_workflow.py tests/integration/test_client_operations.py -q
pnpm --dir frontend test:unit src/platform/astrophotoflow/workflowBridge.test.ts src/stores/nodeOutputStore.workflowSwitch.test.ts src/scripts/changeTracker.test.ts
node tests/browser/platform-workflows.mjs
```

取消的锁内验证使用根dev已有pytest／aiohttp，不新加pytest插件：`tests/interfaces/comfyui/test_cancel.py`用`asyncio.run`及aiohttp既有TestServer/TestClient运行真实内部route／typed适配；⑤测试覆盖跨软件停止聚合，真实原生／软件停止仍在G08隔离实例核对。可复用原生同步helper测试，命令只选择两个不需async插件的现有类：

```powershell
uv run --locked --no-sync pytest -c pyproject.toml --noconftest -o pythonpath=engine/ComfyUI engine/ComfyUI/tests-unit/jobs_cancel_test/jobs_cancel_test.py::TestClassifyJobForCancel engine/ComfyUI/tests-unit/jobs_cancel_test/jobs_cancel_test.py::TestCancelJobHelper -q
```

上游该文件的完整HTTP异步测试还需要未入当前dev锁的pytest-asyncio／pytest-aiohttp及其fixture，现有固定runtime也不含这些测试依赖。因此完整上游命令明确未就绪，不能作为本卡已可跑或通过门，不安装插件、不以未收集／跳过async计通过；必要取消行为由本卡锁内新测试和G08真实用例验证，不重复实现原生取消器。

真实结束或已核实停止后，B54从该run.context.inputs调用②`observe_reference_inputs(settings, inputs)`，把后置事实写回同run的`RunDetail.reference_observations`；只观察preparation=reference项。缺少采用上下文／结束证据则如实保留未知，不改旧AssetVersion或再次运行。用一条真实reference素材在执行期间变更的用例核对changed／missing／unverified、观察时间和hash，并断言软件／prompt均无第二次提交。

**9. Ready/证据。** B24/B53及G08阻塞；取消/事件/public签名已齐，不增加软件取消HTTP或保存状态任务表。完整get_implementation_usage/workflows_busy/find_active_input_usage归B53，此卡只增实际观察/结果接入。证据记录原生动作回执、③active/停止依据、预览/完整文件分别hash、task/asset/source定位、断连与部分清理事实；失败保持unknown/具体原因，不自动恢复。整卡自动/独立审查通过后集成，用户批准另作为M5出口。

<a id="b55"></a>

## B55 — 软件/节点确认更新与未打开图的受控保存

状态：未开工；待确认总计划/前置，满足后才Ready。

**1. 目标。** `codex/workflow-package-node-updates`。软件更新/卸载和自制节点更新先列准确影响，再真实确认；已固定preparing/queued/running/unknown实现阻止替换；变化参数/端口按既定规则，未打开图也沿原生最终文件guard写，逐图报告实际部分结果。A55-1～4 / V06/08 / G09。

**2. 必读。** [FR-03/16](../../../../requirements/README.md#scenario-nodes)、[③更新/卸载数据](../../architecture/data-models/03-software.md#更新与卸载)、[④修改数据](../../architecture/data-models/04-nodes.md#修改已有自定义节点)、[③④公开面](../../api/platform-contracts.md#software-design)、[⑤影响/更新](../../api/platform-contracts.md#workflows-design)、[已批准维护文件入口](../../api/platform-contracts.md#native-design)。重点读④“③必要public”“确认更新及在途保护”“public.py完整签名”“受控保存入口”“共享图控制”。R：[原生文件最终写](../../../../../engine/ComfyUI/app/user_manager.py)；运行实际事实复用 `src/astrophotoflow/modules/workflows/public.py`（B51起创建，B53接运行），原生Store/画布实际操作复用 `frontend/src/platform/astrophotoflow/software/confirmation.ts`（B32起创建）。

**3. 前置。** B32/B43/B51/B54；复用B53完整get_implementation_usage及现有maintain_package/①维护gate。G04已锁定实际加载/刷新/显式重启条件；G09未打开图和嵌套最终guard失败即阻塞。用户确认的是准确业务计划，普通Agent不能借维护后台改任意图。

**4. 文件表。**

| 路径 | M/R与职责 | 依赖/边界 |
|---|---|---|
| `src/astrophotoflow/contracts/workflows.py` | M：既定WorkflowChange/Impact/Preview/Result、NativeWorkflowChange/Result组合DTO | 单向引用③④，不造另一Target/审批/回执对象 |
| `src/astrophotoflow/modules/software/public.py`、`src/astrophotoflow/modules/software/routes.py` | M：真实preview_update/update_package/uninstall_package及首次公开卸载/图影响联动 | 固定包/准确版本/maintain_package；不直接调用④⑤ |
| `src/astrophotoflow/modules/nodes/public.py`、`src/astrophotoflow/modules/nodes/routes.py` | M：确认后的update_definition，复用B41纯差异和PortRemap | ④只写当前定义，测试/图实例归⑤；不保存多版类 |
| `src/astrophotoflow/modules/workflows/public.py`、`src/astrophotoflow/modules/workflows/routes.py` | M：find_definition_usage/preview/apply_workflow_change，复用B53实现占用 | 只改确认APF实例/参数/线，未知原生JSON原样保留 |
| `src/astrophotoflow/interfaces/http/app.py` | M：确认/维护段组合③④⑤，签发准确逐文件permit；get_node_details真实load | 不写ORM，不把impact_token当确认权限 |
| `src/astrophotoflow/interfaces/comfyui.py`、`engine/ComfyUI/server.py` | M：apply_file_change/receive_workflow_change固定受控内部路由 | 转发原生userdata，同一最终guard，无旁写JSON |
| `engine/ComfyUI/app/user_manager.py` | R，必要M仅复用B51同guard接维护来源 | 同token真实文件bytes核对；不建第二保存器 |
| `frontend/packages/astrophotoflow-ui/src/modules/software/SoftwarePanel.vue`、`frontend/packages/astrophotoflow-ui/src/modules/software/api/contracts.ts`、`frontend/packages/astrophotoflow-ui/src/modules/software/api/client.ts` | M：同一准确软件计划/真实确认/逐项状态 | 许可敏感输入仍用户直接处理 |
| `frontend/packages/astrophotoflow-ui/src/modules/nodes/NodeEditor.vue`、`frontend/packages/astrophotoflow-ui/src/modules/nodes/api/contracts.ts`、`frontend/packages/astrophotoflow-ui/src/modules/nodes/api/client.ts` | M：影响预览/确认更新/旧测试提示 | 软件配套变化默认与custom全新默认区分 |
| `frontend/src/platform/astrophotoflow/software/confirmation.ts`、`frontend/packages/astrophotoflow-ui/src/modules/workflows/WorkflowPanel.vue` | M：维护结果可见/后续交互重读保存图，保草稿不抢视图 | 无需每个被改图活动页面，不授Agent写权 |
| `src/astrophotoflow/interfaces/client/software.py`、`src/astrophotoflow/interfaces/client/nodes.py`、`src/astrophotoflow/comfyui/proxy.py`、`docs/api/openapi.json` | M：精确update-preview/update与实际响应 | 固定具名映射，无任意URL |
| `tests/modules/software/test_service.py`、`tests/modules/nodes/test_service.py`、`tests/modules/workflows/test_service.py`、`tests/modules/workflows/test_runs.py`、`tests/integration/test_platform_workflow.py`、`frontend/src/platform/astrophotoflow/workflowBridge.test.ts`、`tests/browser/platform-workflows.mjs` | M：差异、在途、草稿/文件竞态、部分失败/加载真实事实 | 不复制另一个工作流更新引擎 |

**5. 完整关键签名与映射。**

```python
# software.public
def preview_update(settings: Settings, package_id: str, target_version: str) -> PackageChange: ...
async def update_package(settings: Settings, package_id: str, target_version: str, expected_package_token: str) -> SoftwarePackage: ...
async def uninstall_package(settings: Settings, package_id: str, expected_package_token: str) -> SoftwarePackage: ...
@asynccontextmanager
async def maintain_package(package_id: str) -> AsyncIterator[None]: ...
# nodes.public；复用B41准确差异/包定义替换
def preview_definition_update(workspace: Path, definition: NodeDefinition, expected_content_token: str, operation: SoftwareOperation) -> DefinitionChange: ...
def update_definition(workspace: Path, change: DefinitionChange) -> SavedDefinition: ...
def replace_package_definitions(workspace: Path, package_id: str, definitions: list[NodeDefinition], expected_tokens: dict[UUID, str]) -> list[DefinitionWriteResult]: ...
# workflows.public
ObservePrompt = Callable[[UUID], Awaitable[JsonObject]]
ApplyFileChange = Callable[[NativeWorkflowChange], Awaitable[NativeWorkflowChangeResult]]
def find_definition_usage(database: Database, settings: Settings, definition_id: UUID, pages: Sequence[PageObservation]) -> list[WorkflowImpact]: ...
def preview_workflow_change(database: Database, settings: Settings, change: WorkflowChange, pages: Sequence[PageObservation]) -> WorkflowChangePreview: ...
async def apply_workflow_change(database: Database, settings: Settings, change: WorkflowChange, preview: WorkflowChangePreview, apply_file_change: ApplyFileChange, *, operation_id: UUID, pages: dict[UUID, PageObservation], permits: dict[str, FileWritePermit]) -> list[WorkflowChangeResult]: ...
# B53已首次实现，本卡消费/回归
async def get_implementation_usage(database: Database, settings: Settings, query_prompt: ObservePrompt, *, package_ids: list[str], definition_ids: list[UUID]) -> list[RunImplementationUse]: ...
# interfaces/comfyui.py
async def apply_file_change(client: "AsyncClient", change: NativeWorkflowChange) -> NativeWorkflowChangeResult: ...
async def receive_workflow_change(server: "PromptServer", request: "Request") -> "Response": ...
# app内B32已有闭包增量，不让③④反向依赖⑤
async def request_software_action(package_id: str, action: SoftwareActionKind, body: SoftwareInstallRequest | SoftwareUpdateRequest | SoftwareUninstallRequest) -> PendingSoftwareAction: ...
async def confirm_software_action(body: ConfirmSoftwareEvent, *, page_id: UUID, page_token: str) -> PendingSoftwareAction: ...
async def execute_software_action(package_id: str, operation_id: UUID) -> PackageMutationResult: ...
async def get_node_details(definition_id: UUID, *, database: Database, settings: Settings, native_client: "AsyncClient") -> NodeDetails: ...
```

公开POST `/software/packages/{package_id}/update-preview|update|uninstall`与`/nodes/{definition_id}/update-preview|update`按[③④HTTP契约](../../api/platform-contracts.md#software-design)映射；package动作先202待真实网页确认，不因GET/link/Agent布尔开始。Python/TS更新及卸载方法按下面[④准确客户端](../../api/platform-contracts.md#python-clients)实现，不从既有命名惯例推测。内部唯一POST engine `/astrophotoflow/internal/workflow-change`→receive_workflow_change；不进浏览器代理或MCP。app.get_node_details调用B42实际read_node_loads，不把JSON token充load token。

```python
def preview_software_update(self, package_id: str, target_version: str) -> PackageUpdatePreviewResult: ...
def update_software(self, package_id: str, body: SoftwareUpdateRequest) -> PendingSoftwareAction: ...
def uninstall_software(self, package_id: str, body: SoftwareUninstallRequest) -> PendingSoftwareAction: ...
def preview_node_update(self, definition: NodeDefinition, operation_version: str, expected_content_token: str) -> NodeUpdatePreviewResult: ...
def update_node(self, definition: NodeDefinition, operation_version: str, expected_content_token: str, impact_token: str) -> NodeUpdateResult: ...
```

```typescript
previewUpdate(packageId: string, targetVersion: string): Promise<PackageUpdatePreviewResult>
requestUpdate(packageId: string, body: SoftwareUpdateRequest): Promise<PendingSoftwareAction>
requestUninstall(packageId: string, body: SoftwareUninstallRequest): Promise<PendingSoftwareAction>
previewUpdate(body: { definition: NodeDefinition; operation_version: string; expected_content_token: string }): Promise<NodeUpdatePreviewResult>
update(body: { definition: NodeDefinition; operation_version: string; expected_content_token: string; impact_token: string }): Promise<NodeUpdateResult>
```

Python前三个归SoftwareOperations、后两个归NodeOperations；TS前三个归SoftwareClient、后两个归NodesClient，随既有工厂增量。B32没有⑤真实影响时未发布卸载，本卡首次打通请求→具体计划→网页确认→实际卸载/逐图缺失提示，不返回空impact。接口前缀统一 `/api/v1`，包动作返202，节点更新前后事实按④。

**6. 四步。** ①只读准确包/定义before/after及全部关联保存图/已知页面草稿，复用PortRemap，形成影响校验/阻塞run；②请求当前动作/真实网页确认后在既有maintain_package/定义准入段再核包、定义、图/草稿、get_implementation_usage，busy/unknown拒绝且不排稍后；③所属模块写软件/定义、⑤逐图重新核bytes/批准范围/同步，构造允许APF变更的json_text一次，签发permit，ApplyFileChange→固定内部引擎route→原生自身userdata POST原UTF-8正文→B51最终guard→file-finished，无活动页也可；④真实load与逐图结果反馈UI/客户端/测试，需显式重启则先释放维护动作再调用①，不在自身占用内restart。

参数/连线规则：custom所有实例参数用新版默认；package只把变化参数改新默认；同方向同名同类型（含仅重排）保线，改名/改类型/删除断对应线，新增不自连；包删节点/卸载保节点缺失提示。已固定实现和旧运行事实不修改。跨定义/软件/图不是分布式事务：已写部分保留，首失败不自动继续未尝试项，不假回滚。

**7. 禁止/保持。** 不直接Path.write_text保存图、不虚构page_id、不为维护授普通Agent后台编辑、不建headless编辑器/第二转换器；无跨文件原子回滚/长期多版类/自动更新队列；变更/新草稿使旧计划失效，不覆盖；许可准备不因精简省略；原件和自制定义保持。

**8. 测试。** 两项目各图含同定义，custom参数全默认和端口重排/改名/类型/删除/新增；package只变化默认、缺失节点保留；preparing尚未固定binding、queued、顶层failed但call unknown皆阻替换；预览后新草稿/bytes/定义变化409零本次写；关闭文件无活动页可经userdata真实写；第一图成功第二图失败逐项事实，不重写第一图；保存成功load旧token显示未就绪。执行：

```powershell
uv run --locked --no-sync pytest tests/modules/software/test_service.py tests/modules/nodes/test_service.py tests/modules/workflows/test_service.py tests/modules/workflows/test_runs.py tests/integration/test_platform_workflow.py tests/interfaces/comfyui/test_proxy.py -q
pnpm --dir frontend test:unit src/platform/astrophotoflow/workflowBridge.test.ts src/platform/workflow/management/stores/workflowStore.test.ts
node tests/browser/platform-workflows.mjs
```

G09真实证明未打开图/实际userdata最终guard/写成关联失败和部分失败；G04实际load条件沿已锁结论，不用fake loaded通过。

**9. Ready/证据。** 上游/G09阻塞；公开关键签名已有，内部仅写上述真实步骤，不新helper架构。维护窗口共享固定runtime的原型遵守已确认隔离/维护窗口约定：验证结束恢复原正常dev状态并记录，不能把重建/重启正常dev当随意开发步骤。证据含确认计划、old/new token/bytes、affected图/端口差异、实际load、逐图file/association结果、在途阻塞/无自动重试。整卡集成与用户M5验收分记。

<a id="b56"></a>

## B56 — 派生能力目录与本地混合Top10

状态：G10只读资源预检进行中；B56尚未Ready。固定模型／后端／资源选择、下载／许可及本地运行benchmark未完成；完整目录仍依赖B43／B52／B54真实能力入口。

**1. 目标。** `codex/capability-catalog-search`。目录由真实业务/④节点/③操作派生；已知能力直接get，未知才keyword+固定本地embedding检索最多10候选，完整定义按需读；模型故障显式keyword及原因，恢复据实hybrid。A56-1～3 / V18 / G10。

**2. 必读。** [统一工具发现FR-07](../../../../requirements/README.md#tool-discovery)、[⑤数据目录边界](../../architecture/data-models/05-workflows.md)、[目录类型/公开面/Schema闭包](../../api/platform-contracts.md#mcp-design)、[①固定资源边界](../../../../../src/astrophotoflow/core/README.md)。重点读④“目录类型和具名入口”“可独立解释schema及最小$defs闭包”和[固定ID映射](../../api/platform-contracts.md#capability-dispatch)；[既有资源定位/固定runtime](../../../../../src/astrophotoflow/core/workbench.py)与项目锁文件只读核对。

**3. 前置。** B12可先起G10原型；完整目录依B43/B52/B54真实入口，数据58集合沿契约第8节，B57才更换MCP注册。**固定模型/后端/资源来源/版本/许可/实际运行组合未选定前，不编写通用embedding层或新增依赖。** 有资源/依赖取舍按原计划给用户选择；原型/选择后回填第9项明确内容再Ready。

**4. 文件表。**

| 路径 | N/M/R与职责 | 依赖/边界 |
|---|---|---|
| `src/astrophotoflow/contracts/workflows.py` | M：既定CapabilityKind/Summary/Definition/Search联合 | 引用③④最终定义，无重复summary/可编辑目录 |
| `src/astrophotoflow/modules/workflows/public.py`、`src/astrophotoflow/modules/workflows/routes.py` | M：两个领域纯查询、keyword/固定embedding融合与明确降级 | 输入当前真实CapabilityDefinition序列；不反读MCP/导入interfaces |
| `src/astrophotoflow/interfaces/http/app.py` | M：从API/请求模型/固定业务映射与③④public组合目录并传⑤ | 真实Schema+最小传递闭包$defs；不把全部112模型返回 |
| `src/astrophotoflow/core/workbench.py`、`src/astrophotoflow/core/config.py` | R优先；G10已选资源确需共用机制时M最小固定资源定位/采用事实 | 不导入⑤/新资源注册表；本卡禁止预造resources.py/ModelManager；精确资源落位须先回填 |
| `src/astrophotoflow/interfaces/client/workflows.py`、`src/astrophotoflow/client.py`、`src/astrophotoflow/comfyui/proxy.py`、`docs/api/openapi.json` | M：两个具名GET与组合/代理/实际快照 | 不泛化客户端URL/method/函数调用 |
| `tests/modules/workflows/test_service.py`、`tests/integration/test_client_operations.py`、`tests/interfaces/comfyui/test_proxy.py`、`tests/integration/test_platform_workflow.py` | M：目录来源/闭包/Top10/降级和真实模型记录 | 单元fixture不证明检索质量/资源占用 |
| `pyproject.toml`、`uv.lock` | R；仅G10选定真实后端且现有依赖不足，经已确认选择才M精确依赖 | 不默认新增向量库/多模型包，不更新无关锁项 |

**5. 完整签名/公开面。**

```python
# workflows.public：仅这两个必要函数，不建CatalogService
def search_capabilities(capabilities: Sequence[CapabilityDefinition], settings: Settings, query: str, *, kind: CapabilityKind | None = None, source: str | None = None) -> CapabilitySearch: ...
def get_capability(capabilities: Sequence[CapabilityDefinition], kind: CapabilityKind, capability_id: str) -> CapabilityDefinition: ...
# AssetClient组成的具名方法
def search_capabilities(self, query: str, *, kind: CapabilityKind | None = None, source: str | None = None) -> CapabilitySearch: ...
def get_capability(self, kind: CapabilityKind, capability_id: str) -> CapabilityDefinition: ...
```

GET `/api/v1/capabilities/search?query=...&kind=...&source=...`及GET `/api/v1/capabilities/{kind}/{capability_id}`，search路由先于动态路由。app从真实模型/固定映射供给CapabilityDefinition，节点/操作仅返回定义不可直接call。来源/ready/reason来自所属模块当前事实；不从定义存在推就绪。既有 `/capabilities`原服务能力清单语义保持，不能不经说明改成新搜索返回。

**6. 三步。** ①G10只读比较候选并锁定一套固定模型/后端及准确资源，再细化必要共用入口（仅确需时）；②真实目录按种类/来源派生，Tool模型schema携完整最小$defs闭包，get精确返回，不全文索引科学原件/偏好；③keyword+embedding融合/Top10与明确降级、定义变化重建相关派生项，后端/模型不可用不静默换模型；测中文/英文/准确术语/相似词，记录真实数据规模/硬件/时延/内存，不造门槛。B57才能发布三工具。

**7. 禁止/保持。** 不建能力身份/作者/角色/版权体系、目录编辑表、向量数据库、模型多后端插件、生成式推理/聊天或个人偏好向量化；不把software_operation当任意MCP直接执行；已知Skill直达不强制先search；不编rank分数/性能数字；无无限候选默认分页替代Top10。

**8. 测试。** F-CATALOG真实58业务+已实现新增操作+节点/软件操作分型；kind/source筛选准确；get返回的schema所有$ref可独立解析，仅本次闭包；中文/英文查询≤10；模型不可用keyword+具体原因，恢复后hybrid；节点定义改内容派生项更新且不改权威；无偏好/原件进入索引。执行：

```powershell
uv run --locked --no-sync pytest tests/modules/workflows/test_service.py tests/integration/test_client_operations.py tests/interfaces/comfyui/test_proxy.py -q
```

G10真实固定模型benchmark只在隔离/已确认资源环境；原型命令必须在模型/后端选定后写成准确命令并记录，当前不能编一个不存在的benchmark CLI。仅目录单元通过不等检索质量已验。

**9. Ready/阻塞与证据。** G10资源预检见`.artifacts/implementation/G10/model-preflight.json`及[验证矩阵](../../../../development/test-matrix.md#demo-b31-probe)：两项官方候选已有固定revision／权重SHA／许可证及本地依赖环境事实，但尚未选定或下载、未运行。**仍需用户选择唯一模型和接受资源来源／许可证；随后用授权隔离资源环境复测并记录完整后端版本、实际资源目录、必要依赖／准确入口／命令。** 不允许Agent自行决定模型、下载权重、变更依赖或发明公共resource API。B43／B52／B54真实能力未完成前，完整B56目录也不得Ready。证据须含真实硬件/候选集/中文英文查询结果、降级与恢复、时延/资源观察；不把模型索引当新业务权威。

<a id="b57"></a>

## B57 — 三MCP入口整体迁移、真实客户端与公共移除闭合

状态：未开工；待确认总计划/前置，满足后才Ready。

**1. 目标。** `codex/mcp-three-entry-migration`。真实stdio tools/list恰三个入口；58数据业务ID完整固定映射且现HTTP/CLI/图像/错误语义保持；①离线本机控制先于在线AssetClient；真实外部客户端在已交回目标完成读材/局部改图/保存/真实运行/预览/选择保存，手改后安静且下次读最新目标。A57-1～4 / V01/18，本卡关闭A54-5与V17公共移除迁移 / G06/G10真实客户端出口。

**2. 必读。** [FR-07/08、统一发现](../../../../requirements/README.md#tool-discovery)、[58完整集合与三入口](../../api/platform-contracts.md#mcp)、[精确工具/客户端签名、错误与Schema](../../api/platform-contracts.md#mcp-design)、[普通移除闭合](../../api/platform-contracts.md#data-design)。R：[当前server](../../../../../src/astrophotoflow/interfaces/mcp/server.py)、[imports/tools](../../../../../src/astrophotoflow/interfaces/mcp/tools/imports.py)、[library/tools](../../../../../src/astrophotoflow/interfaces/mcp/tools/library.py)、[organization/tools](../../../../../src/astrophotoflow/interfaces/mcp/tools/organization.py)、[具名AssetClient](../../../../../src/astrophotoflow/client.py)、[现行Skill](../../../../../.agents/skills/astrophotoflow-library/SKILL.md)、[操作参考](../../../../development/library-agent-tools.md)。

**3. 前置。** B55+B56，M1～M4自身验收记录通过；用户已确认M3/M4交叉同轮分别验收。原58入口保持到本卡一次切换；不能把目录内部开发提前注册第二套工具。新增业务ID已由[④固定映射](../../api/platform-contracts.md#capability-dispatch)确定；用户已确认素材移除HTTP/client/MCP与本卡一次切换，不增过渡工具或兼容分支。

**4. 文件表。**

| 路径 | M/D/R与职责 | 依赖/边界 |
|---|---|---|
| `src/astrophotoflow/interfaces/mcp/server.py` | M：只注册三入口，字面固定业务ID→请求模型→具名client/本机控制，保留结构化错/图像 | 不反射任意函数或接受URL/method/shell/Python |
| `src/astrophotoflow/interfaces/mcp/tools/imports.py`、`src/astrophotoflow/interfaces/mcp/tools/library.py`、`src/astrophotoflow/interfaces/mcp/tools/organization.py` | D：旧注册/别名实现整体移除，原业务能力留具名client | 删除前逐项核58与ImageContent/本机上传语义已迁；不保兼容注册 |
| `src/astrophotoflow/interfaces/mcp/tools/__init__.py` | M或D（若无真实消费者）：去旧注册导出 | 不留空占位注册框架 |
| `src/astrophotoflow/interfaces/client/workflows.py`、`src/astrophotoflow/interfaces/client/software.py`、`src/astrophotoflow/interfaces/client/nodes.py`、`src/astrophotoflow/client.py` | M/R：补齐前序已定具名操作/读取，固定ID只委托它们 | 上传本地Path读取继续在client，不服务任意读path |
| `src/astrophotoflow/core/workbench.py`、`src/astrophotoflow/interfaces/cli/main.py`、`src/astrophotoflow/interfaces/cli/commands.py` | R优先；M仅真实观察缺口：离线foundation分派/结构化输出 | 不新增全局--config，不写默认目标/全局MCP注册 |
| `src/astrophotoflow/contracts/workflows.py` | M：首次落LibraryRemovalPreview/Apply组合DTO | LibraryRemovalScope只引用B24的contracts/trash.py，不重复定义 |
| `src/astrophotoflow/modules/data/public.py` | M：首次导出remove_library_items，保留B24只读preview | 同域实现，不提前重复写SQL |
| `src/astrophotoflow/modules/data/trash.py`、`src/astrophotoflow/interfaces/http/app.py`、`src/astrophotoflow/interfaces/client/library.py`、`src/astrophotoflow/comfyui/proxy.py` | M：接B24公开scope/B54真实find_input_usage，preview闭包+唯一DELETE强校验 | 去原HTTP WriteSession依赖，业务函数自己BEGIN IMMEDIATE；无旧旁路 |
| `frontend/packages/astrophotoflow-ui/src/modules/data/api/contracts.ts`、`frontend/packages/astrophotoflow-ui/src/modules/data/api/client.ts`、`frontend/packages/astrophotoflow-ui/src/modules/data/workspace/Workspace.vue` | M：普通移除预览/必填确认范围/缺失提示 | 与HTTP/client/MCP同卡切换，旧字段缺失422；无silent default |
| `.agents/skills/astrophotoflow-library/SKILL.md`、`docs/development/library-agent-tools.md`、`docs/development/workbench.md`、`docs/api/README.md`、`docs/api/openapi.json`、`README.md` | M：真实新调用/重连刷新/离线控制及实际HTTP事实 | 只改相关说明，不改用户全局注册/默认workspace |
| `tests/integration/test_cli_mcp_protocol.py`、`tests/integration/test_client_operations.py`、`tests/integration/test_platform_workflow.py`、`tests/modules/workflows/test_service.py`、`tests/modules/workflows/test_runs.py`、`tests/modules/data/test_service.py`、`tests/interfaces/comfyui/test_proxy.py`、`tests/browser/platform-workflows.mjs` | M：exact3/58/错误/图像/离线/真实外部客户端与公共移除 | 同一P/E文件增量，不建MCP兼容测试双轨 |

**5. 完整签名与固定映射。**

```python
from mcp.types import CallToolResult
def search_capabilities(query: str, kind: CapabilityKind | None = None, source: str | None = None) -> CallToolResult: ...
def get_capability(kind: CapabilityKind, id: str) -> CallToolResult: ...
def call_capability(id: str, arguments: dict[str, JsonValue]) -> CallToolResult: ...
# app内两个具名组合闭包；本卡首次实现
def preview_library_removal_for_client(body: LibraryEntriesRemove) -> LibraryRemovalPreview: ...
def remove_library_items_for_client(body: LibraryRemovalApply) -> LibraryEntriesRemoveOut: ...
# preview由B24实现；remove本卡首次在data.trash实现并公开，自己进入write_session
def preview_library_removal(database: Database, body: LibraryEntriesRemove) -> LibraryRemovalScope: ...
def remove_library_items(database: Database, body: LibraryEntriesRemove, *, expected_data_token: str, verify_impact: Callable[[LibraryRemovalScope], None]) -> LibraryEntriesRemoveOut: ...
```

完整既定⑤AssetClient检查表（应前序随真实HTTP落位，本卡只核齐，不再实现另一套调用）：

```python
def list_workflows(self, project_id: UUID, *, limit: int = 50, offset: int = 0) -> WorkflowPage: ...
def get_agent_context(self) -> AgentContext: ...
def get_workflow(self, workflow_id: UUID) -> WorkflowDetail: ...
def edit_workflow(self, body: EditRequest) -> EditResult: ...
def save_workflow(self, guard: WorkflowGuard) -> SaveResult: ...
def replace_workflow(self, body: ReplaceRequest) -> ReplaceResult: ...
def submit_run(self, body: RunSubmit) -> RunDetail: ...
def get_run(self, run_id: UUID) -> RunDetail: ...
def list_workflow_runs(self, workflow_id: UUID, *, limit: int = 50, offset: int = 0) -> RunPage: ...
def cancel_run(self, run_id: UUID) -> CancelResult: ...
def list_run_previews(self, run_id: UUID) -> list[PreviewSummary]: ...
def read_run_preview(self, run_id: UUID, preview_id: UUID) -> bytes: ...
def save_run_output(self, run_id: UUID, body: SaveOutput) -> OutputSaveResult: ...
def find_saved_output(self, asset_version_id: UUID) -> OutputLocator | None: ...
```

原58项迁移子集精确按[④唯一迁移清单](../../api/platform-contracts.md#mcp)：导入10、素材/集合18、恢复/预览6、项目12、设备/预设12；ID为`data.<原工具名>`，集合完全相等（不只计数58）。新增业务ID（含3项新增data.*）只用[④唯一固定表](../../api/platform-contracts.md#capability-dispatch)，不据路径临时命名；foundation.start/status/stop/restart及其已知定义在构造在线AssetClient前本机分派。search/get返回完整定义不执行；node/software_operation不可call。业务错用`CallToolResult(is_error=True, structured_content=真实envelope, content=[TextContent(...)])`保留code/fields/request_id，不用ToolError(str(exc))抹字段；传输断连只报unknown，不造request_id。图像为真实bytes编码ImageContent，非URL或JSON字符串。SDK无output_schema注册参数。

本卡同步修改LibraryOperations两个准确方法（[④客户端](../../api/platform-contracts.md#python-clients)）：

```python
def preview_library_removal(self, body: LibraryEntriesRemove) -> LibraryRemovalPreview: ...
def remove_library_items(self, body: LibraryRemovalApply) -> dict[str, Any]: ...
```

Any仅保留现有客户端返回注解，不进入新DTO；前者POST `/api/v1/library/items/removal-preview`，后者唯一DELETE `/api/v1/library/items`。两handler均在data/trash.py：新preview薄委托app preview闭包；现有remove_library_entries改收LibraryRemovalApply/Request并薄委托remove闭包，去原HTTP WriteSession以免嵌套事务。data中只留新公开函数这一条移除写SQL，旧handler不保旁路。UI沿同一assetApi.send，先用LibraryEntriesRemove取真实preview，再将实际data_token/removal_fingerprint与原items送DELETE，不能自填空影响或静默默认。扩展前端Zod/client及真实OpenAPI与MCP在同卡切换。

**6. 四步。** ①逐项核固定ID/实际请求schema/具名方法/返回形态，并写原58迁移子集与新增固定ID集合／闭包schema测试；旧register暂保工作，内部目录不双注册；②三入口和本机离线分派一次切换、同时移除旧注册文件和别名，保持现有HTTP/CLI/客户端多阶段上传；③按已确认边界，同卡发布preview与扩展DELETE/client/Zod/GUI/MCP字段：data scope→⑤find_input_usage→指纹；DELETE在data实际write_session中重建scope/verify影响/原检查，旧payload422，图节点保留缺失提示。永久unlink保护仍B53且本卡回归；④Skill/参考/配置说明同步，真实客户端刷新/重连后手动+Agent完整链/安静接续，查询不恢复控制，不修改全局注册。

**7. 禁止/保持。** 不保留旧58同名注册/兼容别名/双轨schema；不把import_photo(s)变成服务任意路径；不开放任意URL/method/shell/Python；不新增客户端身份平台/内置推理/自动唤醒；requires_confirmation仅说明，真正确认仍所属业务核验；普通请求不能自填origin或confirmed；主数据原件/默认workspace不变；B57前不提前改变现有HTTP/client/MCP移除语义，本卡一次切换不保旁路。

**8. 测试/真实验收。** 真实stdio tools/list集合精确三个；原58项data迁移子集精确相等，新增3项data.*另与④固定表精确相等且全部get schema引用闭合；结构化revision冲突保code/fields/request_id；display/run图像为ImageContent；HTTP离线foundation.status/start先于在线client可工作，定向目标不改默认/W2；local import仍batch→PUT→start；真实外部客户端刷新后在绑定A选材/edit/save/run/read/save一个完整成员，拖图手改后安静，下次read实际目标/同步/控制，无网页只查工作流事实但②③非画布规则保留；新客户端不能恢复撤销写权；公共移除旧payload422/新指纹冲突409、无写旁路。执行：

```powershell
uv run --locked --no-sync pytest tests/integration/test_cli_mcp_protocol.py tests/integration/test_client_operations.py tests/integration/test_platform_workflow.py tests/modules/workflows/test_service.py tests/modules/workflows/test_runs.py tests/modules/data/test_service.py tests/interfaces/comfyui/test_proxy.py tests/architecture/test_import_boundaries.py -q
node tests/browser/platform-workflows.mjs
```

真实MCP客户端使用隔离workspace的明确环境定位，不修改机器全局注册；用户客户端实际操作/截图/工具结果另记，不以Mock tools/list或58个数据工具单独代签M5科学闭环。

**9. Ready/完成。** 上游/M1～M4自身验收及真实协议/客户端原型为阻塞；第四阶段具名客户端与含新增data项的固定业务ID表已齐，素材移除B57一次切换已获确认。完成证据：exact3／原58迁移子集／新增固定ID列表、全部实际schema/方法映射核对、脱敏真实协议/图像/错误、客户端刷新记录、离线启动和W2/默认保持、完整科学链run/prompt/call/output/task/asset、无网页/手改后接续及限制。B57整卡集成后交用户M5真实验收/批准，未批准不进入依赖该验收的M6。
