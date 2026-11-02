# ② 数据与资产管理开发边界

- 先读本目录 [README](README.md)、受影响代码与测试；跨模块才查 [架构](../../../../docs/architecture/overview.md)，不默认读取历史草案。
- 保留稳定身份、固定成员顺序、资料revision及省略／null／0语义。新运行用纠正资料，旧运行不改。登记、原件可读、解析和预览分开；预览不当科学输入。公开交接不暴露私有ORM；已检查结果归data，图／队列／历史归ComfyUI，具体调用归software。
- 通过公开入口合作，不读他模块私有ORM；只改任务范围，不创建占位接口或空服务。
- 当前状态统一看 [上下文](../../../../docs/development/current-context.md)，不在AGENTS重复“已实现／未实现”。
- 相关验证在`tests/modules/data`；运行遵循根AGENTS和用户本次要求，不因列有命令就自动执行。
