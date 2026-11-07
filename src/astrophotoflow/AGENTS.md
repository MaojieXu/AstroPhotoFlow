# 包结构约束

- 包内分层固定：`core` 放与业务无关的基础设施，`modules` 放业务能力，`contracts` 放跨边界共享模型，`interfaces` 放接入与装配；不新增平行分层，业务规则不进 `core`。
- 包根 `client.py` 与 `cli.py` 是保留公开入口（`AssetClient` 与 `apf`），不迁入子包或改名；`comfyui/proxy.py` 是固定引擎网关，不在其中扩展业务。
- `vendor/` 是随包发布的资源快照（ComfyUI 发行包与路由清单、Bundle 目录），按包数据读取，不当源码修改。
- 业务变化只改所属模块并通过公开入口协作；不恢复已取消的模块树，也不以空包占位未实现能力。
- 模块职责与数据归属见[架构](../../docs/architecture.md)；修改后运行 `uv run --locked --no-sync pytest -q`。
