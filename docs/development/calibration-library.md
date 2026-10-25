# 独立校准库与版本化校准关联

分支：`feature/calibration-library`。起点：`9a0706ef4566ff0fbb37b0e704b4c3f0b861200d`，包含已集成的设置和导入功能。

## 范围与使用

- 素材库默认仍为“全部素材”，另提供“亮场”和“校准库”。Master Light 属于亮场；未知用途仍可从全部素材访问。已有混合组在相关视图中保留，并明确标识混合用途；进入组后显示完整成员。
- 校准库提供“从已有校准照片创建组”，明确选择已经登记的资产版本、组名与场景说明。新组保存逻辑引用，不复制原件、不移动成员、不重新分类，也不自动改造旧导入组。
- 图像组内“组说明、历史版本与校准关联”可编辑当前组资料、查看旧版本，设置 Bias／Dark／Flat／Dark Flat 默认与每个成员的覆盖。历史成员和关联只读；名称和场景说明是当前组资料。
- 关联目标固定为校准 DatasetVersion 或 Master 校准 AssetVersion。目标候选包含可用用途的历史版本，不自动匹配参数，不执行校准、叠加或 Master 合成。
- 成员缺失某个键表示继承；显式 `null` 表示不使用；对象表示覆盖。覆盖保存在该组的 DatasetMember，同一照片在另一组的配置不受影响。
- 仅关联变化也发布新的 DatasetVersion；成员变化及导入追加保留旧默认与保留成员的覆盖。已选旧版的项目保持原版本和原关联。
- 库视图返回完整组成员和 `matching_member_count`。后者使用服务既有 `matches_member` 计算，包含亮场／校准分类和其他实际筛选；当仅部分成员匹配时，外层组批量资料编辑要求先进入完整组。全部成员匹配时仍可直接编辑。

## API

新增：

```text
POST /api/v1/datasets
{name, notes?, asset_version_ids:[...]}

GET /api/v1/calibration/targets?frame_type=dark&limit=50&offset=0&q=...
{items:[{target:{kind,id}, name, frame_type, version_number, member_count}], total, limit, offset}
```

现有版本发布请求增加字段：

```json
{
  "base_revision": 1,
  "asset_version_ids": ["完整成员版本 ID 列表"],
  "calibration_defaults": {
    "dark": {"kind": "asset_version", "id": "固定 Master 版本 ID"},
    "bias": {"kind": "dataset_version", "id": "固定校准组版本 ID"}
  },
  "member_calibration_overrides": {
    "成员资产版本 ID": {"dark": null}
  }
}
```

- 省略 `calibration_defaults` 沿用旧值；提供对象则替换整张默认表，`{}` 清空默认。
- 省略某个成员的覆盖表沿用该成员旧值；提供该成员的对象则替换其覆盖表，`{}` 恢复全部继承。
- 映射对象本身不能为 null；映射内的各类键可以是 null。不存在的成员、错误作用域／用途、非 Master 单资产目标返回标准 `422 INVALID_REFERENCE`；revision 过期返回 `409 REVISION_CONFLICT`。
- 对当前 AssetVersion，目标用途验证读取 Asset 当前明确分类，因此可使用人工纠正为 Master Dark 的照片；历史非当前版本读取固定版本事实。相等且沿用的旧关联不重新验证标签，配置编辑不会重写历史关联。
- `/datasets/{id}/versions/{version_id}` 和版本列表始终返回完整规范成员；匹配成员计数只属于库视图 DTO，不修改版本内容。

Pydantic、Zod、代理白名单和生成 OpenAPI 已同步。没有新增迁移，也没有修改 ORM 或运行配置。

## 永久清理与重试

回收站预览新增 `calibration` 引用类型。所有存活历史默认／成员覆盖均参与保护，引用身份包含目标与用途并进入 fingerprint。其他组仍引用目标时，后端在文件 unlink 前返回 `409 CALIBRATION_IN_USE`；前端显示引用并阻止确认，不清空任何映射。

消费者组和目标同时被选中时采用保留策略：

1. 校准目标原件、共享该物理路径的选中原件和 AssetVersion 先保留；其他选中照片继续按原清理规则处理。
2. 当组仅剩这些保留目标时，可移除已经明确选择的消费者容器。目标照片转为独立回收站记录；只解除即将删除的容器与这些回收站记录之间的 bookkeeping `dataset_version_id`，不改写校准映射。
3. 响应和界面保留明确的“清理引用组后可重试此照片”提示。下一次对剩余回收站项重新预览／清理即可完成；真实文件失败时先解除失败，再完成消费者，最后重试保留目标。

该顺序在两个选择顺序、目标为自己的混合组成员、目标为数据集、消费者文件锁、共享托管路径场景均有回归测试；没有递归重试或一般依赖图框架。既有 R4、受损照片、共享路径和外部来源保护回归保留。

## 隔离与实际验证

工作树：`C:/Users/Administrator/.codex/worktrees/apf-calibration-library/ComfyUI-AstroPhotoFlow`。所有命令在该目录执行：

```powershell
git checkout feature/calibration-library
git merge --ff-only 9a0706ef4566ff0fbb37b0e704b4c3f0b861200d
$env:UV_PROJECT_ENVIRONMENT='C:/Users/Administrator/.codex/worktrees/apf-calibration-library/ComfyUI-AstroPhotoFlow/.artifacts/venvs/dev'
& 'C:/Users/Administrator/Desktop/WorkSpace/ComfyUI-AstroPhotoFlow/.artifacts/venvs/dev/Scripts/uv.exe' sync --locked --extra dev --python 'C:/Users/Administrator/Desktop/WorkSpace/ComfyUI-AstroPhotoFlow/.artifacts/venvs/dev/Scripts/python.exe'
corepack pnpm install --frozen-lockfile
.artifacts/venvs/dev/Scripts/python.exe -c "import astrophotoflow; print(astrophotoflow.__file__)"
.artifacts/venvs/dev/Scripts/python.exe scripts/export_openapi.py
.artifacts/venvs/dev/Scripts/python.exe -m pytest tests/backend/test_calibration.py tests/backend/test_service.py tests/backend/test_ingestion.py tests/backend/test_domain_foundation.py tests/comfyui/test_proxy.py -q --junitxml=.artifacts/reports/calibration-backend.xml
corepack pnpm test --reporter=dot 2>&1 | Tee-Object -FilePath .artifacts/reports/calibration-frontend.txt
corepack pnpm build 2>&1 | Tee-Object -FilePath .artifacts/reports/calibration-build.txt
git diff --check
```

| 检查 | 结果 |
|---|---|
| Python 实际导入位置 | 本工作树 `src/astrophotoflow/__init__.py` |
| 校准／服务／导入／迁移／代理回归 | 114 passed，含 19 个新校准用例；已有 SQLAlchemy 外键环排序警告 1 条 |
| 全部前端组件测试 | 125 passed，含 6 个校准视图／关联／回收站用例 |
| 类型检查、生产构建 | 通过；生成本工作树 `build/frontend` |
| OpenAPI 与代理契约 | 通过；71 条代理路由 |
| 差异空白检查 | 通过 |

组件验证中观察到单资产非方形 Bin 用例的复合模拟事件不稳定；仅将该用例两次打开改为公开的 `dblclick` 触发，保留原数字／取值／revision 断言和其他普通点击覆盖，没有改动生产 Bin 代码。未在未修改基线复现，因此不将其归因于旧基线。失败摘要单独保存在 `.artifacts/reports/calibration-compound-event-failure.json`；最终 125 项通过记录保存在 `calibration-frontend.txt`。

未使用 CUA、未自动点击实际宿主、未重新导入整套真实素材，未启动持久服务或改动全局 MCP／workspace 激活指针。没有待确认的高影响产品抉择；宿主交互仍由用户手动验收。

## 合入提示

- 新库视图和组成员显示复用 `WorkspaceRecords.vue`；预览分支的缩略图点击钩子可直接覆盖这些视图。新建校准组选择表没有独立缩略图实现。
- 校准编辑器通过新 `calibrationUpdated(DatasetOut)` 回调更新当前组并调用 `loadRecords`，不依赖预览分支移除的 DatasetEditor 回调。
- `trash.py` 的校准引用保护独立于预览工作保护：在既有引用重验证之后、active-task／unlink 之前检查校准及共享路径依赖；在最后删除 DatasetVersion 前再检查目标依赖。预览生成状态保护可独立放在同一破坏性事务的文件循环之前。
- `library.py` 只增加既有 matcher 的成员计数；`ingestion.py` 未修改，继续使用公共基础提供的默认／覆盖复制行为。
