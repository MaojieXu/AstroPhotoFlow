# nodes 模块

拥有 workspace 工作流 JSON 中的可编辑节点定义、更新差异与派生节点目录；不执行节点，也不建执行器。

## 公开入口

`public.py` 只导出真实能力：`create_definition`、`describe_node`、`get_definition`、`list_definitions`、`list_nodes`、`preview_definition_update`、`replace_package_definitions`、`update_definition`。

## 内部结构

`storage.py` 读写定义文件，`bindings.py` 校验执行绑定，`changes.py` 计算差异，`definitions.py` 编排写入，`catalog.py` 联合 software 的公开元数据生成目录。

## 与外部的关系

HTTP 查询路由在 `interfaces/http/nodes.py`；Bundle 定义的加载在 `interfaces/native/bundles/`，本模块不建执行器；软件包与调用归 software，画布与执行归 ComfyUI。

## 不变量

节点名称与分类来自声明及 Bundle 双语显示资料，语言切换只改显示标签；分类变化不改节点类型、端口或执行绑定；旧声明缺分类时归入软件根目录；已有画布自定义标题不被覆盖。

## 测试

`tests/modules/nodes/`。节点更新规则见[节点子系统](../../../../docs/subsystems/nodes.md)。
