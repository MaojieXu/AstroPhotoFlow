# ③ 外部软件接入与环境

拥有固定软件包、安装／就绪及实际调用观察。`public.py`提供共享能力，`bundles.py`处理独立Bundle，`routes.py`由应用装配。Siril程序、操作和适配器来自独立私有仓库；节点定义归④、图与运行归⑤。

Bundle SDK v1保留已发布单图输入／输出契约；v2消费真实具名图像／序列／文件输入、多输出与分析文件。契约见`contracts/bundles.py`、`contracts/software.py`，具体命令和参数声明仍在独立Bundle，不在平台生成空节点。宿主负责进程、实际观察、取消、输出范围检查；分析与科学输出分别交⑤／②检查，进程退出不等于节点结果已就绪。

开发预览可用进程级`ASTROPHOTOFLOW_BUNDLE_CATALOG`读取独立目录快照，默认仍使用包内固定发布目录。覆盖不会更新默认workspace、全局MCP或正常dev；同样必须固定新tag与SHA、走现有安装计划／网页确认及实际原生加载。快照导出要求干净已提交checkout且HEAD与tag一致，不能把脏工作区冒充旧SHA。操作见[开发流程](../../../../docs/development/README.md)。

## 本模块必须保持

计划须当前网页确认；维护繁忙拒绝，空闲重启后实际加载才就绪。卸载保留素材、定义和工作流；敏感登录／许可由用户输入。记录准确Bundle／软件版本；当前只做开发构建，未知先查询，不自动重放。

实际类型看`contracts`及公开代码，不从旧详设抄签名。完整用户规则见 [需求](../../../../docs/requirements/README.md)，实现与验收状态见 [当前上下文](../../../../docs/development/current-context.md)；不在这里重复维护进度。

## 定位与验证

- [源码导航](../../../../docs/architecture/module-map.md)定位真实入口；[架构](../../../../docs/architecture/overview.md)规定跨模块边界。
- 测试位置：`tests/modules/software`。是否运行依用户当前要求，命令见 [开发流程](../../../../docs/development/README.md)。
- 通用节点编辑、完整工作流运行、记忆及后续能力按 [当前计划](../../../../docs/development/implementation-plan.md)选择实际任务，不因目录或定义文件存在而认定交付。
