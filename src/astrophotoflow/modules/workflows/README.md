# ⑤ 工作流、执行与Agent交互

协调明确活动画布、科学输入和软件调用。`canvas.py`负责在线页面／图操作，`software_calls.py`协调②③，`siril_preview.py`提供显示样本预览。当前已有这些窄实现，完整项目关联、持久运行记录及多次逐节点预览尚未交付。

具名Bundle调用在受理时固定定义、参数和Bundle提交；图像／序列／文件引用均由公开数据能力解析。完成结果先经过科学文件／容器帧数／分析schema检查，再发布输出引用和轻量预览。按明确原生prompt查询的调用摘要与分析文件由HTTP、Python客户端、CLI `run-calls` 和MCP共用；未知调用只补实际观察，不重跑。它们是当前调用事实的增量，不替代尚未完成的完整项目运行库。

## 本模块必须保持

唯一当前图用原生JSON；复用保存、草稿、撤销、转换和队列。实际写入核对目标／内容／控制；手改接管、明确交回，切图暂停后续写／提交，已有运行继续。正式运行先成功保存；未知先查，预览归原图，只有所选完整结果交②。

实际类型看`contracts`及公开代码，不从旧详设抄签名。完整用户规则见 [需求](../../../../docs/requirements/README.md)，实现与验收状态见 [当前上下文](../../../../docs/development/current-context.md)；不在这里重复维护进度。

## 定位与验证

- [源码导航](../../../../docs/architecture/module-map.md)定位真实入口；[架构](../../../../docs/architecture/overview.md)规定跨模块边界。
- 测试位置：`tests/modules/workflows`。是否运行依用户当前要求，命令见 [开发流程](../../../../docs/development/README.md)。
- 通用节点编辑、完整工作流运行、记忆及后续能力按 [当前计划](../../../../docs/development/implementation-plan.md)选择实际任务，不因目录或定义文件存在而认定交付。
