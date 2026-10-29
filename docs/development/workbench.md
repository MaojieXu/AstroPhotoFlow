# 原生网页工作台使用

网页导入直接选择本机文件／文件夹，无需配置授权根目录。工作台设置已隐藏“授权导入目录”区域；既有import_roots配置及旧接口保留，修改其他设置不会清空这些值。此项仅改前端呈现，实际编译／隔离更新及未执行验证见当前上下文。

首轮运行验收面向 Windows x64/Python 3.12/CPU。最终用户安装发行 wheel 无需 Node 或 Git；首次初始化准备固定 CPU 依赖，工作流不要求生成式图像模型。

```powershell
py -3.12 -m venv .apf-env
.\.apf-env\Scripts\python.exe -m pip install .\.artifacts\dist\astrophotoflow-0.1.0-py3-none-any.whl
.\.apf-env\Scripts\apf.exe init --workspace D:\AstroPhotoFlow\workspace --service-port 18190 --comfyui-port 18188
.\.apf-env\Scripts\apf.exe start --workspace D:\AstroPhotoFlow\workspace
.\.apf-env\Scripts\apf.exe status --workspace D:\AstroPhotoFlow\workspace
```

打开start返回的实际网页地址；示例端口空闲时为 `http://127.0.0.1:18188/#/workflows`。节点库下方依次是素材库、工作流，两者与节点库共用原生侧栏，画布始终可见。设备管理在素材库“导入”旁，默认设备组合，可切换我的设备；拍摄预设在所属组合内维护。该模块不提供项目页面或设备回收站，项目数据及公开接口保留。关闭浏览器保留后台任务，使用 `apf stop --workspace ...` 显式退出。

## 运行目录与数据

固定原生引擎位于 LocalAppData/AstroPhotoFlow/runtime/native-web-0.1.0，与旧 0.1.0 runtime 分离。业务数据仍在指定 workspace；网页资源在 workspace/web，ComfyUI 用户工作流在 workspace/comfyui-user，科学原件和预览仍在 data。

原生服务直接注册业务网关，默认禁用外部 Custom Nodes；不需要链接 custom_nodes，不再安装 AstroPhotoFlow 插件。领域服务仍为内部 FastAPI 进程，由工作台先启动并检查健康，再启动网页引擎。

## CLI、MCP 与维护

CLI 命令与58个 MCP 工具保持。使用 ASTROPHOTOFLOW_CONFIG 指定目标 workspace 的 config.toml；读取当前 revision 后再编辑。接口与例子见[操作参考](library-agent-tools.md)。

B11起，默认位置由用户`~/.config/astrophotoflow/config.toml`的`[workspace] default`指定workspace目录，`apf init`激活时写入；显式workspace和`ASTROPHOTOFLOW_CONFIG`优先。旧active-workspace不再读取，没有默认设置时请明确指定目标。本轮未迁移或修改本机原默认指针，可继续使用显式路径。M1候选提供自动端口、真实启动采用记录及左侧“工作台配置”侧栏。start／status／stop／restart返回结构化结果；定向控制不修改默认位置。保存不重启，可在侧栏保存后点击“重启工作台”，或使用`apf restart --workspace <目标>`显式应用；繁忙或无法确认时拒绝。原dev旧版本保留，本轮人工验收请用M1隔离地址，不能把文档成文当作用户验收通过。

```powershell
.\.apf-env\Scripts\apf.exe stop --workspace D:\AstroPhotoFlow\workspace
.\.apf-env\Scripts\apf-service.exe db status
.\.apf-env\Scripts\apf-service.exe db upgrade
```

服务不会自动升级已有数据库；当前 schema 为 `0009_remove_legacy_capture_profiles`。workspace 搬迁前停止所有服务，复制整份 workspace 后以新路径启动，更新客户端配置路径。不要只复制 SQLite 主文件。

停止时工作台请求领域服务退出并等待导入／预览排空。超过等待时限会明确报错并保留进程记录，稍后再次运行 stop；不会将仍在排空的任务假报完成。

启动失败也沿用同一排空流程。尚未完成登记的进程保留在当前控制记录中，身份暂不可读时后续stop重新核对；若启动中断在PID记录之前，状态保持未知并要求人工核对，不报告已停止。启动、清理和控制结果保存错误会一起说明；不要在状态未知时直接重复启动。

诊断查看 workspace/logs/service.log、comfyui.log、健康检查及 apf status。不要输出 service.token。软件适配、节点制作、工作流级MCP、结果比较与本地上下文尚待实施；产品使用外部Agent，不提供内置聊天或Agent推理／生成式模型后端。目标中的软件MCP和本地检索embedding按[③概要](../../src/astrophotoflow/modules/software/README.md)及⑤后续设计管理，目前没有相应安装或查询命令，不改变现有平台CPU runtime和58个数据工具。完整范围与阶段以[现行需求](../requirements/README.md)为准，桌面安装包不是网页交付前置条件。

网页重启先保存配置，未保存时按钮禁用并提示。重启采用已保存值；当前生效值在服务重启前保持。断连只查询既有请求，不自动重发。网页地址可点击新页打开。修改网页端口后当前页面不支持跨端口自动重连，使用界面展示的配置入口重新打开；若实际端口因占用改变，执行`apf status --workspace <目标>`获取真实地址，未知不能视为成功。
