> 历史设计参考（2026-10-29退出现行计划）。签名、状态和任务顺序可能过时；不能直接据此实施。当前任务见 [当前计划](../../../../development/implementation-plan.md)。

# M3任务卡：外部软件接入与环境

## 2026-10-29 M3 本地实现候选（未执行测试、未获用户验收）

本条覆盖下文历史记录中 B31 首操作未选、B33 未开工及软件包页面命令目录的对应现状；不覆盖 M4/M5 的其余任务。

- B31：用户授权选择首个 CLI 工具，本轮锁定 Siril 1.4.4 Auto Stretch。单件／固定有序 FITS 组由一次脚本按顺序 load → autostretch → save，原件不作输出；完整文件、数值 0、缺失文件和不支持的指定 HDU 明确处理。199 条命令仍为资料目录，不批量生成可运行节点。
- B32：沿用同一原生 WebSocket 的计划／真实按钮确认，修复 NativePageEvent 联合类型解析。页面只常驻软件名、红绿就绪点和安装／卸载按钮，计划进入原生 Dialog；红点原因可悬停／聚焦查看。新增程序副本卸载接口，确认后只删除 workspace/software/siril/app，保留素材、定义及画布。包状态／节点 token 变化拒绝旧计划，调用及维护繁忙时拒绝。
- B33：software.public 提供 invoke_operation／inspect_operation／cancel_operation／get_usage，保存真实阶段、日志、退出及候选文件。定向终止当前调用的专用进程，发送与实际退出分别返回；未知句柄不猜已停。启动前观察失败不运行，运行后观察失败不自动重算；服务恢复核对已有 PID／创建时间，未知占用继续阻止维护。
- 首节点：interfaces/siril_node.py 注册 V3 的 Siril Auto Stretch（APF_169de0837f814cdea3295541ecacf463），使用 APF_SCIENCE；控件从既有 JSON 定义读取，默认绑定变更明确拒绝。原生队列、停止及输出预览复用，不引入第二执行队列。软件未安装时节点可见，运行明确拒绝；安装后无需为首节点重启。
- 科学交接：data.public.resolve_canvas_inputs 验证固定成员顺序、完整内容哈希及当前资料／设备／校准快照；workflows/software_calls.py 接收仅原生内部调用，固定运行目录、保存必要调用事实并检查输出，输出保持引用，不自动登记为素材。普通网页代理、CLI 和 MCP 不开放直接 Siril 执行路由。
- 边界：当前仅首个固定节点接入；完整 M4 动态节点库／编辑器、M5 项目图关联／SQLite 运行权威及更新影响、Agent 软件入口仍按后续任务实施。提前交付的卸载不改写任何图，不冒充 B55 完整维护影响闭环。必要调用 JSON 与日志位于本次原生 prompt 的 runs/<prompt_id>/，后续完整运行记录接入仍待实现。

编写用例但不运行；已完成 UI 类型检查、原生类型检查及前端生产构建，Python 语法／OpenAPI 导出及隔离 demo-preview 更新证据统一存于 `.artifacts/implementation/m3-software-20261029/`。真实安装、下载、原生图执行／定向停止与视觉质量均待用户验收；不操作浏览器、不开展性能实验，不提交、推送或合并。


本文件落实[近期总计划](../implementation-plan.md#m3)，不另定义协议。文件路径均相对仓库根；N＝本卡新增，M＝修改既有或前置卡创建的文件，R＝只复用。B31已实现只读包查询、版本绑定命令目录和单图原型；B41已实现定义JSON操作；安装、真实调用和原生加载仍待实现。每卡先读根及所改作用域AGENTS。

状态：B31／B32进行中；B33未开始。B41本地候选通过，B42／B43未开始。各卡仍须核对自身前置和Ready条件；自动验证与Milestone人工批准分开记录。M3/M4按真实Batch依赖交叉实施，同轮分别用户批准，不建立彼此整M批准循环。共享HTTP仅复用B13窄移的同一实现。工作目录/工具和共享runtime恢复按[验证环境](../implementation-plan.md#validation-environment)，用户真实操作/批准按[人工验收门](../implementation-plan.md#acceptance-gates)；tmp_path单元无需停dev，本轮不操作环境。

<a id="b31"></a>

## B31：锁定首软件、目录与准确操作

状态：进行中；`demo` 上开展 G02 隔离原型，实际证据和未完成项见[验证矩阵](../../../../development/test-matrix.md#demo-b31-probe)。本卡尚未通过。

用户决定待答：首个Siril操作；同滤镜序列选用官方样例、用户提供素材还是记录缺口。候选参数实验与当前CLI/图像门槛见[验证矩阵](../../../../development/test-matrix.md#demo-b31-probe)。

### 1. 目标与可观察结果

分支 codex/software-first-package。用户选定一个软件的准确来源／版本、一个科学操作、真实测试输入后，查询可得准确维护清单、当前安装／未就绪原因及完整操作定义。查询无安装／运行／登录副作用。至少一次真实原型证明该操作消费完整科学文件并产生可检查产物；有序集合用至少两成员证明一次交接，不能用模拟包代签。

### 2. 必读依据

- [FR-03](../../../../requirements/README.md#fr-03-软件适配与能力目录)、[FR-13](../../../../requirements/README.md#fr-13-环境检测安装与恢复)、AT-02/25/33、[③软件信息](../../architecture/data-models/03-software.md#软件包与必要信息)、[③概要](../../../../../src/astrophotoflow/modules/software/README.md)。
- [④契约③行为](../../api/platform-contracts.md#software)、[③字段／public／HTTP与状态位置](../../api/platform-contracts.md#software-design)、[固定运行调用边界](../../api/platform-contracts.md#native-design)。
- `src/astrophotoflow/AGENTS.md`、`src/astrophotoflow/contracts/AGENTS.md`、`src/astrophotoflow/modules/software/AGENTS.md`、`src/astrophotoflow/interfaces/AGENTS.md`。

### 3. 前置与运行依赖

前置 B12、B22；首软件和版本固定为Siril 1.4.4 CLI，release及portable archive/GPLv3信息已核对，但发布物无可核验校验和／签名。初始操作选择（Auto Stretch仅为已测候选）和同目标同滤镜多成员素材来源仍待用户决定；本地无可用科学序列，故本卡当前不可Ready。正式安装／许可准备归B32用户操作，③正式invoke归B33。隔离workspace使用B12实际ready地址和B22科学文件交接，正常dev数据不参与写入。

### 4. 文件与职责／依赖

| 路径 | N/M/R | 本卡职责与依赖 |
|---|---|---|
| `src/astrophotoflow/contracts/software.py` | N | 从④摘录本卡实际使用的SoftwarePackage／SoftwareOperation／ParameterDefinition／端口及相关DTO；只依赖标准库、Pydantic和contracts。 |
| `src/astrophotoflow/contracts/common.py` | R | 沿StrictModel／UuidInput／JsonObject；不重复公共类型。 |
| `src/astrophotoflow/contracts/inputs.py` | R | 复用B22科学引用／ResolvedInput／选择；不重建另一份文件Schema。 |
| `src/astrophotoflow/modules/software/public.py` | N | 项目维护的已选包／准确操作与配套定义读取；当前软件state.json事实读取。模块只依赖core/contracts，不import节点或工作流实现。 |
| `src/astrophotoflow/modules/software/routes.py` | N | 本卡发布真实包列表与版本绑定只读命令目录；包动作／组合details在B32接通，不建立未实现安装／更新路径。 |
| `src/astrophotoflow/interfaces/http/app.py` | M | 装配真实software路由，沿当前settings／认证，零③④⑤ORM旁写。 |
| `src/astrophotoflow/comfyui/proxy.py` | M | 只加入本卡实际公开查询的固定白名单，沿B12实际采用地址。 |
| `src/astrophotoflow/interfaces/client/software.py` | N | SoftwareOperations真实list查询；get组合详情归B32，无任意URL调用。 |
| `src/astrophotoflow/client.py` | M | 将SoftwareOperations组合进现有AssetClient，保留公开入口。 |
| `scripts/export_openapi.py` | R | 用既有脚本真实导出当前已实现路由。 |
| `docs/api/openapi.json` | M | 保存实际生成快照，不手工伪造实现。 |
| `tests/modules/software/test_service.py` | N | 本卡包／操作查询和真实定义约束；B32/B33继续增量同文件。 |
| `tests/integration/test_platform_workflow.py` | M（B12创建后） | 首软件原型的真实版本／输入输出证据，后续卡复用；不另建软件试验平台。 |

软件当前事实落workspace/software/{package_id}/state.json，专用软件落其app/；清单来源属于已选固定包，不接受客户端下载URL、脚本或任意版本。配套节点原始JSON只由本卡读取，不在software模块写④workspace/nodes文件。

### 5. 完整关键签名与调用关系

以下新增于software/public.py（签名直接按④）：

~~~python
def list_packages(settings: Settings) -> list[SoftwarePackage]: ...
def get_package(settings: Settings, package_id: str) -> SoftwarePackage: ...
def get_command_catalog(package_id: str, version: str) -> list[SirilCommand]: ...
def get_operation(settings: Settings, package_id: str, version: str, operation_id: str) -> SoftwareOperation: ...
def get_bundled_definitions(settings: Settings, package_id: str, version: str) -> list[dict[str, JsonValue]]: ...
~~~

查询链：HTTP认证→software.routes→四个具名public读取→固定清单／当前安装事实→契约响应。get_operation只查准确版本，缺条目404；get_bundled_definitions只返回JSON，不校验成④对象／写定义／加载／运行。app稍后按NodeDefinition.model_validate核对，不让contracts/software.py导入contracts/nodes.py。

Python客户端位于 `src/astrophotoflow/interfaces/client/software.py`，根AssetClient组合此mixin；准确签名亦见[④客户端](../../api/platform-contracts.md#python-clients)：

~~~python
class SoftwareOperations:
    def list_software_packages(self) -> list[SoftwarePackage]: ...
~~~

最终HTTP：GET /api/v1/software/packages返回200 list[SoftwarePackage]；GET /api/v1/software/packages/{package_id}/versions/{version}/commands返回固定包／准确版本的list[SirilCommand]，每条含官方资料与逐命令参数、输入输出、Headless、依赖、风险、定义、registry和CLI证据备注，unknown保持显式；GET包详情的SoftwarePackageDetails组合及get_software_package由B32接入，不临时以SoftwarePackage改变同一路径最终响应。

### 6. 有序实施步骤

1. 记录用户已选包、准确来源／版本、发行条件、操作、格式/HDU／单个或集合、准备／许可方式；首操作必须有本包配套定义可供B32/B42装配和B43制作起点，无证据处保持未支持。
2. 以真实测试素材做G02原型；记录命令或实际API、退出、产物、顺序、限制与原件hash。此原型不是把软件执行开放为MCP工具。
3. 从④落实际DTO，后写四个只读public；准备状态／可用原因来自真实观察，未知百分比为null。
4. 接真实list HTTP／固定代理和已定签名的具名客户端；仅为实际消费者导出契约。保留缺项404、错误code/fields/request_id。
5. 执行相称查询／契约／代理回归并真实导出OpenAPI；把准确支持组合交给B41/B32/B33。

### 7. 禁改及保持

不新增软件会话表、安装计划表、状态历史、多版并存、通用适配器注册或任意执行API。查询不安装／登录／启动处理；③不写④节点文件、⑤运行库或②资产。保留58数据MCP注册和现Skill，本卡不改变它们。

### 8. 测试文件、命令与输入／预期

拟新增测试文件创建后执行，未创建前不可当作已有命令已通过：

~~~powershell
uv run --locked --no-sync pytest tests/modules/software/test_service.py tests/interfaces/comfyui/test_proxy.py -q
uv run --locked --no-sync pytest tests/integration/test_platform_workflow.py -q
uv run --locked --no-sync pytest tests/architecture -q
~~~

| 输入／操作 | 预期 |
|---|---|
| 清单已知包／准确版本；未知包或操作 | 已知返回真实字段；未知404。反复读取不出现软件进程、安装文件或节点写入。 |
| 未安装、缺许可／资源 | 可查询但ready=false，原因准确；不以定义存在推ready。 |
| 任意URL、清单外版本或脚本正文 | 不受理为安装／运行输入；无副作用。 |
| 至少两成员真实有序科学输入及已选HDU | 原型实际一次消费完整顺序，产物可核对；不以显示JPEG／首帧替代科学数据。 |

### 9. 完成、证据与Ready阻塞

A31-1～3；V05/V13；G02的首包／操作部分；P-SOFTWARE/P-INTEGRATION。交接准确软件来源／版本、素材hash、实际调用与产物、支持格式／HDU／集合及停止待验点、测试日志及候选提交/脏差异至`.artifacts/implementation/B31/`。现有停止证据只覆盖真实CLI进程在操作中被强制终止；Siril优雅取消或③调用API取消仍待验证。参数错误原型只覆盖一个不支持选项并观测退出码1。未有同类至少两成员科学运算、首软件操作用户选择、完整支持矩阵或前置候选，相关项不得标Ready／完成。M3最终真实invoke与定向停止由B33，安装网页由B32，配套节点真实加载由B42。

<a id="b32"></a>

## B32：网页具体计划确认后的安装／准备

状态：进行中；G03同一ComfyUI WebSocket页面事件传输候选已落代码和单元测试；安装计划／准备HTTP及SoftwarePanel候选已接通。真实WebSocket／按钮来源／用户确认／下载安装仍未验证；G03未通过前不执行安装。

2026-10-28最新只读runtime复核见`.artifacts/implementation/B32/runtime-reuse-preflight-20261028-1303.json`：当前vendor archive／manifest为`c6c7a476…`，真实用户runtime的`.apf-native-build`仍为旧hash `ec74c9e9…`；此前匹配结论只适用于旧候选。`--reuse-runtime`当前会因marker不匹配而明确失败，普通init会触及共享ComfyUI源码／依赖，因此没有初始化W1或启动共享runtime。G03仍需与当前候选hash匹配且可隔离使用的验证环境。 16:23 UTC只读复核进一步确认用户runtime的server.py hash与archive内candidate不同，详情见.artifacts/implementation/B32/runtime-marker-current-readonly-20261028-1623.json。

13:09 UTC请求的两文件临时runtime切换被sandbox自动审查拒绝：原因是修改workspace以外的共享ComfyUI源码和持久marker，且对这项精确改动缺少可信用户授权。原文件备份及拒绝后hash核对见`.artifacts/implementation/B32/runtime-maintenance-backup-20261028-1305/`和`runtime-write-auto-review-rejection-20261028-1309.json`。未通过其他路径重试；需用户明确授权该精确、可恢复维护操作，或提供marker与当前候选匹配的隔离runtime。

### 1. 目标与可观察结果

分支 codex/software-install-confirmation。请求安装返回202同一待确认计划；用户在真实平台软件页看到准确计划并点击确认后才执行，GET查询当前安装／准备／真实结果。无需活动画布或Agent控制。未确认零软件／定义／图副作用。已有图关联的卸载与更新影响完整闭环归B55，不用空影响放行。

### 2. 必读依据

[③契约及软件动作闭包](../../api/platform-contracts.md#software-design)、[同原生连接／可信确认／双解释器](../../api/platform-contracts.md#native-design)、[UI具名客户端](../../api/platform-contracts.md#file-design)、[③数据设计](../../architecture/data-models/03-software.md)及FR-03／FR-13、AT-25／AT-33。读software/AGENTS、interfaces/AGENTS、UI包/core/software/AGENTS、原生桥接AGENTS及受影响原生文件局部规则。

### 3. 前置与运行依赖

B13、B31、B41。B13已按用户确认完成通用client窄移及fields；B41已提供JSON写入，B32不等M4全部批准。G03必须证明真实按钮来源／socket定向回包；失败阻塞安装出口，不增加confirm HTTP、confirmed:true或另一连接。真实首软件及许可方式来自B31；安全敏感输入由用户直接输入。

### 4. 文件与职责／依赖

| 路径 | N/M/R | 本卡职责与依赖 |
|---|---|---|
| `src/astrophotoflow/contracts/software.py` | M | 实际安装请求、ConfirmSoftwareEvent及本卡安装／准备类型；更新/卸载请求留B55消费者，沿④字段。 |
| `src/astrophotoflow/contracts/workflows.py` | N | 仅实际使用的SoftwarePlanSummary／PendingSoftwareAction／SoftwarePackageDetails／PackageMutationResult及其引用闭包；单向引用③④，不需要⑤ORM或空服务。 |
| `src/astrophotoflow/modules/software/public.py`、`src/astrophotoflow/modules/software/routes.py` | M | install／prepare／本包维护和实际包查询；路由只分派真实能力。已有图卸载／更新确认由B55后接。 |
| `src/astrophotoflow/modules/nodes/public.py` | R | 使用B41 replace_package_definitions写包定义；不由software私写nodes JSON。 |
| `src/astrophotoflow/interfaces/http/app.py` | M | 持每包当前pending／Task／最近结果；四个具名闭包的安装/准备分支；确认后组合③安装与④定义写入，关页不取消已受理动作。 |
| `src/astrophotoflow/interfaces/comfyui.py` | N | 只先落实际WS/page确认转发、有限注册与关闭清理；TYPE_CHECKING和入口局部依赖支持领域/引擎双解释器；不填⑤空动作。 |
| engine/ComfyUI/server.py | M | 当前/ws单reader内有限apf消息分派／关闭钩子；reader不可等待会反向等本socket结果的领域请求。 |
| `frontend/src/scripts/api.ts` | M | 现连接有限apf.page/page_result类型与定向接收，不开第二socket。 |
| `frontend/src/platform/astrophotoflow/workflowBridge.ts` | N | confirmSoftware专用宿主链；page/socket实际状态与回包；不做画布操作或授Agent权。 |
| `frontend/src/platform/astrophotoflow/NativeShell.vue` | M | 安装／卸载当前真实桥接，软件确认链接按既定query打开SoftwarePanel，GraphView继续常驻。 |
| `frontend/packages/astrophotoflow-ui/src/modules/software/SoftwarePanel.vue`、`frontend/packages/astrophotoflow-ui/src/modules/software/api/contracts.ts`、`frontend/packages/astrophotoflow-ui/src/modules/software/api/client.ts`、`frontend/packages/astrophotoflow-ui/src/modules/software/index.ts` | N | 显示计划、安装/准备状态和原因；真实确认调用宿主callback；同源具名HTTP复用B13公共client，不导原生Store。 |
| `frontend/packages/astrophotoflow-ui/src/index.ts` | M | 只导出本卡组件、真实客户端/DTO及所需callback类型。 |
| `src/astrophotoflow/interfaces/client/software.py`、`src/astrophotoflow/client.py`、`src/astrophotoflow/comfyui/proxy.py`、`docs/api/openapi.json` | M | 本卡具名客户端／白名单／实际OpenAPI；不公开内部确认链。 |
| `tests/modules/software/test_service.py`、`tests/interfaces/comfyui/test_proxy.py` | M | 软件动作、确认、部分事实／错误及代理。 |
| `frontend/src/platform/astrophotoflow/workflowBridge.test.ts` | N | 有限确认WS和真实按钮来源；后续同文件增量。 |
| `tests/browser/platform-workflows.mjs` | M（B13创建后） | 真实软件页/确认；唯一跨模块浏览器文件增量。 |

### 5. 完整关键签名与调用关系

新增或扩充 `src/astrophotoflow/modules/software/public.py` 的真实安装/准备能力；`uninstall_package` 连同卸载公开链由B55首次实现：

~~~python
@asynccontextmanager
async def maintain_package(package_id: str) -> AsyncIterator[None]: ...
async def install_package(settings: Settings, package_id: str, version: str, expected_package_token: str) -> SoftwarePackage: ...
async def prepare_package(settings: Settings, package_id: str) -> SoftwarePreparation: ...
~~~

create_app内绑定实际settings/workspace和当前动作的闭包（④完整目标签名；update分支及已有图卸载在B55真实消费者落位时扩展，不先注册假路径）：

~~~python
async def request_software_action(package_id: str, action: SoftwareActionKind, body: SoftwareInstallRequest | SoftwareUpdateRequest | SoftwareUninstallRequest) -> PendingSoftwareAction: ...
def get_software_package_details(package_id: str, *, expected_operation_id: UUID | None = None) -> SoftwarePackageDetails: ...
async def confirm_software_action(body: ConfirmSoftwareEvent, *, page_id: UUID, page_token: str) -> PendingSoftwareAction: ...
async def execute_software_action(package_id: str, operation_id: UUID) -> PackageMutationResult: ...
~~~

薄适配与宿主：

~~~python
def register_native(server: "PromptServer") -> None: ...
async def handle_socket(server: "PromptServer", socket: "WebSocketResponse", message: dict[str, JsonValue]) -> bool: ...
async def forward_page_event(server: "PromptServer", socket: "WebSocketResponse", event: NativePageEvent) -> None: ...
async def socket_closed(server: "PromptServer", socket: "WebSocketResponse") -> None: ...
~~~

~~~typescript
export function confirmSoftware(operationId: string): Promise<PendingSoftwareAction>
export interface SoftwareClient {
  listPackages(): Promise<SoftwarePackage[]>
  getPackage(packageId: string, operationId?: string): Promise<SoftwarePackageDetails>
  requestInstall(packageId: string, body: SoftwareInstallRequest): Promise<PendingSoftwareAction>
  prepare(packageId: string): Promise<SoftwarePreparation>
}
export function createSoftwareClient(fetchApi: FetchApi): SoftwareClient
~~~

上列SoftwareClient只写本卡已发布成员；B55在同一interface加入④既定previewUpdate/requestUpdate/requestUninstall，不创建兼容interface或空方法。Python方法按④python-clients，随真实HTTP落位：

~~~python
class SoftwareOperations:
    def get_software_package(self, package_id: str, *, operation_id: UUID | None = None) -> SoftwarePackageDetails: ...
    def install_software(self, package_id: str, body: SoftwareInstallRequest) -> PendingSoftwareAction: ...
    def prepare_software(self, package_id: str) -> SoftwarePreparation: ...
~~~

B55负责同mixin的preview_software_update/update_software及完整uninstall_software映射；不以客户端直调本机软件代替HTTP。

调用链：POST install→request_software_action→202不可变plan→SoftwarePanel显示同operation_id→真实按钮confirmSoftware→同WS经实际page_id/token→confirm_software_action短准入→maintain_package重核当前plan→唯一Task execute_software_action→③真实安装＋④包定义→GET真实结果。GET、链接、Agent自报confirmed均不能触发副作用。

### 6. 有序实施步骤

1. 先G03小原型证明同socket消息方向、实际连接身份与真实按钮交接；保留feature_flags等原生消息，不新增确认API。
2. 落本卡动作DTO及app具体pending/Task；operation_id下plan不可变，新明确请求只替换未确认当前动作，旧UUID失效。
3. 实现③实际install/prepare和maintain；确认准入后才执行，先成功准入再回running；重复running/completed确认只返现状。
4. app按NodeDefinition.model_validate核对B31配套JSON，以B41 replace_package_definitions写唯一JSON；不把保存成功报告为loaded。B42之前无实际注册事实，不造NativeLoadReport。
5. 接GET详情、POST install/prepare及SoftwarePanel；软件确认target可空，与画布权解耦。已有图更新/卸载完整影响不在本卡发布，B55接线。
6. 安装结束后如实际需重启，先结束本动作/释放busy，显示具体原因，再由①显式生命周期；不自动重启或延后排队。

### 7. 禁改及保持

不新建确认HTTP/CLI/MCP工具，不接受自报human/confirmed；不引入审批账本／软件任务表／第二WS／第三服务；不伪造空图影响。③不import④⑤public，app承担组合。许可正文、密码和验证码不入请求／日志／Agent。部分写入据实报告，不原子回滚、不把关页/响应断连当取消。无新MCP注册。

### 8. 测试文件、命令与输入／预期

~~~powershell
uv run --locked --no-sync pytest tests/modules/software/test_service.py tests/interfaces/comfyui/test_proxy.py tests/architecture -q
pnpm --dir frontend exec vitest run src/platform/astrophotoflow/workflowBridge.test.ts
node tests/browser/platform-workflows.mjs
~~~

浏览器脚本创建后沿现native-web模式用APF_WEB_URL定位本卡新隔离实例实际ready地址；不得填正常dev端口。锁定Node/pnpm按当前开发流程。拟新增脚本尚未创建，命令不是本轮已通过事实。

| 输入／操作 | 预期 |
|---|---|
| POST install后未点击；GET／打开confirmation_url／自填confirmed | 202 awaiting_confirmation，同一plan可读；软件/定义/图零变化；伪确认无效。 |
| 真实软件页同UUID确认，无活动画布 | 进入唯一动作并真实安装；不授予画布权。 |
| 包状态/清单变化、旧UUID、重复确认／响应丢失 | 旧计划409 expired或真实当前事实；不启动第二Task、不自动重播。 |
| 安装成功但节点尚未加载／加载失败 | 保留安装与定义写入事实，明确未加载；不写ready=true。 |
| 页面关闭／需要许可／需要重启 | 已受理动作继续；敏感步骤由用户直输；动作结束后才允许显式重启。 |

### 9. 完成、证据与Ready阻塞

A32-1～4的安装/准备/确认部分；V05及V06包自身部分，G03；P-SOFTWARE/P-HOST/P-BROWSER/E-TRANSPORT。保存同operation_id的提案、真实按钮、实际连接、安装/定义事实及未加载原因；逐项测试、截图、版本/日志进入`.artifacts/implementation/B32/`。G03失败、准确包未选或B13/B41未落位时相关项待前置。已有图的卸载和更新仍待B55，不以本卡通过销项。M3用户通过B33公开入口原型/既有测试脚本检查真实科学输出和日志；此时不提供正式图运行按钮。M3/M4同轮分别批准。

<a id="b33"></a>

## B33：真实软件调用、观察与定向停止

状态：未开工；待确认总计划/前置，满足后才Ready。

### 1. 目标与可观察结果

分支 codex/software-invocation。③在隔离运行目录按准确操作消费B22完整科学输入，报告实际日志、阶段、退出、产物及当前占用；只观察不重跑，定向取消区分请求与真实停止。正式图受控调用由B53接线。M3人工验收运行既定公开入口的原型/测试脚本，用户核实际产物/日志；不为验收新建临时执行HTTP、MCP或UI按钮。

### 2. 必读依据

[③完整调用DTO／public](../../api/platform-contracts.md#software-design)、[inspect_operation及实际停止](../../api/platform-contracts.md#native-design)、[科学输入](../../api/platform-contracts.md#data-design)、[③实际使用](../../architecture/data-models/03-software.md#实际使用)、[FR-03](../../../../requirements/README.md#fr-03-软件适配与能力目录)、[FR-09](../../../../requirements/README.md#fr-09-原生引擎执行与运行记录)、[FR-14](../../../../requirements/README.md#fr-14-本地安全权限与隐私)、AT-13／AT-17／AT-18／AT-26。复读software局部AGENTS及B31已锁定的软件支持记录。

### 3. 前置与运行依赖

B22、B32（包含B31首软件及B41定义依赖）。真实专用软件已安装，许可与所需资源就绪；本卡不可用假工具产物代签。B31原型已给准确输入/输出/参数、至少两成员集合及实际取消能力待验证项。

### 4. 文件与职责／依赖

| 路径 | N/M/R | 本卡职责与依赖 |
|---|---|---|
| `src/astrophotoflow/contracts/software.py` | M | SoftwareInvocation/Observation/Result/CancelResult/Use/ProducedFile，复用inputs.ResolvedInput；不导nodes/workflows。 |
| `src/astrophotoflow/modules/software/public.py` | M | 真实invoke/inspect/cancel/get_usage与已有maintain_package互斥；只保当前句柄，不建调用历史表。 |
| `src/astrophotoflow/modules/data/public.py`、`src/astrophotoflow/modules/data/science_inputs.py` | R | 输入解析只经public；不读②ORM、预览或HTTP handler。 |
| `src/astrophotoflow/core/config.py` | R | 使用B12实际采用settings/workspace和现目录机制，不改默认位置。 |
| `tests/modules/software/test_service.py` | M | 真实调用边界、观察／退出／不支持取消和维护互斥。 |
| `tests/integration/test_platform_workflow.py` | M | 隔离真实首软件、原件hash和产物／集合顺序／停止记录；B53/54增量复用。 |

### 5. 完整关键签名与调用关系

~~~python
async def invoke_operation(settings: Settings, invocation: SoftwareInvocation, observe: Callable[[SoftwareObservation], Awaitable[None]]) -> SoftwareResult: ...
async def inspect_operation(settings: Settings, invocation: SoftwareInvocation, previous: SoftwareObservation | None) -> SoftwareObservation: ...
async def cancel_operation(call_id: UUID) -> SoftwareCancelResult: ...
def get_usage(package_id: str) -> list[SoftwareUse]: ...
@asynccontextmanager
async def maintain_package(package_id: str) -> AsyncIterator[None]: ...
~~~

invoke的输入：已准入的run_id/node_execution_id/call_id、准确包/版本/operation/content_token、dict[str,list[ResolvedInput]]、实际参数及受控work_directory。observe在启动前及真实阶段／终态await；启动前观察记录失败阻止软件调用，已经开始后的记录失败保留真实调用/日志，不重算。③只报告ProducedFile候选；完整科学检查归⑤→②，登记归用户选择后②。

inspect只核对已有调用及previous.runtime_ref的真实证据，不启动／重跑／取消；active=true/false/null与历史结果state分别表达。get_usage内存空不证明服务重启前调用已停。cancel只按call_id句柄，不全局interrupt，不因sent/not_running或失联就释放占用。

### 6. 有序实施步骤

1. 依据B31准确操作实现一次真实调用，核安装版本/许可/参数/科学选择，只写work_directory，原件只读。
2. 在真正启动前报告starting及必要runtime_ref；真实阶段/日志有依据才报告progress；await到真实终态或无法证明的unknown。
3. 按声明输出名/成员顺序记录ProducedFile，不按文件名猜节点/端口，不自动登记或渲染预览。
4. 实现inspect的实际调用恢复定位、active观察；不能恢复则null及原因，不猜空闲/成功。
5. 定向cancel_operation并观察停止；不可停如实not_supported。maintain_package与新invoke互斥，busy拒绝不排自动维护。
6. 用至少两成员真实集合证明一次有序操作，记录部分产物/非零退出/停止证据；移交B42加载定义及B53受控调用，综合⑤持久占用后续B54/B55联调。

### 7. 禁改及保持

无软件执行HTTP/MCP入口、任意path/URL/shell；不让③保存运行权威或反查⑤ORM，不另加会话/调用意图表，不重建队列。不凭HTTP取消/超时/句柄丢失推已停止；不因失败/断连换软件、输入保证或自动重试。首软件不支持某行为就保留限制与阻塞。

### 8. 测试文件、命令与输入／预期

~~~powershell
uv run --locked --no-sync pytest tests/modules/software/test_service.py tests/integration/test_platform_workflow.py tests/architecture -q
~~~

| 输入／操作 | 预期 |
|---|---|
| 实际准确软件＋一文件/至少两成员有序集合＋明确HDU/参数 | 一次真实调用，采用值可核对，产物按声明名/顺序；输入hash不变。 |
| 参数不合操作、版本不符、许可未就绪、非支持科学选择 | 实际调用前明确拒绝，无偷偷强转/替代预览。 |
| 非零退出、部分文件、观察中断 | 不报完整成功；保留真实调用、日志和可知产物，不重算。 |
| A活跃、取消指定B；不可停／句柄丢失／恢复只读观察 | 不误停A；请求/停止分开；无证据active=null，查询不重新调用软件。 |
| maintain与新invoke竞争 | 只允许一侧准入，另一方明确busy；无延后自动任务。 |

### 9. 完成、证据与Ready阻塞

A33-1～4，V13/V15，G02剩余真实调用与停止部分；P-SOFTWARE/P-INTEGRATION。移交准确环境、调用方式/输入hash/参数、实际runtime_ref可恢复边界、日志、退出、完整候选路径（仅内部）和取消观察至`.artifacts/implementation/B33/`。无法证明实际停止时不得写stopped/ready，保留具体限制；⑤持久运行、原生取消聚合与重新启动后占用仍待B54/B55，不由当前空句柄测试代签。
