# ③ 外部软件接入与环境开发边界

- 先读本目录 [README](README.md)、受影响代码与测试；跨模块才查 [架构](../../../../docs/architecture/overview.md)，不默认读取历史草案。
- Bundle维护与热加载遵循[软件和节点需求](../../../../docs/requirements/README.md#fr-03-软件适配与能力目录)。记录准确Bundle／软件版本；当前只做开发构建，未知先查询，不自动重放。
- 通过公开入口合作，不读他模块私有ORM；只改任务范围，不创建占位接口或空服务。
- 当前状态统一看 [上下文](../../../../docs/development/current-context.md)，不在AGENTS重复“已实现／未实现”。
- 相关验证在`tests/modules/software`；运行遵循根AGENTS和用户本次要求，不因列有命令就自动执行。
