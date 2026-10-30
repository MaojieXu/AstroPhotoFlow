# ⑤ 工作流、执行与Agent交互开发边界

- 先读本目录 [README](README.md)、受影响代码与测试；跨模块才查 [架构](../../../../docs/architecture/overview.md)，不默认读取历史草案。
- 唯一当前图用原生JSON；复用保存、草稿、撤销、转换和队列。画布编辑遵循[当前图与 Agent 编辑需求](../../../../docs/requirements/README.md#fr-02-原生工作流与画布)。正式运行先成功保存；未知先查，预览归原图，只有所选完整结果交②。
- 通过公开入口合作，不读他模块私有ORM；只改任务范围，不创建占位接口或空服务。
- 当前状态统一看 [上下文](../../../../docs/development/current-context.md)，不在AGENTS重复“已实现／未实现”。
- 相关验证在`tests/modules/workflows`；运行遵循根AGENTS和用户本次要求，不因列有命令就自动执行。
