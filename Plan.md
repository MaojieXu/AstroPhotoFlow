# 方案 A 与真实素材 pytest 的合并实施计划

## 1. 统一素材状态与处理规则

素材新增 `calibration_status`，固定使用三种值。

| 状态 | 判断依据 |
|---|---|
| `UnCalibrated` | 明确确认尚未进行校准 |
| `Calibrated` | 明确确认预期校准已完成 |
| `Unknown` | 信息不足、处理不完整或来源无法确认 |

- 外部导入默认 `Unknown`，导入时可明确声明状态并保存声明依据。
- 保存 Master 绑定只更新待用配置。
- 校准成功的输出登记为新素材，记录来源素材、实际 Master 和软件调用。
- 明确保留状态的操作沿用输入状态。缺少处理语义的操作输出 `Unknown`。
- 软件操作的状态规则由明确的定义和执行回执确定。
- Master 同样保存自己的校准状态。
- 数据集成员状态一致时展示该状态，否则汇总为 `Unknown`，并显示三种状态的成员数量。
- 保留当前状态模型、revision、设备及导入快照、运行输入记录和原件保护。

## 2. 完整磁盘结构与命名规则

### 固定目录结构

五种用途均包含 Subframe、MasterFrame 和三种状态。

```text
data/
├─ astrophotoflow.sqlite3
├─ library/
│  ├─ Light/
│  │  ├─ Subframe/
│  │  │  ├─ UnCalibrated/
│  │  │  ├─ Calibrated/
│  │  │  └─ Unknown/
│  │  └─ MasterFrame/
│  │     ├─ UnCalibrated/
│  │     ├─ Calibrated/
│  │     └─ Unknown/
│  ├─ Dark/
│  │  ├─ Subframe/
│  │  │  ├─ UnCalibrated/
│  │  │  ├─ Calibrated/
│  │  │  └─ Unknown/
│  │  └─ MasterFrame/
│  │     ├─ UnCalibrated/
│  │     ├─ Calibrated/
│  │     └─ Unknown/
│  ├─ Flat/
│  │  ├─ Subframe/
│  │  │  ├─ UnCalibrated/
│  │  │  ├─ Calibrated/
│  │  │  └─ Unknown/
│  │  └─ MasterFrame/
│  │     ├─ UnCalibrated/
│  │     ├─ Calibrated/
│  │     └─ Unknown/
│  ├─ Bias/
│  │  ├─ Subframe/
│  │  │  ├─ UnCalibrated/
│  │  │  ├─ Calibrated/
│  │  │  └─ Unknown/
│  │  └─ MasterFrame/
│  │     ├─ UnCalibrated/
│  │     ├─ Calibrated/
│  │     └─ Unknown/
│  ├─ DarkFlat/
│  │  ├─ Subframe/
│  │  │  ├─ UnCalibrated/
│  │  │  ├─ Calibrated/
│  │  │  └─ Unknown/
│  │  └─ MasterFrame/
│  │     ├─ UnCalibrated/
│  │     ├─ Calibrated/
│  │     └─ Unknown/
│  └─ Unclassified/
│     ├─ Subframe/
│     │  ├─ UnCalibrated/
│     │  ├─ Calibrated/
│     │  └─ Unknown/
│     ├─ MasterFrame/
│     │  ├─ UnCalibrated/
│     │  ├─ Calibrated/
│     │  └─ Unknown/
│     └─ Other/
│        ├─ UnCalibrated/
│        ├─ Calibrated/
│        └─ Unknown/
├─ previews/
└─ staging/
```

`Unclassified` 接收用途未知的素材。形态也无法确定的素材，以及其他受支持文件，进入 `Other`。

### Subframe 目录内部

每个数据集使用一个目录，目录名包含数据集名称、设备与拍摄参数及短 ID，内部直接保存导入文件和固定的 `dataset.json`。

```text
Light/Subframe/UnCalibrated/
├─ IC443_P0_Green__<相机>__GAIN90__T-20C__EXP120s__F-Green__a1b2c3d4/
│  ├─ light-G-001.fits
│  ├─ light-G-002.fits
│  └─ dataset.json
└─ IC443_P0_Red__<相机>__GAIN90__T-20C__EXP120s__F-Red__b2c3d4e5/
   ├─ light-R-001.fits
   ├─ light-R-002.fits
   └─ dataset.json
```

- 数据集由 Agent／User 明确组织，成员张数可以变化，组内拍摄参数差异以 warning 展示。
- 分组与滤镜拆分由 Agent／User 完成，系统展示并校验提交成员的参数差异。
- 组内用途、相机、读出模式、ISO／Gain／Offset、温度、曝光、滤镜、Binning 和光学配置逐项展示差异。最高与最低实测温差不超过 1°C 视为匹配，超过阈值及其他拍摄参数差异只返回 warning，允许保存与处理。拍摄时间、文件名和序号允许不同。
- 未知资料保留未知，由 Agent／User 确认。
- 数据集目录保存实际导入的原件，`dataset.json` 保存有序成员及校准关系。
- 每次导入生成独立素材 ID 和托管原件。同一素材最多属于一个数据集，JSON 记录其稳定 ID 和原件路径，移除归属后可加入另一数据集。
- 数据集 JSON 可以引用其他数据集目录中的已有素材。
- 移除数据集成员保留原件，原件清理由素材回收站负责。

### MasterFrame 目录内部

```text
Dark/MasterFrame/Unknown/
└─ ASI2600MM__MODE-UNK__GAIN-UNK__T-UNK__EXP120s/
   └─ MasterDark_120s__c3d4e5f6/
      └─ master-dark.fit
```

每个 Master 使用独立目录，保存原始文件名。

### 命名与路径约束

数据集目录使用：

```text
<数据集名称>__<相机>__<读出模式>__<ISO或Gain>__<温度>__<曝光>__<滤镜>__<短ID>
```

- Dark、Bias、DarkFlat 省略滤镜字段。
- 使用已确认设备名称或已记录的文件观察名称，保留未知和名称差异。
- ISO、Gain 和标准模式分别明确表达，数值 `0` 有效。
- 温度使用完整实测值，目录名称保留必要小数，科学匹配读取完整资料。
- 曝光统一使用秒，保留必要小数。
- 未知字段使用 `UNK`，组内参数差异和未知数量由界面及 JSON 展示，目录标签采用首个当前成员的参数。
- 数据集目录使用上述完整模板，Master 目录沿用 `<名称>__<短ID>`。
- 短 ID 从完整 ID 生成，从 8 位开始，冲突时增加长度。
- 原文件名保留，重名时追加素材短 ID。
- 统一处理 Windows 非法字符、保留名称、尾部空格和句点，并预检完整路径长度。
- 修改资料先保存数据库，通过“整理目录”更新物理位置和 JSON。
- 整理前计算移动范围、检查冲突与占用，失败时报告实际完成情况。

## 3. 数据库与 JSON 镜像

SQLite 持久保存素材身份、当前位置、成员顺序、三种状态及校准关系。

每个数据集在自身目录内生成一份固定名称的 `dataset.json`，包含：

- 数据集 ID、名称、当前 revision 和状态数量。
- 有序成员的素材 ID、相对路径、校准状态及状态依据。
- 待用 Master 的用途、ID、名称和相对路径。
- 已知的实际校准及软件处理来源摘要。

JSON 明确区分待用配置和已执行事实，路径统一相对 `library/`。

同步行为：

- 导入、成员编辑、校准修改、状态修改和目录整理后，更新受影响数据集。
- 数据库提交后，通过临时文件和原子替换发布镜像。
- 镜像失败时保留已提交数据，记录待更新状态并支持重建。
- 重建从数据库生成当前内容。
- 素材资料或位置变化同步更新所属数据集及引用它的校准关系镜像。
- 永久清理继续检查引用、活动任务和文件归属，并维护相关 JSON。

## 4. 前端、后端、HTTP、CLI 和 MCP

| 部分 | 实施内容 |
|---|---|
| 后端 | 统一处理状态、命名、路径、镜像、目录整理和原件保护 |
| 前端导入 | 声明校准状态，展示资料来源与未知值 |
| 素材列表 | 按三种状态筛选，显示当前状态和实际位置 |
| 数据集详情 | 显示成员顺序、状态数量、待用 Master 和实际处理来源 |
| 文件操作 | 提供打开目录、重建 JSON、预检并整理目录 |
| HTTP | 扩展素材和数据集字段，提供位置查询、镜像重建及目录整理接口 |
| CLI／MCP | 复用同一服务，返回状态、依据和位置，写入使用当前 revision |
| 软件调用 | 固定本次实际输入，按明确处理语义登记输出状态 |
| 生成物 | 更新 OpenAPI、前端 SDK、MCP 工具清单和生成 CLI |

前端、HTTP、CLI 和 MCP 的分组操作统一接受 Agent／User 明确提交的成员清单，并展示、校验参数差异。

目录整理与镜像状态通过各入口一致返回。部分成功、占用、过期 revision 和失败文件均使用真实回执。

## 5. 五组真实数据与 pytest 体系

### 数据基线

以下五个目录作为原始测试素材目录。数据集分组与滤镜拆分由 Agent／User 明确选择，并固化为测试 fixture 清单。

| 目录 | 数量 | 测试价值 |
|---|---:|---|
| `IC443_RGB_P0` | 93 | RGB、120 秒、完整滤镜名称 |
| `IC443_RGB_P1` | 94 | 完整滤镜名称与 G／B／R 并存 |
| `IC443_SHO_P1` | 158 | 窄带与 RGB 混合，120／300 秒曝光 |
| `IC443_SHO_P2` | 159 | 温度及相机名称存在差异 |
| `2023-10-01_Calibration` | 10 | 3 个 Master Dark、7 个 Master Flat，部分资料缺失 |
| **合计** | **514** | 约 16 GiB，文件头均已只读检查 |

所有源文件只读。托管副本、数据库、故障文件及报告位于 pytest 临时目录。

### 文件组织

```text
tests/real_data/
├─ conftest.py
├─ test_catalog.py
├─ test_imports.py
├─ test_datasets.py
├─ test_calibration.py
├─ test_interface_parity.py
├─ test_library_layout.py
├─ test_dataset_manifest.py
└─ test_calibration_status.py
```

在现有根测试配置中注册数据根目录参数、完整导入开关及 pytest 标记。

| 文件 | 覆盖内容 |
|---|---|
| `test_catalog.py` | 文件数量、格式、头部分类、真实差异及缺失值 |
| `test_imports.py` | 托管复制、哈希、逐项回执、部分失败、恢复和重试 |
| `test_datasets.py` | 明确分组、参数 warning、当前成员、排序、追加、移除、独立原件及项目引用 |
| `test_library_relations.py` | 独立导入、回收站引用、外部引用清理保护、活动调用占用、分类回滚及设备 revision |
| `test_calibration.py` | Master 用途、兼容检查、未知确认、共享配置及并发 |
| `test_interface_parity.py` | HTTP、生成 CLI、MCP 的交叉读写及错误一致性 |
| `test_library_layout.py` | 完整分类矩阵、命名、路径归属、整理与部分失败 |
| `test_dataset_manifest.py` | JSON 内容、关系同步、并发、失败报告及重建 |
| `test_calibration_status.py` | 三种状态、声明依据、绑定行为、输出传播和目录一致性 |

### 分层执行

- 头部检查覆盖全部 514 个文件。
- 常规功能测试选择各类代表样本，按 fixture 中明确的成员清单验证导入、参数诊断和分组结果。
- 完整导入独立执行一次 514 文件复制。
- 故障注入只作用于临时副本或测试调用。
- 状态传播使用明确的操作定义和受控回执验证。
- 真实软件处理单独记录实际运行情况。

注册 `real_data`、`full_import`、`plan_a` 标记。方案 A 实现后，其用例纳入真实素材验收。

未指定素材根目录时，真实数据用例显示跳过原因。显式指定后，缺失目录或不符合基线应失败。完整复制额外要求 `--run-full-import`。

代表样本入口：

```powershell
uv run --locked --no-sync pytest tests/real_data `
  --real-data-root "E:/AstroPhotoFlow/Erellaz" `
  -m "not full_import"
```

完整导入入口：

```powershell
uv run --locked --no-sync pytest tests/real_data `
  --real-data-root "E:/AstroPhotoFlow/Erellaz" `
  --run-full-import `
  -m full_import
```

报告写入 `.artifacts/reports/real-data/`，记录任务 ID、源文件、阶段状态、错误码及通过／失败／跳过数量。

## 6. 实施顺序与交付

1. 增加状态契约、数据库字段及处理来源表达。
2. 实现目录命名、路径分配和安全整理。
3. 贯通导入、数据集、校准、结果保存与 JSON 镜像。
4. 同步前端、HTTP、客户端、CLI 和 MCP。
5. 编写真实数据 pytest、适配现有测试及生成物。
6. 更新中英文文档、执行静态检查和生产构建。
7. 沿用现有 `dev`，原地重建开发测试库并安装新前端，保持停止状态。

本次交付包含功能实现和成体系的 pytest 源码。按此前要求，执行静态检查与构建，自动测试和端到端运行留作后续验收，交付时明确记录未执行项目。
