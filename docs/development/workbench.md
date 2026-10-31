# 使用本地网页工作台

当前仅开发构建，Windows x64／Python3.12／CPU有既有证据，完整交付和其他平台见 [当前上下文](current-context.md)。安装平台wheel不要求Node；Siril独立Bundle需要Git访问，缺少Git时按平台计划准备受管MinGit，私有凭据由用户在系统Git中提供。

## 安装并打开

使用实际取得的开发wheel路径替换示例，不把文件名示例当作正式发布：

```powershell
py -3.12 -m venv .apf-env
.\.apf-env\Scripts\python.exe -m pip install <开发wheel路径>
.\.apf-env\Scripts\apf.exe init --workspace D:\AstroPhotoFlow\workspace --service-port 18190 --comfyui-port 18188
.\.apf-env\Scripts\apf.exe start --workspace D:\AstroPhotoFlow\workspace
.\.apf-env\Scripts\apf.exe status --workspace D:\AstroPhotoFlow\workspace
```

打开start返回的实际网页地址，端口冲突时会自动选择；不要固定猜测地址。首次初始化准备固定CPU运行依赖，后续相同版本复用已完成环境。也可先运行`apf runtime prepare`准备软件，再用`apf workspace create --workspace <路径>`只建空配置和目录；打开网页仍需`init`或明确提供已有网页资源。手动处理不需要生成式模型。

## 日常操作

- 画布常驻，节点库下有素材库、工作流及软件包；侧栏可调宽／收起。设备管理在素材库“导入”旁，预设在所属组合内。
- 导入直接选择本机文件或一个文件夹，文件夹只取当前层支持文件，无需先配置授权根。原件就绪与后台预览分开。
- 素材名称点击后选画布落点，或整行拖入；缩略图点击查看。固定组可切成员，图片、名称和参数保留。
- 软件页查看实际就绪与原因；安装／切换版本／卸载在原生弹窗确认准确计划。实际节点能力以所安装Bundle及其就绪状态为准，命令资料不等于可执行节点。
- 从设置进入工作台配置。保存不自动重启，显式重启采用保存值；未保存内容不能用于重启。繁忙或无法确认空闲时拒绝。

修改端口后当前页面不能跨端口自动重连，按界面或`apf status`返回的新地址打开。断连先查询已有请求，不自动再提交一次。关闭浏览器不停止已受理任务。

## 中英文

在“设置 → 常规 → 语言”选择English或简体中文。首次使用按浏览器偏好选择并保存到当前workspace的原生`Comfy.Locale`；繁体中文设置归并为简体中文，其他不支持的设置归并为英文。各workspace互不影响。

网页即时更新展示；MCP连接读取同一保存值，尚未选择时使用英文。修改语言后重新连接MCP，以刷新客户端缓存的工具说明。语言设置不可读或损坏时明确报错，不通过另建配置覆盖。

用户名称、原始命令、参数／端口标识及原始软件日志保持原文。Bundle双语展示需要该版本提供翻译资源；旧Bundle缺少时显示原始文案。切换语言不修改工作流内容、科学输入或参数值。

## Bundle版本

软件包页为每个Bundle提供一个版本下拉框，进入页面时检查官方Git标签，也可点击“刷新版本”。Bundle版本与程序版本分别展示；两个通道分别标记“最新正式版／最新开发版”。未安装时正式版优先，缺少兼容正式版时选兼容开发版；已有安装时保留当前版本。灰色项会说明系统、SDK、声明格式或必要文件的不兼容原因。

选择版本后点击“安装”或“切换版本”，复核当前／目标Bundle版本、程序版本、tag、commit及节点变化，再确认。可以选择兼容的旧版本；切换后的缺失节点保留提示，素材和工作流按原有规则保留。确认计划始终指向当时选定的提交，之后发现新版本不会改动目标。

私有仓库访问沿用系统Git凭据。检查失败时保留已安装信息及上次成功列表，并显示失败和上次检查时间；实际安装仍须重新验证目标。历史实验标签`v0.1.0`、`v0.1.1`及未发布tag的本地候选不进入官方安装列表。

## 停止、诊断和数据保护

```powershell
.\.apf-env\Scripts\apf.exe stop --workspace D:\AstroPhotoFlow\workspace
```

停止等待任务排空；超时或身份未知会保留记录，不表示已停止，先查询状态及日志。日志位于workspace的`logs`，不要输出service.token。

业务数据在指定workspace，网页在`web`，原生工作流在`comfyui-user`，素材／预览在`data`；程序runtime与之分离。默认workspace由用户TOML的`[workspace] default`选择，显式workspace／配置环境优先，控制命令不改变默认位置。

已有数据库不自动升级，升级前保护数据并按明确计划执行；平台不提供workspace搬迁服务。不要只复制运行中的SQLite主文件。CLI／MCP选定目标及schema查询见 [API入口](../api/README.md)，源码开发见 [开发命令](README.md)。
