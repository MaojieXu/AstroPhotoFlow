# core 基础设施

`core` 提供与业务无关的配置、进程与维护控制、数据库连接与迁移基础；不拥有业务事实，不读其他模块私有 ORM。

## 入口

`config.py` 定义 `Settings`（host、port、data_dir、allowed_origins、import_roots、file_workers、preview_workers、workspace，及 service_url、database_path、token_path、lock_path 派生属性）与 `CONFIG_PATH`；`workbench/` 准备工作区、控制服务启停并观察重启；`database/` 提供连接、schema 与 Alembic 迁移；`errors.py`、`files.py`、`localization.py` 提供共享错误、原子替换与错误本地化。

## workbench 子包

`workbench/__init__.py` 只显式导出 `create_workspace`、`initialize`、`install_frontend`、`prepare_runtime`、`request_restart`、`restart`、`restart_result`、`start`、`status`、`stop`、`update_running_state` 与 `WorkbenchError`；内部 `runtime`、`workspaces`、`state`、`processes`、`observations`、`operations`、`control` 分别负责准备、工作区、文件、进程、观察、控制准入与启停，外部只经公开函数。

## 不变量

配置保存不自动重启，性能参数在下次显式重启后生效；繁忙或无法确认空闲时拒绝重启；维护操作使用公开的 `update_running_state`，不在配置解析中写运行状态。

## 依赖方向

`core` 不导入 `modules` 与 `interfaces`；业务模块可依赖 `core` 与 `contracts`。模块职责见[架构](../../../docs/architecture.md)。

## 测试

`tests/core/` 覆盖配置、工作台、迁移与本地化；`tests/packaging/` 覆盖打包交付。
