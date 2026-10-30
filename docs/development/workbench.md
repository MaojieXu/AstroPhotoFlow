# 使用本地网页工作台

当前仅开发构建，Windows x64／Python3.12／CPU有既有证据，完整交付和其他平台见 [当前上下文](current-context.md)。安装平台wheel不要求Node；Siril独立Bundle需要Git访问，缺少Git时按平台计划准备受管MinGit，私有凭据由用户在系统Git中提供。

## 安装并打开

使用实际取得的开发wheel路径替换示例，不把文件名示例当作正式发布：

```powershell
py -3.12 -m venv .apf-env
.\.apf-env\Scripts\python.exe -m pip install <开发wheel路径>
.\.apf-env\Scriptspf.exe init --workspace D:\AstroPhotoFlow\workspace --service-port 18190 --comfyui-port 18188
.\.apf-env\Scriptspf.exe start --workspace D:\AstroPhotoFlow\workspace
.\.apf-env\Scriptspf.exe status --workspace D:\AstroPhotoFlow\workspace
```

打开start返回的实际网页地址，端口冲突时会自动选择；不要固定猜测地址。首次初始化准备固定CPU运行依赖，手动处理不需要生成式模型。

## 日常操作

- 画布常驻，节点库下有素材库、工作流及软件包；侧栏可调宽／收起。设备管理在素材库“导入”旁，预设在所属组合内。
- 导入直接选择本机文件或一个文件夹，文件夹只取当前层支持文件，无需先配置授权根。原件就绪与后台预览分开。
- 素材名称点击后选画布落点，或整行拖入；缩略图点击查看。固定组可切成员，图片、名称和参数保留。
- 软件页查看实际就绪与原因；安装／卸载在原生弹窗确认准确计划。Siril当前可执行操作是Auto Stretch，命令资料不等于全部可执行节点。
- 从设置进入工作台配置。保存不自动重启，显式重启采用保存值；未保存内容不能用于重启。繁忙或无法确认空闲时拒绝。

修改端口后当前页面不能跨端口自动重连，按界面或`apf status`返回的新地址打开。断连先查询已有请求，不自动再提交一次。关闭浏览器不停止已受理任务。

## 停止、诊断和数据保护

```powershell
.\.apf-env\Scriptspf.exe stop --workspace D:\AstroPhotoFlow\workspace
```

停止等待任务排空；超时或身份未知会保留记录，不表示已停止，先查询状态及日志。日志位于workspace的`logs`，不要输出service.token。

业务数据在指定workspace，网页在`web`，原生工作流在`comfyui-user`，素材／预览在`data`；程序runtime与之分离。默认workspace由用户TOML的`[workspace] default`选择，显式workspace／配置环境优先，控制命令不改变默认位置。

已有数据库不自动升级，升级前保护数据并按明确计划执行；平台不提供workspace搬迁服务。不要只复制运行中的SQLite主文件。CLI／MCP选定目标及schema查询见 [API入口](../api/README.md)，源码开发见 [开发命令](README.md)。
