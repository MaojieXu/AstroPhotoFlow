# 配置与开发环境收尾验收

日期：2026-10-25。基线：feature/remake / 4cc317d。本轮统一运行配置、替换旧开发入口并清除历史运行目录，未增加业务接口、表、schema revision 或 MCP 工具。

## 交付内容

- `astrophotoflow.config` 是后端、代理、CLI/MCP 和工作台的共享配置模块，复用原有类型和校验。显式路径优先于环境，再读取 active-workspace 指针或默认文件；选定配置无效时直接失败。
- `.env.example` 与根 `config.example.toml` 提供模板。实际 `.env` 和 `.artifacts/workspaces/dev/config.toml` 不提交；端口／数据／素材根目录由 TOML 管理，令牌继续为 workspace 内文件。
- 使用现有 uv 加载 dotenv，无新依赖。启动 uv 前明确设置项目 Python 环境；Windows MCP 注册的绝对路径使用正斜杠，避免路径转义歧义。
- MCP 注册已改为开发环境 uv 加载根 `.env` 后启动 `apf mcp`。注册条目不再保存旧 ASTROPHOTOFLOW_CONFIG 或 PYTHONPATH；其他 Codex/MCP 配置经逻辑散列对比未变。
- 新 workspace 是 `.artifacts/workspaces/dev`，使用新空数据库；CLI 默认指针已同步，前端 31388、资产服务 31390。
- 标准用户 CPU runtime 已核对固定 ComfyUI commit、torch 2.14.1+cpu、torchvision 0.29.1+cpu、前端 1.57.1，直接复用，没有重新安装 CPU 依赖。当前插件和前端产物已同步。

## 实际验证

| 范围 | 结果 |
|---|---|
| 受影响 Python 回归 | 首轮 71 项中 70 passed；唯一失败为合并配置后的错误文案差异。统一文案后代理和后端两项定向回归均通过，71 个不同用例最终均有通过证据 |
| 配置覆盖 | 显式路径、环境、当前指针、默认位置的优先级；选定文件缺失不回退；相对数据目录；无效配置；各入口一致 |
| 退出进程回归 | 单元回归确认子进程退出后才清除状态；真实 stop 使原 6 个进程全部退出，31388/31390 释放，再次 start/status 为 running |
| 真实 MCP 与 CLI | 使用写入 Codex 的同一注册配置，从仓库外启动 stdio；五工具集合精确匹配，list_assets 与 CLI 查询一致且 total=0 |
| 前端与 API | 主页、代理健康和素材列表均 200，新库 schema 为 0006_library_trash_cleanup_state，素材总数为 0 |
| 静态资源 | JS/CSS 的构建文件、runtime 插件文件和 HTTP 响应逐字节相等；前端源码未改，沿用原 111 项通过记录 |
| 发行包 | 共享配置模块改变包内导入路径，已重建 wheel/sdist；源码目录外安装、无 Node 的 sdist 重建和重新安装检查通过 |

原有 ORM 迁移对比仍有循环外键排序 warning，未为此改变模型。没有重导入全量真实素材，没有 computer use 或前端自动点击。

## 清理与保留

整个旧 `service/`、`test/` 已解除配置和进程依赖后删除。历史测试工作台退出，包括仍使用旧解释器的预览实例；VS Code Black/Pylint 的本机工作区配置已切到新开发环境，避免后台工具重新占用旧解释器。

旧测试目录中的 RAW、HEIF 输入及来源／散列清单移至忽略的 `tests/data/reference-samples/`，原 Astro Dataset、原始 ZIP 和 reference 项目保持。R4 关键摘要保留为 docs/archive/acceptance/trash-r4-2026-10-24.md。历史数据库和可重现运行缓存不迁移。

详细本地证据在 `.artifacts/reports/` 的 config-tests、config-message-tests、dev-lifecycle、dev-integration、config-build、config-packaging 文件，以及 `.artifacts/maintenance/` 的入口迁移和清理记录。日志不进入 Git，实际本机配置不进入 Git。
