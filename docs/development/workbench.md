# 原生网页工作台使用

首轮运行验收面向 Windows x64/Python 3.12/CPU。最终用户安装发行 wheel 无需 Node 或 Git；首次初始化准备固定 CPU 依赖，工作流不要求生成式图像模型。

```powershell
py -3.12 -m venv .apf-env
.\.apf-env\Scripts\python.exe -m pip install .\.artifacts\dist\astrophotoflow-0.1.0-py3-none-any.whl
.\.apf-env\Scripts\apf.exe init --workspace D:\AstroPhotoFlow\workspace --service-port 18190 --comfyui-port 18188
.\.apf-env\Scripts\apf.exe start --workspace D:\AstroPhotoFlow\workspace
.\.apf-env\Scripts\apf.exe status --workspace D:\AstroPhotoFlow\workspace
```

打开 `http://127.0.0.1:18188/#/workflows`。节点库下方依次是素材库、工作流，两者与节点库共用原生侧栏，画布始终可见。设备管理在素材库“导入”旁，默认设备列表，保留组合、预设和项目管理。关闭浏览器保留后台任务，使用 `apf stop --workspace ...` 显式退出。

## 运行目录与数据

固定原生引擎位于 LocalAppData/AstroPhotoFlow/runtime/native-web-0.1.0，与旧 0.1.0 runtime 分离。业务数据仍在指定 workspace；网页资源在 workspace/web，ComfyUI 用户工作流在 workspace/comfyui-user，科学原件和预览仍在 data。

原生服务直接注册业务网关，默认禁用外部 Custom Nodes；不需要链接 custom_nodes，不再安装 AstroPhotoFlow 插件。领域服务仍为内部 FastAPI 进程，由工作台先启动并检查健康，再启动网页引擎。

## CLI、MCP 与维护

CLI 命令与58个 MCP 工具保持。使用 ASTROPHOTOFLOW_CONFIG 指定目标 workspace 的 config.toml；读取当前 revision 后再编辑。接口与例子见[操作参考](library-agent-tools.md)。

```powershell
.\.apf-env\Scripts\apf.exe stop --workspace D:\AstroPhotoFlow\workspace
.\.apf-env\Scripts\apf-service.exe db status
.\.apf-env\Scripts\apf-service.exe db upgrade
```

服务不会自动升级已有数据库；当前 schema 为 `0009_remove_legacy_capture_profiles`。workspace 搬迁前停止所有服务，复制整份 workspace 后以新路径启动，更新客户端配置路径。不要只复制 SQLite 主文件。

停止时工作台请求领域服务退出并等待导入／预览排空。超过等待时限会明确报错并保留进程记录，稍后再次运行 stop；不会将仍在排空的任务假报完成。

诊断查看 workspace/logs/service.log、comfyui.log、健康检查及 apf status。不要输出 service.token。软件适配、节点制作、工作流级MCP、结果比较与本地上下文尚待实施；产品使用外部Agent，不提供内置聊天或Agent推理／生成式模型后端。目标中的软件MCP和本地检索embedding按[③概要](../../src/astrophotoflow/modules/software/README.md)及⑤后续设计管理，目前没有相应安装或查询命令，不改变现有平台CPU runtime和58个数据工具。完整范围与阶段以[现行需求](../requirements/README.md)为准，桌面安装包不是网页交付前置条件。
