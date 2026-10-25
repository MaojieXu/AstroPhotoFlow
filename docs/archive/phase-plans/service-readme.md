# AstroPhotoFlow 本地资产服务

本服务以独立进程运行。ComfyUI 加载 AstroPhotoFlow Extension 时会复用已认证且健康的服务，或自动启动一个由扩展管理的服务并监控其状态。扩展不会安装依赖或自动迁移现有数据库。第一阶段的项目、设备和拍摄配置管理继续可用；第二阶段增加素材导入、资产资料编辑、数据集、项目选用和 FITS 显示。产品数据库不会预置演示资产。

## 环境与配置

需要 Python 3.11+ 和 uv。复制配置示例到：

```text
~/.config/astrophotoflow/config.toml
```

示例内容在 [config.example.toml](config.example.toml)。配置中的数据目录独立于扩展及 ComfyUI；默认是 `~/.local/share/astrophotoflow`。服务只绑定本机回环地址。需要导入素材时，在共享配置中添加一个或多个 `[[imports.roots]]`，每项包含唯一 `id` 和绝对 `path`；没有配置来源时，管理及查询仍可用，导入页会提示未配置。

从仓库根目录安装锁定依赖：

```bash
uv sync --project service --locked
```

日常使用时启动 ComfyUI 即会启动或复用资产服务。扩展在当前进程的 `PATH` 和 `~/.local/bin/uv` 中查找 uv，以锁定依赖启动服务并等待就绪，首次等待最多 20 秒；启动 ComfyUI 不会安装依赖或升级已有数据库。

首次启动服务会创建数据目录、仅当前用户可读的 `service.token`，并为新数据库初始化 schema。令牌只由服务及 ComfyUI 后端代理读取，不放入浏览器。需要诊断时也可以手动启动服务：

```bash
uv run --project service apf-service serve
```

手动启动会在终端前台运行。端口被占用或配置无效时会明确失败，不会改用其他地址。

ComfyUI 浏览器只能通过 `/astrophotoflow/api/v1/...` 同源代理调用服务；本机令牌由扩展后端持有。导入来源只接受配置根目录内的相对路径。

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

`GET /api/v1/library/items` 支持 `sort_by`：`created_at`、`name`、`classification`、`camera`、`parameter_mode`、`exposure_seconds`、`sensor_temperature_c`、`binning`、`cfa_pattern`、`optical_system`、`filter`、`integration_seconds`、`storage_mode`、`status` 和 `notes`，并支持 `order=asc|desc`。搜索和筛选先应用于完整匹配集，再排序和分页。

`DELETE /api/v1/library/items` 接收 `{ "items": [{ "entry_type": "asset", "id": "<uuid>", "revision": 1, "current_version_id": null }] }`；数据集项将 `entry_type` 设为 `dataset`，并携带当前 `current_version_id`。服务在一个事务中校验整批 revision 和数据集版本；成功只隐藏素材库入口，不删除文件、资产、版本、数据集成员或项目引用。重复请求返回 `removed_count: 0`。

测试使用隔离临时数据库，不会向产品库写入测试资产：

```bash
uv sync --project service --extra test
uv run --project service --extra test pytest service/tests
```

支持格式、实际解析能力、固定预览预设、解码依赖许可证及合成验收样本见[资产格式支持矩阵](../docs/资产格式支持矩阵.md)。FITS、常规图像、相机 RAW、XISF、HEIF 和视频首帧仅持久化最长边 100 px 的 JPEG 缩略图；素材列表展示小图，点击图片不打开预览。SER 使用格式读取器，其余视频使用系统 FFmpeg。RAW 的具体支持取决于 LibRaw 支持的相机型号和编码；NumPy 只入库。导入任务保留逐文件内容、元数据、预览状态和同条件组的拉伸参数；取消后只重试已登记项，`resume` 仅用于服务中断的原任务。

既有素材缺少预览时，可在服务停止或持有数据库锁的环境中执行 `uv run --project service --locked --no-sync apf-service previews backfill`。命令只补缺失预览，单项失败写入服务日志并继续后续项目。

本阶段不提供导入后扫描或文件变化监控、科学处理、视频逐帧、NumPy 切片、软件 Node、MCP 或 Agent 能力。
