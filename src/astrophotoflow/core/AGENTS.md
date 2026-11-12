# 基础设施约束

- 先读本目录 README；`core` 不拥有业务事实，不导入 `modules`，不读其他模块私有 ORM。
- 不改用户默认 workspace、全局 MCP 注册、真实素材或正在运行的服务；启停与重启只经 `core` 的公开控制入口。
- 配置保存不自动重启；性能类参数在下次显式重启后生效；繁忙或无法确认空闲时拒绝重启。
- 不新建配置历史、workspace 登记表或数据搬迁服务；数据库结构由 `database/` 下的 Alembic 管理，当前基线与 v1／v2 数据保留规则见[开发文档](../../../docs/development.md#目录)。
- 测试位置 `tests/core/`、`tests/packaging/`。
