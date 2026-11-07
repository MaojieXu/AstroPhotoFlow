# 节点

[English](nodes.en.md) | 中文

workspace 中可编辑的节点定义、更新差异与派生节点目录归 nodes 模块；模块职责见[架构](../architecture.md)，节点执行归 software 与原生侧。

## 职责

- 把用户定义与 Bundle 同步副本保存到 workspace 的节点目录，并用来源字段区分。
- 联合软件公开元数据装配节点目录，提供名称、分类、端口、参数与内容令牌。
- 计算定义更新差异，先确认影响再写入。

## 更新规则

- 更新时实例参数全部采用新版默认值。
- 同方向、同名、同类型的端口保留连线，包括重排；变化的端口断线。
- 输入与输出各自名称唯一；规则不扩展到任意第三方节点。
- 在途内容与历史不改；保存不以测试通过为门槛。

## 目录与显示

- 名称与分类来自节点声明与 Bundle 双语显示资料；切换语言只改变显示标签。
- 缺少分类的旧声明归入软件根目录；分类不改变节点类型、端口或执行绑定。
- 已有画布上的自定义节点标题保留。

## 输入与输出

- 输入：定义写入、Bundle 同步与更新确认。
- 输出：节点定义、差异、写入结果与节点能力目录。
- 校验失败清晰返回；引用的定义不存在或缺参数时不猜测默认值。

## 对外契约

- HTTP 查询在 `src/astrophotoflow/interfaces/http/nodes.py`；契约在 `src/astrophotoflow/contracts/nodes.py`。
- Bundle 的原生加载在 `src/astrophotoflow/interfaces/native/bundles/`，本模块不建立执行器。
- 字段以 [OpenAPI 快照](../api/openapi.json) 为准。

## 测试与边界

- 测试在 `tests/modules/nodes/`。
- 节点执行与进程观察归 software；画布写入与撤销归原生桥接。
