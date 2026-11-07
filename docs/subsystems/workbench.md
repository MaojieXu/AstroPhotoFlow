# 工作台

[English](workbench.en.md) | 中文

配置、workspace 目录、进程控制与维护归 core 模块；常驻进程只有原生网页/引擎与 FastAPI 领域服务两个。模块职责见[架构](../architecture.md)，使用步骤见[使用说明](../user/workbench.md)。

## 职责

- 解析配置与默认 workspace，准备 runtime，启动、停止与查询两个常驻进程并记录采用的配置。
- 提供工作台配置的读取、保存与显式重启；保存不自动重启，重启采用已保存值。
- 维护服务令牌、日志与运行时文件；不拥有业务事实。

## workspace 布局

- `config.toml` 与 `data/`；data 相对配置解析，默认放在 workspace 下。
- `data/` 下是 SQLite 数据库、受管原件、previews、上传暂存与 service.token。
- `input/`、`output/`、`logs/`、`context/`、`comfyui-user/`、`comfyui-data/` 与 `run/` 存放原生与运行文件；`input/` 不是素材库原件目录。
- 详细持久内容与缓存归属见[架构](../architecture.md)。

## 启动与控制

- 启动准备 runtime 与网页目录后启动两个进程；端口冲突时选择实际端口。
- 配置保存遇到繁忙或无法确认空闲时拒绝；未保存内容不能用于重启。
- 停止等待任务排空；超时或身份未知保留记录并说明未确认停止。
- 已有数据库不自动升级；日志在 workspace 的 `logs/`，不输出服务令牌。

## 输入与输出

- 输入：配置文件、显式 workspace 与控制命令、工作台配置修改。
- 输出：实际采用的配置与端口、进程记录、维护结果与配置状态。
- 连接断开时先查询已有请求，不自动重复提交。

## 对外契约

- HTTP 路由在 `src/astrophotoflow/interfaces/http/system.py` 与 `maintenance.py`；配置与控制在 `src/astrophotoflow/core/config.py` 与 `core/workbench/`。
- HTTP 认证与依赖在 `src/astrophotoflow/interfaces/http/dependencies.py`；字段以 [OpenAPI 快照](../api/openapi.json) 为准。
- 本机启停在 HTTP 服务外执行，业务读写仍走各模块公开入口。

## 测试与边界

- 测试在 `tests/core/` 与 `tests/packaging/`。
- 维护接口经公开入口更新运行状态；业务规则不进入 core。
