# 最终 bug 修复与设备资料解耦验收

日期：2026-10-25。分支：`feature/remake`，基于 `d49c3de` 及原工作区未提交修改继续开发；验收时尚未提交、推送或合并；验收后按用户指令将本轮实现合入并推送 dev。

## 已实现行为

- 上传和目录导入接受时在同一事务将显式设备、预设和组合引用的资料冻结到 `import_defaults_snapshot.equipment_snapshots`，按设备 ID 保存。参数的人工／文件／预设优先级、null 和零值语义不变。
- 登记、部分登记后的恢复和失败重试使用原快照。设备已删除时版本外键为空，历史 ID、名称、规格及备注保留；删除不改写任务快照。
- 素材当前资料使用本条素材快照，项目固定版本使用该版本快照。按设备排序及筛选名称不读取设备库当前名称；同 ID 的不同历史名称在筛选项合并显示。
- 已保存的拉伸数值不再依赖参考版本的存活；FITS／XISF 参考图删除后，其余成员仍能首次生成及重新生成大图。原件就绪、完整配方及生成任务清理保护保留。
- 使用组合和预设存在草稿或正在保存时，管理筛选入口及应用按钮禁用；已打开面板同样受保护。
- 设置回收站输入采用现有 `UuidInput`，修复正常 UUID 字符串被严格模型拒绝而返回 422 的问题。

## 接口及结构调整

- 移除旧 CaptureProfile 页面、路由、DTO、能力字段和项目关联。旧 `/api/v1/capture-profiles` 返回404；项目 `capture_profile_ids` 不再接受，版本响应不再包含 `capture_profile_id`。
- 保留历史迁移 `0001–0008`，新增 `0009_remove_legacy_capture_profiles`；移除旧配置表、关联表和版本外键列，检查 SQLite 外键完整性。
- 同步 OpenAPI、Zod、前端 fixture、代理契约和发行迁移资源清单。CLI 命令及58个MCP工具集合不变。
- 本次开发库按授权直接重建，不转换旧配置、旧任务或旧测试记录。

## 自动化证据

| 检查 | 实际结果 |
|---|---|
| 完整 Python 产品测试 | 270 passed，1 skipped；已有 SQLAlchemy 循环外键排序警告1条 |
| 跳过项 | `test_ffmpeg_extracts_one_video_frame`，本机 FFmpeg unavailable |
| 完整前端测试 | 19 files，138 passed |
| TypeScript 检查／生产构建 | 通过，168 modules |
| wheel 源码目录外安装 | 通过，入口、schema、插件及资源检查通过 |
| sdist 无 Node 重建 wheel | 通过，并重新安装验证 |
| 平台 | Windows、Python 3.12.4；Linux 本轮未运行 |

关键回归：`tests/backend/test_equipment_snapshots.py` 覆盖21项设备生命周期、排队上传／目录导入、部分登记恢复、失败重试及历史名称；`test_display_previews.py` 覆盖 FITS／XISF 删除参考图后生成／再生成，以及未就绪保护。前端 SettingsOrganization 和 Workspace regression 覆盖草稿、保存中筛选及逐条／固定版本设备名称。

命令入口：

```powershell
.artifacts/venvs/dev/Scripts/python.exe -m pytest -q --basetemp=.artifacts/pytest-final-full --junitxml=.artifacts/reports/final-python.xml
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit
node node_modules/vitest/vitest.mjs run --config vitest.config.ts --reporter=dot --reporter=junit --outputFile.junit=.artifacts/reports/final-frontend.xml
node node_modules/vite/bin/vite.js build
.artifacts/venvs/dev/Scripts/python.exe -m build --installer uv
.artifacts/venvs/dev/Scripts/python.exe scripts/verify_distribution.py
```

Windows 测试需要允许 asyncio 的本地 socketpair；沙箱阻断时初始化会挂起。本轮使用获准的本地测试权限完成，未以修改产品事件循环规避环境限制。构建工具通过临时隔离环境安装，未升级产品依赖。

报告：`.artifacts/reports/final-python.xml`、`final-frontend.xml`、`packaging.json`；构建和发行验证日志为 `final-build.log`、`final-distribution.log`。

## 当前开发实例

已核对并停止旧31388／31390进程族。仅清理当前 dev workspace 中的测试数据库、托管对象、预览、暂存和旧数据库备份；外部原图、测试数据集、ZIP、配置、服务令牌和既有CPU runtime保留。

新库 revision 为0009，素材／设备／项目／组均为空。重启后主页、服务健康、ComfyUI代理健康均返回200；实际提供的JS／CSS与本次构建字节一致。原全局MCP命令发现58工具；CLI、MCP和前端代理均查询同一空库，全局注册未修改。

入口：<http://127.0.0.1:31388/>。由用户刷新后手动检查。未执行 computer use 点击，未重导入整套真实素材。

运行证据：`.artifacts/reports/final-dev-reset.json` 和 `final-runtime.json`。
