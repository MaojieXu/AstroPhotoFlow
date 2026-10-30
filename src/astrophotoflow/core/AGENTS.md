# ① 公共基础设施开发边界

- 先读本目录 [README](README.md)、受影响代码与测试；跨模块才查 [架构](../../../docs/architecture/overview.md)，不默认读取历史草案。
- 不改用户默认workspace、全局MCP或真实数据。配置保存不重启，性能参数下次显式重启采用；繁忙／不能确认空闲拒绝。不建配置历史、workspace登记或搬迁服务。
- 通过公开入口合作，不读他模块私有ORM；只改任务范围，不创建占位接口或空服务。
- 当前状态统一看 [上下文](../../../docs/development/current-context.md)，不在AGENTS重复“已实现／未实现”。
- 相关验证在`tests/core tests/packaging`；运行遵循根AGENTS和用户本次要求，不因列有命令就自动执行。
