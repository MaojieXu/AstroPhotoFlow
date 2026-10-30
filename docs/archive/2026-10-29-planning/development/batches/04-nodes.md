> 历史设计参考（2026-10-29退出现行计划）。签名、状态和任务顺序可能过时；不能直接据此实施。当前任务见 [当前计划](../../../../development/implementation-plan.md)。

# M4任务卡：节点构建与原生加载

2026-10-29：本轮 M3 按用户要求提前接通一个固定 Siril Auto Stretch V3 节点，控件读取包／workspace JSON，使用原生节点注册与队列；新增测试未执行。该窄接入不等于 B42 通用定义加载／确认更新或 B43 编辑器已完成，详见[本轮 M3](03-software.md)。


本文件落实[近期总计划](../implementation-plan.md#m4)，不另定义协议。文件路径均相对仓库根；N＝本卡新增，M＝修改既有或前置卡创建的文件，R＝只复用。当前③④业务/UI仍待实现，M不代表文件今天存在；不先建空实现。每卡先读根及所改作用域AGENTS。

状态：B41进行中，B42／B43未开工；前置及总计划条件按卡检查，自动集成与Milestone人工批准分记。M3/M4按真实Batch依赖交叉实施，同轮分别用户批准，不建立彼此整M批准循环。共享HTTP仅复用B13窄移的同一实现。工作目录/工具和共享runtime恢复按[验证环境](../implementation-plan.md#validation-environment)，用户真实操作/批准按[人工验收门](../implementation-plan.md#acceptance-gates)；tmp_path单元无需停dev，本轮不操作环境。

<a id="b41"></a>

## B41：唯一JSON节点定义与六个public函数

状态：通过（本地`demo`候选）；④定义契约、JSON文件CRUD／token／替换及定向测试已实现，9项节点测试与6项架构测试通过，GPT-6.1 Sol Low独立审查无剩余问题。未集成dev；M4 Milestone人工验收待B42／B43同轮完成后进行。证据见[验证矩阵](../../../../development/test-matrix.md#demo-b31-probe)。

### 1. 目标与可观察结果

分支 codex/node-definitions。workspace/nodes/{definition_id}.json是④唯一可编辑定义；能读取、首次创建、预览差异、准确替换单定义和软件包定义。绑定准确B31操作，端口/参数映射内嵌。此卡仅④JSON公开业务，不发布NodeDetails HTTP/客户端，首次真实HTTP组合归B42。

### 2. 必读依据

[FR-16](../../../../requirements/README.md#fr-16-节点构建测试保存与更新)、AT-03/29、[④节点信息](../../architecture/data-models/04-nodes.md#节点需要哪些信息)、[④使用](../../architecture/data-models/04-nodes.md#从制作到使用)、[④概要](../../../../../src/astrophotoflow/modules/nodes/README.md)、[④精确类型／六函数／副作用](../../api/platform-contracts.md#nodes-design)。读contracts、nodes及software局部AGENTS。差异规则严格使用④，不能另发明端口兼容策略。

### 3. 前置与运行依赖

B31、B22；B31准确操作和维护包已锁定。无需实际⑤运行或测试通过，不以许可/operation.ready=false阻止保存。B41先供B32软件安装组合写包定义，再由B42加载，不等待M3全部人工批准而形成循环。

### 4. 文件与职责／依赖

| 路径 | N/M/R | 本卡职责与依赖 |
|---|---|---|
| `src/astrophotoflow/contracts/nodes.py` | N | NodeDefinition/SavedDefinition/DefinitionChange/PortRemap/DefinitionWriteResult等④DTO；引用contracts.software.ParameterDefinition等唯一模型。 |
| `src/astrophotoflow/modules/nodes/public.py` | N | 六函数直接管理唯一JSON与必要纯绑定/remap；不预拆service/repository/manager。 |
| `src/astrophotoflow/contracts/common.py`、`src/astrophotoflow/contracts/software.py`、`src/astrophotoflow/contracts/inputs.py` | R | StrictModel/UUID/JsonObject、准确参数定义/科学类型；不复制schema。 |
| `src/astrophotoflow/modules/software/public.py` | R | 由app/明确调用方读取准确SoftwareOperation后传入④；③不反向调用④。 |
| `tests/modules/nodes/test_service.py` | N | JSON、绑定、token、首次创建、方向/名称/类型重排与包替换的行为测试；后续卡增量。 |
| `tests/architecture/test_import_boundaries.py` | M | 实际④实现出现后补消费公开入口／禁止④→⑤和私有ORM规则，不造通用检查框架。 |

### 5. 完整关键签名与调用关系

~~~python
def list_definitions(workspace: Path) -> list[SavedDefinition]: ...
def get_definition(workspace: Path, definition_id: UUID) -> SavedDefinition: ...
def create_definition(workspace: Path, definition: NodeDefinition, operation: SoftwareOperation) -> SavedDefinition: ...
def preview_definition_update(workspace: Path, definition: NodeDefinition, expected_content_token: str, operation: SoftwareOperation) -> DefinitionChange: ...
def update_definition(workspace: Path, change: DefinitionChange) -> SavedDefinition: ...
def replace_package_definitions(workspace: Path, package_id: str, definitions: list[NodeDefinition], expected_tokens: dict[UUID, str]) -> list[DefinitionWriteResult]: ...
~~~

首次创建：调用方生成UUID→准确operation→create_definition核绑定→exclusive写一个JSON→SavedDefinition。preview只读旧token/候选operation返回DefinitionChange，不写文件；update_definition只由已核影响和在途使用的装配后调用，写前重核before token。公开维护入口在B55，不能让B41直接API绕过影响确认。

native_type稳定APF_{definition_id.hex}。content_token按完整模型JSON排序对象键、保留数组次序、UTF-8紧凑序列化SHA-256。不是版本库。输入名和输出名各自唯一；参数与数据输入不占同一原生键，也不能占内部apf_execution_token。定义不含项目素材、路径、凭据。

### 6. 有序实施步骤

1. 从④落DTO，只支持SoftwareBinding；Python/复合请求明确不支持。
2. 实现只读list/get、exclusive create、稳定native_type/content_token；损坏文件明确失败，不跳过、不伪报loaded。
3. 实现preview_definition_update：输入/输出分方向按同名同类型映射，纯重排保线；改名/类型/删除仅断对应端口；新增不自动连。custom实例参数规则为全用新默认。
4. 实现update_definition临时文件替换及写前token冲突；不保旧版。此public供未来真实确认装配，不立即加路由。
5. 实现replace_package_definitions：只改该包package定义，不碰custom；完整旧ID→token在首写前核对，先增改后删；首文件失败停止，逐项真实返回，不回滚。
6. 回归纯函数/文件行为与依赖边界；交B32真实包定义写入，交B42真实加载。无假NodeDetails、无加载或测试callback。

### 7. 禁改及保持

不建节点表、发布/激活/测试历史库、项目节点草稿、旧版并存、Protocol或代码执行环境。不引入nodes→workflows或nodes→interfaces；不发布未接真的节点HTTP，不将保存等同加载/ready。保留原生节点系统和任意第三方命名，唯一名规则只适用于本平台自建定义。

### 8. 测试文件、命令与输入／预期

~~~powershell
uv run --locked --no-sync pytest tests/modules/nodes/test_service.py tests/architecture -q
~~~

| 输入／操作 | 预期 |
|---|---|
| create→在两张普通原生测试图复用同定义；已有ID再次create；损坏JSON | 唯一JSON和同native_type；409；明确失败不跳过。 |
| 同方向重名、无效binding、参数键冲突；operation.ready=false | 前三者422且无写；真实不ready仍可保存，不伪报可运行。 |
| 端口重排／单独改名／改类型／删除／新增，参数含0/null | remap/断口与④一致；全默认值真实保留，不做旧参数兼容判断。 |
| 旧token更新；package expected_tokens缺旧ID或冲突 | 首次副作用前409。 |
| package批量第二文件失败 | 首项真实已写事实保留，后续不执行；custom不变，不冒充原子回滚。 |

### 9. 完成、证据与Ready阻塞

A41-1～3的定义保存部分，V07/V08的④纯定义部分；P-NODES/E-BOUNDARY。六函数全部有具体输入输出/错误/文件副作用测试，输出差异与精确字段交B42/B55，日志至`.artifacts/implementation/B41/`。不以此关闭真实加载/测试/实例更新。准确operation未定则待前置；本卡不受⑤测试生产者尚未存在的阻塞。

<a id="b42"></a>

## B42：实际白名单注册与首个NodeDetails HTTP

状态：未开工；待确认总计划/前置，满足后才Ready。

### 1. 目标与可观察结果

分支 codex/node-native-loading。一个固定白名单平台包从④真实定义生成原生类，实际registry报告当前/旧token/缺类/未知；数据引用节点APF_DATA_REFERENCE同包注册。首次发布节点列表/详情/创建HTTP及NodeDetails客户端，真实保存、加载、软件就绪分别表达。此卡不证明科学调用成功，调用归B53。

### 2. 必读依据

[④节点HTTP／组合字段](../../api/platform-contracts.md#nodes-design)、[原生文件落点、白名单、实际registry生产者](../../api/platform-contracts.md#native-design)、[④制作到使用](../../architecture/data-models/04-nodes.md#从制作到使用)、[FR-16](../../../../requirements/README.md#fr-16-节点构建测试保存与更新)、[FR-13](../../../../requirements/README.md#fr-13-环境检测安装与恢复)、AT-02／AT-11／AT-29／AT-33；读core、interfaces、nodes、原生engine与宿主AGENTS。

### 3. 前置与运行依赖

B41、B32、B33。B32写入真实配套定义；实际软件/许可ready来自③。B12隔离固定runtime，领域httpx与引擎aiohttp双解释器。G04先验证实际白名单loader、注册marker和明确刷新/重启条件；不默认热加载成功。

### 4. 文件与职责／依赖

| 路径 | N/M/R | 本卡职责与依赖 |
|---|---|---|
| `src/astrophotoflow/interfaces/comfyui.py` | M | register_nodes、read_node_loads、receive_node_loads和register_native有限只读route；引擎不读业务ORM/节点JSON自行猜语义。 |
| `src/astrophotoflow/core/workbench.py` | M | initialize/安装网页资源同处写固定薄引导；启动保留disable-all-custom-nodes并只加whitelist astrophotoflow_nodes。core仅写固定文本，不import接口层。 |
| engine/ComfyUI/nodes.py；engine/ComfyUI/main.py；engine/ComfyUI/comfy/cli_args.py；engine/ComfyUI/folder_paths.py | R | 现loader/白名单/base目录派生；本卡先复用，不因实现方便重写loader。 |
| engine/ComfyUI/server.py | M | 现实际装配处注册有限node-loads路由；只认证/解析/委托，不堆领域业务。 |
| `src/astrophotoflow/contracts/nodes.py`、`src/astrophotoflow/contracts/workflows.py` | M | NativeLoadReport/NativeNodeLoad/NodeDetails等本卡真实响应，保持③④→⑤契约单向关系。 |
| `src/astrophotoflow/modules/nodes/routes.py` | N | GET /nodes、GET /nodes/{id}、POST /nodes薄适配，委托app真实组合。test/update路径等真实消费者后续接通。 |
| `src/astrophotoflow/interfaces/http/app.py` | M | app.get_node_details：④定义＋③真实就绪＋实际read_node_loads，ready/reason唯一生产者；B53之前测试字段事实为null。 |
| `src/astrophotoflow/interfaces/client/nodes.py` | N | NodeOperations的list_nodes/get_node/create_node按[④客户端](../../api/platform-contracts.md#python-clients)精确签名。 |
| `src/astrophotoflow/client.py` | M | 将NodeOperations组合进现有AssetClient。 |
| `frontend/packages/astrophotoflow-ui/src/modules/nodes/api/contracts.ts`、`frontend/packages/astrophotoflow-ui/src/modules/nodes/api/client.ts`、`frontend/packages/astrophotoflow-ui/src/modules/nodes/index.ts` | N | Zod/具名list/get/create，复用B13同源client；不复制原生nodeDef schema。 |
| `frontend/packages/astrophotoflow-ui/src/index.ts`、`src/astrophotoflow/comfyui/proxy.py`、`docs/api/openapi.json` | M | 实际公开导出/白名单/OpenAPI同步。内部node-loads绝不加入公开代理。 |
| `frontend/src/services/litegraphService.ts`、`frontend/src/schemas/nodeDefSchema.ts` | R | 真实ComfyNodeDef导出/registerNodeDef刷新；不另建前端registry。 |
| `tests/modules/nodes/test_service.py`、`tests/interfaces/comfyui/test_proxy.py`、`tests/architecture/test_import_boundaries.py` | M | 实际组合/边界、当前类token、列表创建返回。 |
| `frontend/src/platform/astrophotoflow/workflowBridge.test.ts`、`tests/integration/test_platform_workflow.py` | M | 真实加载与前端定义刷新/受控状态，后者保留实际runtime证据。 |

固定引导仅workspace/comfyui-data/custom_nodes/astrophotoflow_nodes/__init__.py：from astrophotoflow.interfaces.comfyui import register_nodes，然后赋原生两个mapping。这里是运行产物，不能把产品源码生成到workspace、engine/custom_nodes或新增vendor资源。

### 5. 完整关键签名与调用关系

~~~python
def register_nodes() -> tuple[dict[str, type], dict[str, str]]: ...
async def read_node_loads(client: "AsyncClient", definition_ids: Sequence[UUID]) -> NativeLoadReport: ...
async def receive_node_loads(server: "PromptServer", request: "Request") -> "Response": ...
async def get_node_details(definition_id: UUID, *, database: Database, settings: Settings, native_client: "AsyncClient") -> NodeDetails: ...
~~~

register_nodes向受认证领域GET /internal/native/definitions取④实际定义/软件观察，生成原生类并在类上静态保存APF_DEFINITION_ID/APF_CONTENT_TOKEN；原生loader才真正注册。GET engine /astrophotoflow/internal/node-loads按重复definition_id查询实际NODE_CLASS_MAPPINGS，不能从定义文件补token。read_node_loads只适配该固定路由。

NodeDetails.ready由app仅在software_ready、load.loaded且实际类token==当前保存token时为true；其他false及准确reason。查询断连，详情保留定义/软件事实并load=unknown，绝不伪造空report为确定not_loaded。B53之前没有显式测试生产者，latest_test/matches_current_content直接null；不创建假latest_node_test或空callback。B53同次把此组合接真实⑤查询。

~~~typescript
export interface NodesClient {
  list(): Promise<NodeDetails[]>
  get(definitionId: string): Promise<NodeDetails>
  create(body: { definition: NodeDefinition; operation_version: string }): Promise<NodeDetails>
}
export function createNodesClient(fetchApi: FetchApi): NodesClient
~~~

本卡仅添加真实成员；B53/B55分别在同interface追加④既定test和更新成员，不返回假测试/更新实现。Python客户端精确摘录如下：

~~~python
class NodeOperations:
    def list_nodes(self) -> list[NodeDetails]: ...
    def get_node(self, definition_id: UUID) -> NodeDetails: ...
    def create_node(self, definition: NodeDefinition, operation_version: str) -> NodeDetails: ...
~~~

NodeOperations只调用self.request并按DTO校验；不调用software客户端或本机软件，根AssetClient沿现mixin组合。

### 6. 有序实施步骤

1. G04先用真实固定runtime验证base-directory白名单冷启动和领域先ready；记录保存后是否需定义刷新或显式重启。
2. 写固定薄引导和保留禁任意扫描的启动参数；实现register_nodes的已支持类/固定科学引用，不执行软件。
3. 注册实际registry只读node-loads生产者；缺marker为unknown，缺类not_loaded，旧token如实返回旧值。
4. 实现app.get_node_details和三条真实HTTP；POST先④保存，再读实际registry返回；definition_saved/loaded/software_ready不混成保存成败。
5. 接Python/TS具名客户端、Zod、固定代理和OpenAPI；前端定义刷新复用真实registerNodeDef类型，不重造schema。
6. 执行真实四态/缺引用类验证及依赖检查；交B43制作界面和B53预检。明确未支持热刷新，不添加未经验证热加载route。

### 7. 禁改及保持

不增加第二节点包、多版类注册、节点SQLite表或热加载任务队列；不把JSON存在当loaded，不直接导⑤ORM，也不为null测试字段提前建表/空函数。不顶层导入httpx/FastAPI使引擎失效，领域端也不要求安装原生server/aiohttp；不改runtime锁。节点只注册/添加不启动软件。

### 8. 测试文件、命令与输入／预期

~~~powershell
uv run --locked --no-sync pytest tests/modules/nodes/test_service.py tests/interfaces/comfyui/test_proxy.py tests/architecture -q
pnpm --dir frontend exec vitest run src/platform/astrophotoflow/workflowBridge.test.ts src/services/litegraphService.lateRegistration.test.ts
uv run --locked --no-sync pytest tests/integration/test_platform_workflow.py -q
~~~

| 输入／操作 | 预期 |
|---|---|
| 保存定义但registry缺APF类 | saved可读，not_loaded/ready=false，无测试字段为null。 |
| 当前JSON token新、registry实际类token旧 | load报告旧token，ready=false；不能改报新loaded。 |
| 冷启动真实白名单loader注册当前类，③ready | loaded/token准确，ready=true；注册过程无科学处理。 |
| node-loads查询断连／类marker不可识别 | 直接查询503 NATIVE_LOAD_UNKNOWN；组合详情load=unknown/ready=false且保留定义/软件事实。 |
| 固定引用类缺失 | report.data_reference_loaded=false；B53采用此事实阻相关图提交，不猜引用类已注册。 |
| UI刷新迟到注册 | 原生现行为保持；不会自动升级已存在缺失占位实例为已执行新类。 |

### 9. 完成、证据与Ready阻塞

A42-1～3，V07/V13的加载部分，G04；P-NODES/P-HOST/P-INTEGRATION/E-NATIVE。提交真实registry/mapping静态marker、实际版本和white-list参数、冷启动/刷新/重启条件、三HTTP响应与测试日志至`.artifacts/implementation/B42/`。若G04失败或前置不具真实软件/定义，相关项待前置。即使ready=true也不能代签B53真实受控科学调用、B55维护替换或显式测试。

<a id="b43"></a>

## B43：标准节点制作界面与可读绑定

状态：未开工；待确认总计划/前置，满足后才Ready。

### 1. 目标与可观察结果

分支 codex/node-editor。用户在保留的原生节点库／宿主入口创建、查看标准软件操作定义，编辑常用/高级参数和映射，保存后查看真实加载/软件原因并在两张普通原生测试图复用同一workspace定义。正式P/Q项目关联后由B51/B53/B55补实际项目实例更新/测试。保存不以测试通过为门槛。已有实例更新、影响确认和显式测试分别仍由B55/B53接通，不用静态diff代签。

### 2. 必读依据

[④前端/完整NodesClient契约](../../api/platform-contracts.md#file-design)、[④节点字段与更新规则](../../api/platform-contracts.md#nodes-design)、[真实注册及类型](../../api/platform-contracts.md#native-design)、[④制作到使用](../../architecture/data-models/04-nodes.md#从制作到使用)、[④修改规则](../../architecture/data-models/04-nodes.md#修改已有自定义节点)、[FR-16](../../../../requirements/README.md#fr-16-节点构建测试保存与更新)、AT-29。读UI包、nodes和原生桥接局部AGENTS；UI只能经公开导出消费宿主，不能反向import原生单例。

### 3. 前置与运行依赖

B41、B42；B42真实list/get/create已发布，Python客户端签名/代理/OpenAPI一致。B13共享client/error窄移已完成。运行/测试功能无producer时不提供假按钮或假HTTP；保留明确“尚未接通”的阶段记录，M4只验定义制作/显示。

### 4. 文件与职责／依赖

| 路径 | N/M/R | 本卡职责与依赖 |
|---|---|---|
| `frontend/packages/astrophotoflow-ui/src/modules/nodes/NodeEditor.vue` | N | 标准定义表单、常用/高级参数、SoftwareBinding展示和新定义保存；按后端事实显示保存/加载/就绪/最近测试。 |
| `frontend/packages/astrophotoflow-ui/src/modules/nodes/api/contracts.ts`、`frontend/packages/astrophotoflow-ui/src/modules/nodes/api/client.ts`、`frontend/packages/astrophotoflow-ui/src/modules/nodes/index.ts` | M | 复用B42 NodesClient/list/get/create，公开实际组件和DTO；只补真实消费字段，不复制diff权威或原生schema。 |
| `frontend/packages/astrophotoflow-ui/src/modules/software/index.ts` | R | 通过所属模块公开SoftwareClient读取包的node_definition_ids和准确installed_version，不导软件UI内部状态。 |
| `frontend/packages/astrophotoflow-ui/src/core/client.ts` | R | B13共用FetchApi/ApiClientError/createApiClient及fields，不在节点模块复制请求实现。 |
| `frontend/packages/astrophotoflow-ui/src/index.ts` | M | 包根公开NodeEditor/真实客户端/DTO，原生不导UI内路径。 |
| `frontend/src/platform/astrophotoflow/NativeShell.vue`、`frontend/src/platform/astrophotoflow/workflowBridge.ts` | M | 在现宿主装配点挂载/关闭NodeEditor并桥接原生使用；继续保留GraphView和节点库→素材库→工作流顺序，不创建新应用。 |
| `frontend/src/services/litegraphService.ts`、`frontend/src/schemas/nodeDefSchema.ts` | R | 原生定义刷新/注册实际入口，节点交接用真实公开类型和既有Store，业务UI不导入。 |
| `src/astrophotoflow/modules/nodes/public.py` | R | B41 preview_definition_update/remap规则单一权威；本卡不在UI再实现一套参数兼容/端口diff。 |
| `tests/modules/nodes/test_service.py` | M | 若界面发现B41具体回归才补对应pure行为；不新增同一规则第二测试矩阵。 |
| `frontend/src/platform/astrophotoflow/workflowBridge.test.ts`、`tests/browser/platform-workflows.mjs` | M | 制作/新建保存/错误事实和宿主边界的集中可见验证。 |

NodeEditor的具体Vue内部事件不是新HTTP协议；宿主回调必须typed，不能传原生Store到UI或让UI自行推ready。当前精确文档没有规定新增独立NodePanel/EditorStore/制作Wizard文件，本卡不为界面拆出这些层。

### 5. 完整关键签名与调用关系

复用B42已发布签名：

~~~typescript
export interface NodesClient {
  list(): Promise<NodeDetails[]>
  get(definitionId: string): Promise<NodeDetails>
  create(body: { definition: NodeDefinition; operation_version: string }): Promise<NodeDetails>
}
export function createNodesClient(fetchApi: FetchApi): NodesClient
~~~

差异计算只复用④：

~~~python
def preview_definition_update(workspace: Path, definition: NodeDefinition, expected_content_token: str, operation: SoftwareOperation) -> DefinitionChange: ...
~~~

制作起点的真实读取链：SoftwareClient.listPackages/getPackage→包的node_definition_ids及准确installed_version→NodesClient.get→实际SavedDefinition作为首操作配套模板。使用模板形成新的UUID/source=custom草稿，保留可读的准确execution映射供编辑，operation_version取该次明确安装版本；不从名称猜操作或使用不存在的operations字段。

制作保存链：NodeEditor→NodesClient.create→既定POST /nodes→app从③get_operation核对准确operation→④create_definition→真实registry组合→NodeDetails→UI显示。SoftwarePackage本身不返回完整SoftwareOperation，B56前不得新造/software/operations HTTP或假目录来补读取。近期本卡范围就是已选首包配套首操作；其他准确操作的发现沿B56既定能力读取，不增加临时操作接口或改变本卡首操作范围。

更新草稿不等于已更新实例；完整update-preview HTTP/NodeUpdatePreviewResult需要⑤影响生产者，归B55，不在此返回空WorkflowChangePreview。M4的端口差异验收由B41真实函数及测试证明，UI只呈现既定规则，不声称已执行跨图更新。

最近测试在B53前两个字段为null；B53以后本组件直接显示app给的真实latest_test及matches_current_content。没有测试/失败不阻保存；旧结果不标为当前定义通过。

### 6. 有序实施步骤

1. 沿上述包→配套定义链读取B42真实NodeDetails，形成首操作custom新定义表单；只支持首批SoftwareBinding，参数按真实模板的kind/nullable/default/advanced显示。
2. 先贯通list/get/新建保存；表单传唯一NodeDefinition与operation_version，路径身份从正文definition_id派生，不另传可矛盾ID。
3. 显示保存与loaded/ready分离，保留code/fields/requestId；旧类token、缺软件/许可、查询未知各显示准确原因，UI不自己算ready。
4. 经包根导出与NativeShell现装配挂载；实际原生Store/刷新留宿主。验证新定义能在两张普通原生测试图选用，添加不执行软件；本阶段没有正式项目图关联UI。
5. 已有定义可形成编辑草稿；完整确认更新/实例重映射/显式测试等B55/B53消费者出现后在各负责卡追加入口，不在本卡接假按钮/空route。M4记录静态差异与未来边界。
6. 做浏览器和宿主相称验证，按人工M4验收记录使用体验/错误显示；用户批准后才记M4近期自身完成。

### 7. 禁改及保持

不新增节点发布流程、强制测试门槛、旧版选择、参数兼容层、跨项目编辑器状态库、Python/复合环境。UI不读原生Store、数据库或计算软件/加载ready；保持原生画布、撤销、视口、现节点库和侧栏顺序。测试/更新未接不冒充完成，不能因减少按钮前移S6。

### 8. 测试文件、命令与输入／预期

~~~powershell
uv run --locked --no-sync pytest tests/modules/nodes/test_service.py tests/architecture -q
pnpm --dir frontend exec vitest run src/platform/astrophotoflow/workflowBridge.test.ts src/services/litegraphService.lateRegistration.test.ts
pnpm typecheck
uv run --locked --no-sync pnpm check:boundaries
node tests/browser/platform-workflows.mjs
~~~

浏览器沿B32同一测试文件，用隔离APF_WEB_URL；不触正常dev。新增UI若有具体组件回归再加相称测试，不能先复制整个端口矩阵到UI测试。

| 输入／操作 | 预期 |
|---|---|
| 选择准确软件操作，新建常用/高级参数、固定值/映射，含合法0/null | 保存真实定义，各字段/绑定可读，不以未ready/无测试阻保存。 |
| 保存后registry未加载／旧token／③未就绪／查询未知 | 分别显示后端事实，保存不被渲染成执行成功或伪ready。 |
| 同方向端口重排/改名/类型/删除/新增规则 | B41函数结果正确；UI说明参数全新默认与对应断线，不声称已有图已更新。 |
| 在两张普通原生测试图分别添加同一新定义 | 使用同一workspace定义/native_type，添加不触发处理，不复制项目定义；正式P/Q关联待B51，实际测试/更新待B53/B55。 |
| B53前无测试、以后失败或旧内容测试 | 前者null；后者显示真实范围/失败/旧内容，不变为保存门槛。 |
| 开关制作界面/切侧栏 | 画布常驻、顺序/原生节点库/现数据功能保持，无UI→原生禁止依赖。 |

### 9. 完成、证据与Ready阻塞

A43-1～3（定义制作/差异规则部分）、V07/V08的M4自身部分，P-NODES/P-HOST/P-BROWSER/E-BOUNDARY。表单截图、保存/加载/错误响应、两张普通原生图复用证据、测试及类型/边界日志进入`.artifacts/implementation/B43/`。B42 producer不真实或宿主公开连接未闭合时待前置；B53显式测试/B55实例更新继续待联调。M4人工验收必须与M3分别获用户批准，静态diff不代签维护安全。
