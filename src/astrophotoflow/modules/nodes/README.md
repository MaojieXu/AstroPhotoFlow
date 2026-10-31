# ④ 节点构建与发布

拥有workspace JSON可编辑定义、更新差异和派生节点目录。`public.py`是定义公开操作，`catalog.py`联合③公开元数据，`routes.py`提供查询。Bundle原生加载在`interfaces/bundle_nodes.py`，不在本模块建立执行器。

## 本模块必须保持

节点名称和分类由声明及 Bundle 双语显示资料提供。原生目录使用稳定路径，语言切换只改变显示标签；旧声明缺少分类时仍归入软件根目录。分类不改变节点类型、端口或执行绑定，已有画布自定义标题保留。

保存不以测试通过为门槛；最近测试由⑤读取。更新先确认影响，实例全参数用新版默认；同方向／同名／同类型端口保线（含重排），变化端口断线。输入／输出各自名称唯一，不扩展到任意第三方节点。在途内容和历史不改。

实际类型看`contracts`及公开代码，不从旧详设抄签名。完整用户规则见 [需求](../../../../docs/requirements/README.md)，实现与验收状态见 [当前上下文](../../../../docs/development/current-context.md)；不在这里重复维护进度。

## 定位与验证

- [源码导航](../../../../docs/architecture/module-map.md)定位真实入口；[架构](../../../../docs/architecture/overview.md)规定跨模块边界。
- 测试位置：`tests/modules/nodes`。是否运行依用户当前要求，命令见 [开发流程](../../../../docs/development/README.md)。
- 通用节点编辑、完整工作流运行、记忆及后续能力按 [当前计划](../../../../docs/development/implementation-plan.md)选择实际任务，不因目录或定义文件存在而认定交付。
