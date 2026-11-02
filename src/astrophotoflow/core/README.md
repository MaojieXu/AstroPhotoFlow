# ① 公共基础设施

配置、进程／维护、数据库连接和迁移基础；HTTP认证和依赖归interfaces/http/dependencies.py；不拥有业务事实。`config.py`、`workbench/`及`database`是主要入口。默认workspace、保存／采用值、自动端口与启停已有实现。

## 本模块必须保持

不改用户默认workspace、全局MCP或真实数据。配置保存不重启，性能参数下次显式重启采用；繁忙／不能确认空闲拒绝。不建配置历史、workspace登记或搬迁服务。

实际类型看`contracts`及公开代码，不从旧详设抄签名。完整用户规则见 [需求](../../../docs/requirements/README.md)，实现与验收状态见 [当前上下文](../../../docs/development/current-context.md)；不在这里重复维护进度。

## 定位与验证

- [源码导航](../../../docs/architecture/module-map.md)定位真实入口；[架构](../../../docs/architecture/overview.md)规定跨模块边界。
- 测试位置：`tests/core tests/packaging`。是否运行依用户当前要求，命令见 [开发流程](../../../docs/development/README.md)。
- 通用节点编辑、原生科学处理闭环及后续能力按 [当前计划](../../../docs/development/implementation-plan.md)选择实际任务，不因目录或定义文件存在而认定交付。

workbench/__init__.py仅显式导出；runtime／workspaces／state／processes／observations／operations／control分别管理准备、工作区、文件、进程、观察、控制准入和启停。维护接口使用公开update_running_state，配置解析不再持有运行状态写入实现。
