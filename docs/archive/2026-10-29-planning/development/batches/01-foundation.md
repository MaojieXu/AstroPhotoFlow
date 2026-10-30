> 历史设计参考（2026-10-29退出现行计划）。签名、状态和任务顺序可能过时；不能直接据此实施。当前任务见 [当前计划](../../../../development/implementation-plan.md)。

# M1任务卡：公共基础设施

本文件落实[近期总计划](../implementation-plan.md#m1)，不另定义协议；公开DTO、签名和错误以④为准。文件路径均相对仓库根；N＝计划新增，M＝修改既有，R＝只复用。每卡先读根及所改作用域AGENTS。

M1三卡已组成实现候选；B11→B12→B13依次继承代码，最终候选在`codex/workbench-settings-ui`。验证见[矩阵](../../../../development/test-matrix.md#m1-foundation)，用户人工批准和dev集成仍待完成，不将中间提交当作单卡最终批准。只有总计划获确认、可识别dev基点及本卡真实前置具备后才Ready；Batch自动集成与Milestone用户验收分别记录。测试只在实际文件落位后执行。工作目录/工具及共享runtime维护窗口按[验证环境](../implementation-plan.md#validation-environment)，用户操作/批准按[人工验收门](../implementation-plan.md#acceptance-gates)。维护窗口必须能用原版本入口恢复原dev；tmp_path单元测试无需停止dev。

<a id="b11"></a>

## B11：workspace配置与运行采用值

状态：2026-10-27已获用户开工授权，基点为dev `9d4c729`，在`codex/workbench-config`实施；分支验证／独立审查见验证矩阵。尚未合入dev，不记I(B11)，不代签M1人工验收；A11-3实际端口回写由B12/G01完成。

1. **结果、分支和追踪**：`codex/workbench-config`。默认TOML定位唯一workspace，保存最新值，运行采用值与保存值分开；配置冲突可见。FR-13/14/15；NFR-01/04/07/08；AT-01近期部分。对接A11-1～3、V01/02、G01的配置部分。

2. **必须读**：[需求FR-13](../../../../requirements/README.md#fr-13-环境检测安装与恢复)、[FR-14](../../../../requirements/README.md#fr-14-本地安全权限与隐私)、[①数据§3](../../architecture/data-models/01-foundation.md#3-关键字段与使用规则)、[①精确契约](../../api/platform-contracts.md#foundation-design)。字段只按ConfigValues/ConfigSave/ConfigState及运行信息表，不在卡中复制schema。指定源代码：`src/astrophotoflow/core/config.py`、`src/astrophotoflow/core/workbench.py`、`tests/core/test_config.py`。

3. **前置及Ready**：确认后的dev设计基线。核心契约已定，无首包/模型前置。设计确认和基点未落实前不Ready；真实G01依已确认维护窗口的实际安排，不阻塞tmp_path单元实现。B12负责真实启动采用与端口写回，不由B11再造启动器。

4. **文件级范围**：

| 文件 | 操作／职责 | 依赖 |
|---|---|---|
| `src/astrophotoflow/contracts/workbench.py` | N：新增Config*/BusyState/Workbench*纯DTO；只建本Batch已用类型，后续随消费者增量 | contracts/common.py、Pydantic |
| `src/astrophotoflow/core/config.py` | M：修改Settings增加明确workspace；修改resolve_config_path/load_settings；新增3个公开函数 | pathlib/tomllib、workbench DTO |
| `src/astrophotoflow/core/workbench.py` | M：仅窄接配置新定位，initialize激活写用户默认TOML；不留active-workspace第二权威 | core/config.py |
| `scripts/export_openapi.py` | M：真实Settings构造明确传该脚本隔离workspace；不变更导出协议 | Settings新增必填kw-only字段 |
| `scripts/verify_distribution.py` | M：内嵌smoke脚本的Settings构造明确传测试workspace；发行执行仍归B62 | 保留原7个位置参数 |
| `tests/core/test_config.py` | M：修改既有优先级与多入口测试，新增保存/采用值/冲突断言 | tmp_path、monkeypatch |
| `tests/core/test_workbench.py` | M：仅调整initialize/start所用配置夹具及旧active指针断言 | 新配置定位 |
| `tests/interfaces/comfyui/test_proxy.py` | M：将原来把用户CONFIG_PATH当工作区配置的夹具改为显式环境选择；代理行为不变 | 新默认TOML只保存workspace定位 |
| `tests/modules/data/test_domain_foundation.py` | M：修改显式Settings构造的workspace字段；既有行为不变 | Settings新必要字段 |
| `tests/modules/data/test_service.py` | M：同上，含多处迁移夹具 | M：同上 |
| `tests/modules/data/test_setups.py` | M：同上 | M：同上 |
| `tests/modules/data/test_calibration.py` | M：同上 | M：同上 |
| `tests/modules/data/test_display_previews.py` | M：同上 | M：同上 |
| `tests/modules/data/test_equipment_snapshots.py` | M：同上 | M：同上 |
| `tests/modules/data/test_import_pipeline.py` | M：同上 | M：同上 |
| `tests/modules/data/test_ingestion.py` | M：同上 | M：同上 |
| `tests/integration/test_import_presets.py` | M：同上 | M：同上 |
| `tests/benchmarks/import_pipeline.py` | M：仅调整实际Settings构造；不重构或运行整个benchmark | M：同上 |

5. **准确关键签名（④第11节；新增）**：

```python
def get_configuration(config_path: Path | None = None) -> ConfigState: ...
def save_configuration(config_path: Path, values: ConfigValues, config_token: str, *, default_workspace: Path | None = None) -> ConfigState: ...
def load_running_settings(workspace: Path) -> Settings: ...
```

现有`resolve_config_path(path: Path | None = None) -> Path`、`load_settings(config_path: Path | None = None) -> Settings`保留入口名，调整既定解析。调用链：get/save→唯一配置解析→读/完整替换TOML；load_running_settings只读本次采用记录供B12消费者。core不读业务ORM。

6. **实施顺序及行为**：先DTO和Settings.workspace→显式config/ASTROPHOTOFLOW_CONFIG/用户CONFIG_PATH的workspace.default定位→get/save/token→运行采用值读取→更新全部明确Settings构造。按④保留原7个位置参数，workspace用必填无默认的 `dataclasses.field(kw_only=True)`；load_settings明确传所选配置父目录，测试及上述两个scripts传真实tmp/test workspace，不从data_dir猜值。旧指针不继续读取。默认未设且无明确目标时清楚失败，不自动造workspace；更改默认仅选位置，不搬文件。保存只修改可编辑值，不启动/重启；旧token409，不覆盖新值。默认位置仅显式非空修改，null拒绝。端口回写只由B12就绪后窄写，不覆盖并发新参数；两个文件保存失败报告真实部分事实，不伪事务回滚。

7. **禁止边界**：不加配置历史、workspace注册/搬迁、兼容旧active指针、默认Settings.workspace猜测、第三服务、业务模型；不动正常dev配置/默认指针/令牌；不改迁移历史/锁文件。构造器必需信息显式更新，不以默认值掩旧调用。

8. **验证**：现有先运行`uv run --locked --no-sync pytest tests/core/test_config.py tests/core/test_workbench.py -q`；修改显式构造后运行`uv run --locked --no-sync pytest tests/modules/data/test_domain_foundation.py tests/modules/data/test_service.py tests/modules/data/test_setups.py tests/modules/data/test_calibration.py tests/modules/data/test_display_previews.py tests/modules/data/test_equipment_snapshots.py tests/modules/data/test_import_pipeline.py tests/modules/data/test_ingestion.py tests/integration/test_import_presets.py -q`。使用tmp_path用户TOML、两个workspace和独立data_dir：显式优先于环境，环境优先于workspace.default；改保存并发后采用值不变；改默认不改当前归属；旧token零覆盖；未设默认明确报错。现有`test_config_path_precedence_and_selected_missing_file`、`test_all_entrypoints_share_resolved_settings`须改到新规则。新增断言放同一test_config.py，不建新测试框架。

9. **交付证据**：`.artifacts/implementation/B11/`记录配置优先级、冲突及采用值断言，以及两个scripts/内嵌smoke中Settings构造的定点核对；B13实际导出和B62仓库外smoke继续真实运行，不提前代签。交B12准确ConfigState、Settings.workspace和当前采用文件读法。A11-3真实回写结果须由B12/G01补，B11不能凭配置单元测试关闭整条V01。

<a id="b12"></a>

## B12：结构化启停、实际地址与基础维护准入

状态：B12已实施并完成双工作区真实验收；中间提交`c23e10d`后的独立审查修复包含在最终M1候选中，不能单独把中间提交视为通过。最终独立复核、用户M1操作及dev集成分别登记，当前不记I(B12)。

1. **结果、分支和追踪**：`codex/workbench-lifecycle`。本机可start/status/stop/restart，返回准确双服务地址/状态/最近结果，自动选择被占用端口；现有导入与预览繁忙拒绝重启。FR-13/14；NFR-01/04/06/08；AT-01近期；A12-1～3、V01/02、G01。

2. **必须读**：[FR-13](../../../../requirements/README.md#fr-13-环境检测安装与恢复)、[①数据§3.2～3.3](../../architecture/data-models/01-foundation.md#32-当前运行信息)、[①详设](../../api/platform-contracts.md#foundation-design)。指定源代码：`src/astrophotoflow/core/workbench.py`的_identity/_record/start/status/stop，`src/astrophotoflow/interfaces/http/app.py`的lifespan/shutdown，`src/astrophotoflow/modules/data/ingestion.py`的import_workers/process_task，`src/astrophotoflow/modules/data/previews.py`的DisplayPreviews.schedule。

3. **前置及Ready**：B11集成。未开工；B11基点未定不可Ready。真实G01按用户已确认维护窗口执行：核对并停止全部原共享runtime实例后更新候选资源，再启动隔离W1/W2；候选验完停止W1/W2并恢复原dev状态。不另备VM，不在正常dev仍使用runtime时更新。③⑤尚未实现时只接现有真实②事实，后续B53首次运行即追加，B54补全。

4. **文件级范围**：

| 文件 | 操作／职责 | 依赖 |
|---|---|---|
| `src/astrophotoflow/core/workbench.py` | M：修改4个控制入口、initialize、最新processes/control文件、身份/健康/实际端口/安全回写 | B11、psutil/httpx、现有启动实现 |
| `src/astrophotoflow/interfaces/cli/main.py` | M：修改start/status/stop格式化，新增restart；定向操作不激活默认 | core/workbench结构化结果 |
| `src/astrophotoflow/interfaces/http/cli.py` | M：修改serve采用load_running_settings的固定本次值 | B11 adopted settings |
| `src/astrophotoflow/client.py` | M：修改在线地址选择采用当前运行信息；公开AssetClient入口保留 | B11/B12实际地址 |
| `src/astrophotoflow/comfyui/proxy.py` | M：修改_configuration采用同份运行地址/Origin；不放宽同源与白名单 | adopted settings |
| `src/astrophotoflow/modules/data/public.py` | M：新增导出data_busy；保留现有4导出 | 数据模块内部实际活动 |
| `src/astrophotoflow/modules/data/imports.py` | M：修改接受/启动/恢复/重试任务准入，不能穿越维护 | app显式准入，原WriteSession |
| `src/astrophotoflow/modules/data/previews.py` | M：修改生成准入，保持DisplayPreviews现有排空及缓存保护 | M：同上 |
| `src/astrophotoflow/interfaces/http/app.py` | M：修改组合现有②busy及原生queue观察；内部maintenance enter/release；生命周期不泄漏令牌 | data.public、core，无私有ORM |
| `src/astrophotoflow/contracts/workbench.py` | 扩充已到实际消费者的WorkbenchState/Result/BusyState | ④第11节 |
| `src/astrophotoflow/core/http.py`、`core/config.py` | 实现TaskAdmission依赖及短锁运行记录更新；原生入队／队列观察屏障在既有proxy接入 | 实际导入／预览和原生消费者 |
| `tests/core/test_workbench.py` | 扩充控制/身份/双服务/并发及回写测试 | tmp_path、monkeypatch |
| `tests/core/test_config.py` | M：修改多入口当前采用值测试 | client/proxy/serve |
| `tests/modules/data/test_service.py` | 扩充maintenance认证/未纳OpenAPI/导入准入 | TestClient夹具 |
| `tests/modules/data/test_display_previews.py` | 扩充维护与真实preview忙闲/排空回归 | 既有可控生成夹具 |
| `tests/interfaces/comfyui/test_proxy.py` | 扩充实际运行地址/Origin沿用及认证回归 | 现有代理夹具 |
| `tests/integration/test_platform_workflow.py` | N：新增文件首次生命周期真实隔离场景，后续Batch增量复用 | 获准W1/W2、固定runtime |

5. **准确关键签名（④第11节；修改/新增）**：

```python
def start(workspace_config: Path | None = None) -> WorkbenchResult: ...
def status(workspace_config: Path | None = None) -> WorkbenchState: ...
def stop(workspace_config: Path | None = None) -> WorkbenchResult: ...
def restart(workspace_config: Path | None = None) -> WorkbenchResult: ...
def initialize(workspace: Path, service_port: int = 8190, comfyui_port: int = 8188, *, frontend_assets: Path | None = None, activate: bool = True, reuse_runtime: bool = False) -> Path: ...
def data_busy(database: Database) -> BusyState: ...
```

initialize保留activate含义但写唯一默认TOML；start移除旧activate参数，调用方按契约更新。控制链：CLI→本机控制→固定workspace/采用值→内部maintenance→现有stop/start→双健康→processes/control→实际地址与源配置端口回写。内部Bearer `POST /internal/maintenance`仅enter/release，不进MCP/公共目录，不新建控制服务。

6. **实施顺序及行为**：先结构化状态/完整文件互斥→复用身份检查→本机控制与实际端口→adopted settings各消费者→②data_busy和维护准入→CLI/测试。只保留当前/最近控制，未完成/待核对不被新控制覆盖。双服务健康及workspace身份匹配才ready；端口扫描不当就绪。回写失败仍报告在线地址和未保存原因，不再启动。维护检查到后续任务准入共用实际互斥；busy或unknown拒绝、不排稍后自动重启。stop保留现有导入/预览排空，实际退出才清记录；领域离线但引擎/进程尚在不能猜空闲。

7. **禁止边界**：core不导入业务；不创建空③⑤busy回调或通用参与者注册器；不新建第三常驻控制服务、自动重试重启/待办队列、历史控制库；不强杀业务代替排空，不误停W2。MCP真实本机控制在B57接入，本卡不改58工具。

8. **验证**：现有`uv run --locked --no-sync pytest tests/core/test_workbench.py tests/core/test_config.py tests/modules/data/test_service.py tests/modules/data/test_display_previews.py tests/interfaces/comfyui/test_proxy.py -q`。实施后新增`uv run --locked --no-sync pytest tests/integration/test_platform_workflow.py -q`。F-WORKSPACE：W2在线，监听器占W1一个优先端口；W1实际两端口不同且健康后回写/返回，重复start复用、W2不变。暂停真实导入/预览后restart拒绝；维护中插新任务拒绝。断连后status核对同operation。沿已有`test_stop_waits_for_domain_service_before_clearing_state`验证排空。记录固定环境冷/热启动耗时及条件，门槛未定不报性能通过。

9. **交付证据**：`.artifacts/implementation/B12/`含双实例地址/身份/Origin/控制ID/预期与观察/日志、冷热条件、未验证项。将③⑤繁忙接入点准确交B33/B53/B54；A12-1真实G01未过则M1不验收，MCP部分保留待B57。

<a id="b13"></a>

## B13：网页工作台配置

状态：B13已实现配置网页／HTTP／具名客户端及同一共用HTTP实现，真实浏览器验收已执行；最终独立复核与用户M1操作分别登记，dev集成待当前候选获用户批准；当前不记I(B13)或A(M1)。

1. **结果、分支和追踪**：`codex/workbench-settings-ui`。网页显示当前workspace保存值/采用值/实际地址/需重启，允许保存，保存不自动重启或改连接。FR-13/14；NFR-03/04/07；A13-1～3、V02、G01网页部分。

2. **必须读**：[FR-13](../../../../requirements/README.md#fr-13-环境检测安装与恢复)、[①数据配置](../../architecture/data-models/01-foundation.md#31-配置)、[①详设](../../api/platform-contracts.md#foundation-design)、[前端具名客户端](../../api/platform-contracts.md#前端具名客户端公开面)。指定源代码：`src/astrophotoflow/interfaces/http/system.py`、`src/astrophotoflow/comfyui/proxy.py`、`frontend/packages/astrophotoflow-ui/src/modules/data/api/client.ts`／`frontend/packages/astrophotoflow-ui/src/modules/data/api/contracts.ts`、`frontend/src/platform/astrophotoflow/NativeShell.vue`。

3. **前置及Ready**：B11、B12集成。用户已确认共用HTTP代码窄移至计划内core/client.ts，errorSchema至core/contracts.ts，data直接重导出/消费同一实现；B13主责，不新增文件框架。同步④后不再把此项列为Choice。本卡未开工，依确认后的基点及前置集成判Ready；真实浏览器按已确认维护窗口执行。

4. **文件级范围**：

| 文件 | 操作／职责 | 依赖 |
|---|---|---|
| `src/astrophotoflow/interfaces/http/system.py` | M：修改新增GET/PATCH设置路由，固定当前在线workspace | core/config公开函数 |
| `src/astrophotoflow/client.py` | M：修改新增2个具名配置HTTP方法，保持AssetClient公开入口 | ConfigSave/ConfigState、原request |
| `src/astrophotoflow/comfyui/proxy.py` | M：修改准确新增settings/workbench GET/PATCH白名单 | 领域路由 |
| `docs/api/openapi.json` | 从实际app生成快照，不能手造已实现接口 | 实际路由/DTO |
| `frontend/packages/astrophotoflow-ui/src/core/contracts.ts` | N：新增①Zod/TS DTO及从data窄移的唯一errorSchema，字段唯一按④ | 纯共同/①契约 |
| `frontend/packages/astrophotoflow-ui/src/core/client.ts` | N：新增createWorkbenchClient；从data窄移FetchApi/ApiClientError/createApiClient同一HTTP实现，保留完整fields | 同源fetch和共同/①schema |
| `frontend/packages/astrophotoflow-ui/src/core/WorkbenchSettings.vue` | N：新增配置读取/编辑/保存/有效值/错误展示；无原生Store导入 | WorkbenchClient |
| `frontend/packages/astrophotoflow-ui/src/index.ts` | M：修改公开组件/客户端/必要类型 | 新core实现 |
| `frontend/packages/astrophotoflow-ui/src/modules/data/api/client.ts` | M：修改为直接重导出/消费core同一HTTP实现，既有数据方法行为保持 | 已确认窄搬迁 |
| `frontend/packages/astrophotoflow-ui/src/modules/data/api/contracts.ts` | M：修改仅重导出/消费core唯一errorSchema，其他数据schema保持 | core/contracts.ts |
| `frontend/src/platform/astrophotoflow/NativeShell.vue` | M：修改经UI包公开导出挂工作台配置入口/面板，GraphView保持挂载 | 包公开面、原生宿主 |
| `tests/modules/data/test_service.py` | M：修改认证/GET/PATCH/OpenAPI一致性 | TestClient |
| `tests/interfaces/comfyui/test_proxy.py` | M：修改新增准确路由/同源与错误透传 | proxy |
| `tests/integration/test_client_operations.py` | M：修改新增具名配置客户端请求/响应/错误断言 | 实际client及DTO |
| `frontend/packages/astrophotoflow-ui/tests/modules/data/api/client.test.ts` | M：修改/复用共用client窄搬迁后的方法/错误/fields行为 | 直接重导出的同一类 |
| `frontend/packages/astrophotoflow-ui/tests/modules/data/api/contracts.test.ts` | R：复用errorSchema同一结构回归 | core schema直接重导出 |
| `tests/browser/platform-workflows.mjs` | N：新增唯一跨模块浏览器文件，先实现工作台配置场景，后续增量复用 | 获准隔离workspace |
| `frontend/packages/astrophotoflow-ui/tests/core/workbench.test.ts` | N：配置保存、采用值、冲突及同一错误类的行为验证 | 实际组件／客户端 |
| `frontend/src/locales/en/main.json`、`zh/main.json` | M：仅新增工作台配置文本，宿主传入翻译函数 | 不向私有UI增加原生依赖 |

5. **准确关键签名（④第10/11节）**：

```typescript
export interface WorkbenchClient {
  getConfiguration(): Promise<ConfigState>
  saveConfiguration(body: ConfigSave): Promise<ConfigState>
}
export function createWorkbenchClient(fetchApi: FetchApi): WorkbenchClient
```

```python
def get_workbench_configuration(self) -> ConfigState: ...
def save_workbench_configuration(self, body: ConfigSave) -> ConfigState: ...
```

两个Python方法在 `src/astrophotoflow/client.py` 的 AssetClient，仅适配既定GET/PATCH，权威签名见[Python具名客户端](../../api/platform-contracts.md#python-clients)。

Python路由只委托B11的`get_configuration(config_path: Path | None = None) -> ConfigState`和`save_configuration(config_path: Path, values: ConfigValues, config_token: str, *, default_workspace: Path | None = None) -> ConfigState`；URL为GET/PATCH `/api/v1/settings/workbench`，UI经`/astrophotoflow/api/v1/settings/workbench`；PATCH正文唯一ConfigSave。不自创Python配置客户端公开名。

共同HTTP窄移保留以下实际签名与推断返回，不新增 ApiClient 类型或包装层：

```typescript
export type FetchApi = (path: string, init?: RequestInit) => Promise<Response>
export function createApiClient(fetchApi: FetchApi)

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly kind: 'network' | 'service' | 'contract',
    readonly status?: number,
    readonly code?: string,
    readonly requestId?: string,
    readonly fields?: z.infer<typeof errorSchema>['error']['fields']
  )
}
```

`createApiClient` 的返回沿现有 get/getBlob/upload/send 对象推断；本卡只补错误解析实际接收的 fields，类型沿当前 errorSchema 的 path/message 数组。data旧路径直接重导出同一函数、类和schema，实例身份与网络行为保持。

6. **实施顺序及行为**：先按④窄移同一HTTP实现/errorSchema→路由/代理/实际快照→Zod/具名client→组件→宿主入口→浏览器。旧data导入直接重导出同一个ApiClientError以保instanceof一致；不做wrapper或第二error类。GET只读当前在线目标；PATCH带真实config_token，409保留用户输入并展示冲突，422保留fields。显示saved/effective/restart_required及实际地址，不能把保存值冒成本次端口。保存不自动重启、不自动换fetch目标；组件只调用明确客户端，无任意URL配置或原生Store依赖。

7. **禁止边界**：无第三应用/服务、重复ApiClientError、第二默认指针、自动重启、配置历史、UI通用settings框架；不为本卡更换Vue/Pinia/Zod版本；保留画布和现有侧栏顺序。新HTTP行为与实际OpenAPI同步，不提前注册MCP。

8. **验证**：现有`uv run --locked --no-sync pytest tests/modules/data/test_service.py tests/interfaces/comfyui/test_proxy.py tests/integration/test_client_operations.py -q`；`pnpm --dir frontend --filter @astrophotoflow/ui test tests/modules/data/api/client.test.ts tests/modules/data/api/contracts.test.ts`；`pnpm typecheck`、`uv run --locked --no-sync pnpm check:boundaries`。新增browser落位后在维护窗口隔离实例设置`$env:APF_WEB_URL = '<该实例实际网页地址>'`，执行`node tests/browser/platform-workflows.mjs`。操作：打开配置→改并发保存→核saved新/effective旧/需重启→旧token再存409且输入保留→本机显式重启→重读effective新/需重启清除。401/403/422字段错误可见，未带令牌被拒；页面无服务令牌正文。窗口结束恢复原dev状态，默认目标不改。

9. **交付证据**：`.artifacts/implementation/B13/`含真实UI截图/设置值前后/失败回执/实际地址及输入、HTTP搬迁后的同一错误类/fields回归；M1人工出口核对配置、重启和端口场景。维护窗口未实际完成或用户未批准不签M1通过。
