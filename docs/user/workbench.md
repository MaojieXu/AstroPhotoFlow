# 使用说明

[English](workbench.en.md) | 中文

本页是日常操作步骤；工作台的产品规则见[工作台规则](../product/workbench.md)，接口查询见[参考](../references.md)。

## 安装并打开

使用实际取得的开发 wheel 替换示例路径：

```powershell
py -3.12 -m venv .apf-env
.\.apf-env\Scripts\python.exe -m pip install <开发wheel路径>
.\.apf-env\Scripts\apf.exe init --workspace D:\AstroPhotoFlow\workspace --service-port 18190 --comfyui-port 18188
.\.apf-env\Scripts\apf.exe start --workspace D:\AstroPhotoFlow\workspace
```

打开 `start` 返回的实际网页地址；端口冲突时会自动选择，不要固定猜测地址。首次初始化准备固定 CPU 运行依赖，后续相同版本复用已完成环境。也可以先运行 `apf runtime prepare` 准备软件，再用 `apf workspace create --workspace <路径>` 只建空配置和目录；打开网页仍需 `init` 或明确提供已有网页资源。安装平台 wheel 不要求 Node；Siril 独立 Bundle 需要 Git 访问。手动处理不需要生成式模型。

## 界面

- 画布常驻；侧栏依次提供节点库、素材库、项目、工作流与软件包。
- 侧栏可以收起和调宽；素材库工具栏提供导入与设备管理入口，侧栏的设置按钮打开设置。

## 导入素材

- 在素材库选择导入，直接选择本机文件或一个文件夹；文件夹只取当前层支持的文件，不需要先配置授权根。
- 登记与原件就绪、后台预览分开显示；部分失败保留失败原因，可单独查看后重试。
- 导入通知只面向本次提交或当前会话，没有历史页或通知中心。

## 素材库与固定组

- 素材库提供简约列表与细节模式；点击素材名称后选择画布落点，或把整行拖入画布。
- 点击缩略图查看素材；固定集合可以切换成员，图片、名称与参数保留。
- 校准列显示最终 Master 名称，版本、来源与诊断按需展开。

## 画布编辑

- 节点的添加、参数、连线、布局、自动保存与撤销都按原生画布操作。
- 重要方案用原生另存为保存；浏览器草稿与撤销沿用原生机制。
- 外来工作流 JSON 按原生机制打开；缺少节点时保留提示，不自动安装。

## 运行与结果

- 运行、队列、进度与取消使用原生入口；运行时每次完成的图像节点产生自动预览。
- 选择完整结果后保存到素材库或导出到本机；格式与精度默认原样保留。
- 预览与缩略图不是科学原件；继续处理从真实完整文件开始。
- 比较结果时注意配准、尺寸、ROI 与拉伸是否一致，指标缺失不等于 0。

## 让外部 Agent 操作

- 在对话中向 Agent 明确说明要改的画布与目标，之后由 Agent 直接编辑该活动画布。
- 普通任务不需要逐节点确认；手动修改会使旧请求失效，Agent 应停止并说明。
- 关闭网页后不再接受画布写入；重连或换客户端时先读取实际状态。

## 软件包

- 软件包页显示每个 Bundle 的实际就绪状态与原因；实际节点能力以已安装 Bundle 及其就绪状态为准，命令资料不等于可执行节点。
- 安装、切换版本与卸载都在原生弹窗里复核准确计划后确认。
- 版本下拉框检查官方 Git 标签，也可刷新；灰色项说明不兼容原因，确认后复核版本、tag、commit 与节点变化。

## 设置

- 设置保存后不自动重启；显式重启才采用保存值，未保存内容不能用于重启。
- 服务繁忙或无法确认空闲时拒绝重启。
- 在“设置 → 常规 → 语言”选择 English 或简体中文；网页即时更新，MCP 重新连接后刷新工具说明。
- 修改端口后当前页面不能跨端口自动重连，按界面或 `apf status` 返回的新地址打开。

## 停止、诊断与数据保护

```powershell
.\.apf-env\Scripts\apf.exe stop --workspace D:\AstroPhotoFlow\workspace
```

- 停止会等待任务排空；超时或身份未知时保留记录、不表示已停止，先查询状态与日志。
- 日志位于 workspace 的 `logs` 目录；不要输出 service.token。
- 业务数据在指定 workspace，网页在 `web`，原生工作流在 `comfyui-user`，素材与预览在 `data`；程序 runtime 与之分离。
- 默认 workspace 由用户 TOML 的 `[workspace] default` 选择；平台不提供 workspace 搬迁服务。
- 已有数据库不自动升级，升级前按明确计划保护数据；不要只复制运行中的 SQLite 主文件。
- 关闭浏览器不停止已受理任务；断连先查询已有请求，不自动再提交一次。

## 延伸阅读

- [工作台规则](../product/workbench.md)
- [素材、设备与校准](../product/data.md)
- [工作流与处理](../product/workflow.md)
- [参考](../references.md)
- [开发](../development.md)
