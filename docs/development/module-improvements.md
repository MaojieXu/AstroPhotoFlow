# 五分支协作开发

功能基线：`a5c638133852c4a50d75579912868e165a203870`（feature/remake）。
本文件记录用户在 2026-10-25 确认的范围；实际完成状态必须附提交和验证证据。

## 已确认的产品约定

- 项目按目标或处理任务组织，收集跨夜、跨滤镜的单图和数据集固定版本。
- 设备分相机、望远镜、滤镜、赤道仪、配件；已有 optical_system 字段的含义保留。
- 使用组合引用注册设备或保存内联设备快照；内联设备不自动写入设备库，组合修改不修改注册设备。
- 拍摄预设属于使用组合。导入优先级为人工显式值、文件实测值、预设默认值、未知；保存导入时快照。
- 自动识别与整批手动指定分类同时支持，前端、CLI、MCP 使用同一规则。无明确依据时保留未知，不猜文件名。
- 亮场与校准素材分开展示。Master Light 属于亮场。
- 校准关联指向固定的校准数据集版本或 Master 校准资产版本，不执行合成或校准运算。
- 组默认和成员覆盖属于亮场数据集版本；成员缺省表示继承，显式空值表示不使用。覆盖不影响其他组。
- 同条件子组按固定成员顺序选择首张可用图作为拉伸基准；不能使用竞速完成顺序。
- 数据、原件托管、解析、预览状态分开；前端主进度只反映登记。失败必须可查询与重试。
- 缩略图 100 px；点击大图最长边 1080 px，按需生成 JPEG 并缓存，不放大小图。

## 分工与执行顺序

主代理维护公共模型、迁移、接口约定、共享运行配置和集成。
公共基础提交后创建下列分支，各自使用独立 worktree；最多两个实现 Agent 并行。

| 分支 | 范围 | 依赖 |
|---|---|---|
| feature/import-pipeline | 快速登记、后台托管、有界并发、分类、拉伸及性能证据 | 公共模型与任务契约 |
| feature/settings-organization | 项目、设备分类、使用组合、组合内拍摄预设 | 公共模型与参数优先级 |
| feature/library-preview | 按需大图、移除重复管理成员入口、保留组内编辑 | 导入与预览边界稳定 |
| feature/calibration-library | 独立校准库、版本绑定、组默认、成员覆盖 | 组合和版本接口稳定 |
| feature/library-agent-tools | 结构化客户端、CLI/MCP 业务操作、数据库管理 Skill | 对应领域 API 稳定 |

首先并行导入与设置；随后预览与校准。工具分支随 API 稳定逐步接入。
每分支只接收本文件、精简任务单和实际相关源码入口，不复制完整聊天。
公共文件变化由主代理协调，不允许通过覆盖其他分支实现消解冲突。

## 运行隔离

- 每个 worktree 有自己的 Python 环境、Node 依赖、配置、数据库、端口、构建目录和测试报告。
- 固定 CPU runtime 的源码和 Python 依赖可以共享。插件使用 `workspace/comfyui-data/custom_nodes/AstroPhotoFlow`，不写全局插件目录。
- 开发源码需显式传入 `--frontend-assets build/frontend`；安装包自带资源。
- worktree 初始化使用 `--reuse-runtime --no-activate`；启动使用 `--no-activate`，避免修改全局默认 workspace 指针。
- 不修改全局 MCP 注册；stdio 测试通过进程环境指向本 worktree 的配置。
- 原始真实数据只读共享，不复制整套到 worktree。测试优先使用合成素材。
- 每次运行核对 `astrophotoflow.__file__` 位于目标 worktree，防止误用另一目录的 editable 安装。

## 接口与验证规则

公共模型：EquipmentSetup、CapturePreset；新增迁移 `0007_setups_and_calibration`。
组合 components 是 `{source:"registered",equipment_id}` 或 `{source:"inline",equipment:{kind,name,specs,...}}`。
预设属于一个组合。新领域路由约定为 `/equipment-setups`、`/equipment-setups/{id}`、
`/equipment-setups/{id}/presets` 和 `/capture-presets/{id}`；需要跨组合查询时提供 GET `/capture-presets`。
导入请求使用可选 `capture_preset_id`；接受时通过 `presets.capture_defaults_snapshot` 保存
`AssetTask.import_defaults_snapshot`（parameters、classification、equipment_setup、capture_preset），重试复制该快照。
导入 worker 不再读取可能已修改的预设。既有 CaptureProfile 和其接口保留，UI 组织在组合内。

校准映射按 bias/dark/flat/dark_flat 存储；目标为 `{kind:"asset_version"|"dataset_version",id}`。
DatasetVersion.calibration_defaults 和 DatasetMember.calibration_overrides 中缺失键表示无默认/继承，
显式 null 表示不使用。两条数据集发布路径均保留旧默认值及被保留成员的覆盖；
校准分支扩展现有发布请求实现校准独立变化也产生新版本，并补充永久清理的引用保护。

- CLI/MCP 通过 HTTP 使用同一业务规则，不直接操作 SQLite。保留已有命令和五工具名称，补充本轮主要操作。
- 保持参数省略/null/0、revision 冲突、分页、错误 envelope 和令牌/同源代理规则。
- API 改动同时维护 OpenAPI、Pydantic、代理白名单和前端 Zod；新工具有真实 stdio 回归。
- 保留取消、恢复、任务重试的资产身份、R4、受损原件、共享路径和外部来源保护回归。
- 性能先分阶段计时，再比较同机相同输入；登记速度与整体托管完成速度分别报告。
- 固定候选后独立审查；相关测试按变更运行，集成完成后一次完整测试与发行包验收。
- 不自动点击前端，不重导入全部真实素材。交互由用户手动验收。
- 本地提交，不推送、不合并 dev/main。待产品抉择记录后继续不依赖它的工作。

## 当前执行记录

| 阶段 | 状态 | 证据 |
|---|---|---|
| 基线与用户抉择 | 已确认 | 本文件及当前 Goal |
| workspace 插件隔离、导入并发配置 | 基础实现通过 | workbench/comfyui 19 项通过；复用/隔离补充 3 项通过 |
| 组合/预设与校准公共模型 | 基础实现通过 | 模型/迁移/契约 9 项通过；前端 111 项通过，类型检查通过 |
| 五个功能分支 | 已从 3f72b71 创建 | 导入与设置已进入各自管理型 worktree；其他按依赖启动 |

逐项交付状态和实际证据见[验收记录](module-improvements-acceptance.md)。
