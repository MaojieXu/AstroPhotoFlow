# ③ 外部软件接入与环境

拥有固定软件包、安装／就绪及实际调用观察。`public.py`提供共享能力，`metadata.py`是领域服务与原生引擎共用的轻量 Bundle 元数据读取入口，`bundles.py`处理独立Bundle，`routes.py`由应用装配。Siril Auto Stretch程序与适配器来自独立私有仓库；节点定义归④、图与运行归⑤。

`environment.py`提供两侧共用的 Bundle 子进程环境；Windows 的程序搜索路径只使用 Bundle 程序目录和系统目录，其他环境值保留，不修改宿主环境。

安装状态原子替换遇到 Windows `WinError 5` 时最多尝试5次，间隔50毫秒。进度写入耗尽尝试只记日志、保留上次进度，下一次直接写最新值；最终状态写入失败必须返回“安装结果未能保存，需核对”，不报告成功或自动重装。其他错误正常返回。

## 本模块必须保持

Bundle维护与热加载遵循[软件和节点需求](../../../../docs/requirements/README.md#fr-03-软件适配与能力目录)。记录准确Bundle／软件版本；当前只做开发构建，未知先查询，不自动重放。

实际类型看`contracts`及公开代码，不从旧详设抄签名。完整用户规则见 [需求](../../../../docs/requirements/README.md)，实现与验收状态见 [当前上下文](../../../../docs/development/current-context.md)；不在这里重复维护进度。

## 定位与验证

- [源码导航](../../../../docs/architecture/module-map.md)定位真实入口；[架构](../../../../docs/architecture/overview.md)规定跨模块边界。
- 测试位置：`tests/modules/software`。是否运行依用户当前要求，命令见 [开发流程](../../../../docs/development/README.md)。
- 通用节点编辑、完整工作流运行、记忆及后续能力按 [当前计划](../../../../docs/development/implementation-plan.md)选择实际任务，不因目录或定义文件存在而认定交付。
