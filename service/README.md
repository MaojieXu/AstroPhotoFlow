# AstroPhotoFlow 本地资产服务

本服务独立于 ComfyUI 运行。扩展提供同源代理，不会启动领域服务。当前阶段只管理项目、设备和拍摄配置，并以只读方式查询资产。产品数据库不会预置演示资产。

## 环境与配置

需要 Python 3.11+ 和 uv。复制配置示例到：

```text
~/.config/astrophotoflow/config.toml
```

示例内容在 [config.example.toml](config.example.toml)。配置中的数据目录独立于扩展及 ComfyUI；默认是 `~/.local/share/astrophotoflow`。服务只绑定本机回环地址。

从仓库根目录安装锁定依赖：

```bash
uv sync --project service
```

首次启动会创建数据目录、仅当前用户可读的 `service.token`，并通过 Alembic 初始化新数据库。令牌只由服务及 ComfyUI 后端代理读取，不放入浏览器。使用命令启动：

```bash
uv run --project service apf-service serve
```

服务在终端前台运行。端口被占用或配置无效时会明确失败，不会改用其他地址。

## 数据库状态与迁移

查询 revision：

```bash
uv run --project service apf-service db status
```

现有数据库不会在服务启动时自动迁移。检查升级提示和当前数据库状态后，显式执行：

```bash
uv run --project service apf-service db upgrade
```

升级已有受支持 revision 前，服务使用 SQLite backup API 在 `<data_dir>/backups/` 保存一致备份；新库初始化无需备份。迁移失败会保留原数据库、备份和诊断，服务不会启动。未知或没有 Alembic revision 的旧库不会被自动 stamp 或改写。

恢复步骤：

1. 停止服务和迁移进程。
2. 保留失败数据库及日志用于诊断；确认备份对应的 Alembic revision 和代码版本。
3. 把数据库备份恢复为 `<data_dir>/astrophotoflow.sqlite3`。先移走现有主库；若存在同名 `-wal`／`-shm` 文件，将其隔离后再恢复，不能与旧主库混用。
4. 用 `apf-service db status` 检查恢复后的 revision，再按需运行显式升级或启动服务。
5. 不覆盖 `service.token` 或整个数据目录；备份文件保留至恢复确认完成。

同一数据目录只能有一个服务或迁移进程持有管理锁。服务正常退出后锁会释放。

## 接口与验证

API 使用 `/api/v1` 和本机 Bearer 令牌。ComfyUI 浏览器通过 `/astrophotoflow/api/v1/...` 同源路径访问代理。接口以 [OpenAPI 快照](openapi.json) 为准；快照由当前 FastAPI 应用生成。

测试使用隔离临时数据库，不会向产品库写入测试资产：

```bash
uv sync --project service --extra test
uv run --project service --extra test pytest service/tests
```

本阶段不提供文件导入、散列计算、资产引用写入、预览、科学格式解析、任务队列或软件／MCP／Agent 能力。
