# ③ 外部软件接入与环境

拥有固定软件包、安装／就绪及实际调用观察。`public.py`提供共享能力，`bundles.py`处理独立Bundle，`routes.py`由应用装配。Siril程序、操作和适配器来自独立私有仓库；节点定义归④、图与运行归⑤。

Bundle SDK v1保留已发布单图输入／输出契约；v2消费真实具名图像／序列／文件输入、多输出与分析文件。契约见`contracts/bundles.py`、`contracts/software.py`，具体命令和参数声明仍在独立Bundle，不在平台生成空节点。宿主负责进程、实际观察、取消、输出范围检查；分析与科学输出分别交⑤／②检查，进程退出不等于节点结果已就绪。

开发预览可用进程级`ASTROPHOTOFLOW_BUNDLE_CATALOG`读取独立目录快照，默认仍使用包内固定发布目录。覆盖不会更新默认workspace、全局MCP或正常dev；同样必须固定新tag与SHA、走现有安装计划／网页确认及实际原生加载。快照导出要求干净已提交checkout且HEAD与tag一致，不能把脏工作区冒充旧SHA。操作见[开发流程](../../../../docs/development/README.md)。
`environment.py`提供两侧共用的 Bundle 子进程环境；Windows 的程序搜索路径只使用 Bundle 程序目录和系统目录，其他环境值保留，不修改宿主环境。

`releases.py`从维护清单指定的官方Git仓库发现标签，复用系统Git凭据，以提交SHA缓存声明元数据。查看版本只取manifest和目录信息；所选版本的JSON声明通过批量blob获取，程序及适配器在安装确认后取得。选择令牌绑定官方来源、tag、commit及manifest，语言和latest标记不参与令牌；安装计划及实际checkout均核对固定目标。旧的仅程序版本请求继续使用原固定目录，不解释为远端latest。版本查询失败独立报告并保留上次成功列表，不接管已安装包的状态或卸载能力。

安装状态原子替换遇到 Windows `WinError 5` 时最多尝试5次，间隔50毫秒。进度写入耗尽尝试只记日志、保留上次进度，下一次直接写最新值；最终状态写入失败必须返回“安装结果未能保存，需核对”，不报告成功或自动重装。其他错误正常返回。

## 本模块必须保持

Bundle维护与热加载遵循[软件和节点需求](../../../../docs/requirements/README.md#fr-03-软件适配与能力目录)。记录准确Bundle／软件版本；当前只做开发构建，未知先查询，不自动重放。

实际类型看`contracts`及公开代码，不从旧详设抄签名。完整用户规则见 [需求](../../../../docs/requirements/README.md)，实现与验收状态见 [当前上下文](../../../../docs/development/current-context.md)；不在这里重复维护进度。

## 定位与验证

- [源码导航](../../../../docs/architecture/module-map.md)定位真实入口；[架构](../../../../docs/architecture/overview.md)规定跨模块边界。
- 测试位置：`tests/modules/software`。是否运行依用户当前要求，命令见 [开发流程](../../../../docs/development/README.md)。
- 通用节点编辑、完整工作流运行、记忆及后续能力按 [当前计划](../../../../docs/development/implementation-plan.md)选择实际任务，不因目录或定义文件存在而认定交付。
