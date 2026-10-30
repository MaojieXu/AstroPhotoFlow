# 节点界面与客户端

当前`client.ts`提供节点目录／定义的消费类型及客户端，公开导出以包`src/index.ts`为准。通用节点制作、影响确认和最近测试界面仍待补，不由目录查询推定已实现。

未来界面展示定义、常用／高级参数、真实加载原因及最近测试。保存不以测试通过为门槛；确认更新后参数与端口规则统一按 [需求](../../../../../../docs/requirements/README.md)执行，不在UI另建版本或测试权威。

原生节点注册、控件、连线与子图协调属于 [宿主桥接](../../../../../src/platform/astrophotoflow)，UI不导入其Store或画布。定义权威见 [nodes](../../../../../../src/astrophotoflow/modules/nodes/README.md)，进度／验收统一见 [当前上下文](../../../../../../docs/development/current-context.md)。
