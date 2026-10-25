# 设置组织：使用组合与拍摄预设

分支：`feature/settings-organization`。公共基础：`3f72b71`；同步共享上传预设事务修复 `7a8dd43`（本分支对应 `9df8813`）。

## 已实现行为

- 设置的主入口为项目、设备、使用组合。设备分类为相机、望远镜、滤镜、赤道仪和配件；设备管理及组合／预设不再提供旧 `optical_system` 设备兼容选项。
- 使用组合可以关联注册设备，或保存只属于该组合的内联设备。编辑组合不会改写注册设备，也不会把内联设备登记进设备库。
- 拍摄预设在所属组合内创建和编辑，删除、恢复与永久删除由统一回收站管理。预设参数保持稀疏结构：未触碰字段不写入；清空已填写字段传 `null`；数值 `0` 保留。
- 项目、设备、使用组合和拍摄预设复用素材库的搜索、筛选、多选、回收站、恢复及永久删除预览；新增和修改继续使用输入表单，不提供设置文件导入。
- 永久删除设备时，素材当前参数和固定版本保留设备快照，设备外键解除；关联的使用组合将注册设备转为组合内快照，预设中的设备默认值不再指向已删除设备。接受后的导入任务独立保留设备资料，设备永久删除不会导致后续登记或重试失败。
- 旧版 CaptureProfile 已移除，包括旧入口、接口、项目字段和数据表；配置统一使用设备、使用组合、拍摄预设。0001–0008 为历史迁移，0009 移除旧结构，不转换旧配置为新预设。
- 项目详情直接提供查看及添加单图／数据集入口，显示选用或固定的版本号与版本 ID。项目固定版本引用的业务语义不变。
- 导入对话框先选组合再选所属预设，只提交 `capture_preset_id`，不把默认值填入人工表单。接受任务时由公共 `capture_defaults_snapshot` 保存配置快照，重试沿用原快照；人工／文件／预设的最终优先级由导入流水线分支消费该契约。
- 组合和预设表单有未保存修改时，切换区域／记录会确认；搜索、筛选、分页与刷新在保存或取消前停用。

## API

| 方法 | 路径 | 用途 |
|---|---|---|
| GET / POST | `/api/v1/equipment-setups` | 分页查询／创建组合 |
| GET / PATCH | `/api/v1/equipment-setups/{setup_id}` | 读取／更新组合 |
| GET / POST | `/api/v1/equipment-setups/{setup_id}/presets` | 查询／创建组合内预设 |
| GET | `/api/v1/capture-presets` | 跨组合查询，可按 `equipment_setup_id` 筛选 |
| GET / PATCH | `/api/v1/capture-presets/{preset_id}` | 读取／更新预设 |

列表沿用 `limit/offset/q/status/sort_by/order`。更新需要 `base_revision`，冲突返回 `409 REVISION_CONFLICT`；不存在对象为 `404 RESOURCE_NOT_FOUND`，错误设备关联为 `422 INVALID_REFERENCE`。预设参数和分类 PATCH 合并明确提供的字段，状态通过归档管理。后端 DTO、前端 Zod、代理白名单和生成的 OpenAPI 同步更新。

## 环境与验证

独立工作树：`C:/Users/Administrator/.codex/worktrees/apf-settings-organization/ComfyUI-AstroPhotoFlow`。
下列命令均从该目录运行；Python、Node 依赖、测试临时数据、报告和构建均属于该工作树。

```powershell
$env:UV_PROJECT_ENVIRONMENT='C:/Users/Administrator/.codex/worktrees/apf-settings-organization/ComfyUI-AstroPhotoFlow/.artifacts/venvs/dev'
& 'C:/Users/Administrator/Desktop/WorkSpace/ComfyUI-AstroPhotoFlow/.artifacts/venvs/dev/Scripts/uv.exe' sync --locked --extra dev --python 'C:/Users/Administrator/Desktop/WorkSpace/ComfyUI-AstroPhotoFlow/.artifacts/venvs/dev/Scripts/python.exe'
corepack pnpm install --frozen-lockfile
.artifacts/venvs/dev/Scripts/python.exe -c "import astrophotoflow; print(astrophotoflow.__file__)"
.artifacts/venvs/dev/Scripts/python.exe scripts/export_openapi.py
.artifacts/venvs/dev/Scripts/python.exe -m pytest tests/backend/test_service.py tests/backend/test_setups.py tests/backend/test_domain_foundation.py tests/comfyui/test_proxy.py tests/backend/test_ingestion.py::test_root_browser_import_versions_edit_and_dataset_references tests/backend/test_ingestion.py::test_project_asset_and_dataset_reference_deletes_check_revision_without_deleting_data -q --junitxml=.artifacts/reports/settings-backend.xml
corepack pnpm test --reporter=dot 2>&1 | Tee-Object -FilePath .artifacts/reports/settings-frontend.txt
corepack pnpm build 2>&1 | Tee-Object -FilePath .artifacts/reports/settings-build.txt
git diff --check
```

| 检查 | 实际结果 |
|---|---|
| Python 导入路径 | 位于本工作树 `src/astrophotoflow/__init__.py` |
| 配置／组合／预设／快照／固定引用／代理测试 | 71 passed；已有 SQLAlchemy 相互外键排序警告 1 条 |
| 全部前端组件测试 | 116 passed |
| 类型检查与生产构建 | 通过；生成本工作树 `build/frontend` |
| OpenAPI 快照及代理契约 | 后端测试通过；69 条代理路由 |
| 差异空白检查 | 通过 |

新增后端测试验证六种设备部分参数更新保留旧字段、内联不注册、组合不修改设备、分页／归档／revision、预设稀疏 null／0、接受后配置变更及重试快照。新增组件测试验证组合创建与编辑、组合内预设创建与编辑、旧版入口、设备类别、未保存保护、导入预设选择及项目双类型添加入口。

未自动点击前端，未执行整批真实素材导入；没有启动持久服务、修改全局 MCP 或激活其他 workspace。宿主实际交互留待用户手动验收。

## 跨分支集成

- `ImportDialog.vue` 仅增加 picker import、`capturePresetId` ref、条件请求字段、打开时重置、组件渲染五处；导入分支的分类与上传逻辑应保留这些独立改动。
- `backend/api.py` 仅增加 setups router import 与 include；导入分支的 lifespan 修改可独立合入。
- `WorkspaceRecords.vue` 仅把组合草稿状态加入分页控件的 disabled 条件；后续素材／预览改动保留此保护。
- 本分支没有修改公共 ORM、schema revision、运行配置、导入 worker 或既有项目引用处理逻辑。共享 `imports.py` 修复通过父代理提供的提交同步。
