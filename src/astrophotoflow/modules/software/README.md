# ③ 外部软件接入与环境

拥有固定软件包、安装／就绪及实际调用观察。`public.py`只显式导出共享能力，`packages/`与`execution/`分别实现包维护与具体执行，`bundles/`处理独立Bundle，HTTP适配位于`interfaces/http/software.py`，由应用装配。Siril程序、操作和适配器来自独立私有仓库；节点定义归nodes；图、队列和执行历史归ComfyUI；具体调用归software，已检查结果归data。原workflows目录已拆除；跨模块装配归interfaces/application。

Bundle SDK仅支持v2，消费真实具名图像／序列／文件输入、多输出与分析文件。契约见`contracts/bundles.py`、`contracts/software.py`，具体命令和参数声明仍在独立Bundle，不在平台生成空节点。宿主负责进程、实际观察、取消、输出范围检查；分析schema与科学输出交data公开能力检查，接入层负责组合，进程退出不等于节点结果已就绪。

操作声明的可选 `automatic_result_preview` 布尔值允许该操作成为自动结果计算目标和依赖，缺省为false；节点目录提供同名能力。显式自动目标不改变原生输出节点身份，整条依赖链均须允许自动执行。主进程正常退出后最多观察已知进程树5秒，确认停止再发布完整结果；仍活动或无法核实时保留unknown，不据此重跑。

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
- 通用节点编辑、原生科学处理闭环、记忆及后续能力按 [当前计划](../../../../docs/development/implementation-plan.md)选择实际任务，不因目录或定义文件存在而认定交付。

Bundle Python由`bundles/loader.py`按独立包命名空间加载，实际内容指纹变化时失效整个自有模块树；从源码编译避免旧时间戳字节码。开发构建采用development.json中的模块名（Siril为`tools.build_catalog`），经`python -m`执行，不保留脚本路径分支。默认发布目录固定为已有SDK v2开发tag v0.2.0-dev.2（5d16fb6fc10b4ee57de428d6eba522c918b1b441），本地开发绑定另有dirty／内容指纹；不得将此拆分当成G6全部完成。
