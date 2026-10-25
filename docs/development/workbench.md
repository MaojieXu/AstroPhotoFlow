# CPU 工作台使用

面向 Windows x64、Python 3.12。安装已有发行 wheel 无需 Node 或 Git；首次 `apf init` 下载固定 CPU 依赖，准备 ComfyUI 0.42.0、前端 1.57.1 和独立运行环境，不下载生成式图像模型。固定来源见包内 vendor 清单。

```powershell
py -3.12 -m venv .apf-env
.\.apf-env\Scripts\python.exe -m pip install .\dist\astrophotoflow-0.1.0-py3-none-any.whl
.\.apf-env\Scripts\apf.exe init --workspace D:\AstroPhotoFlow\workspace --service-port 18190 --comfyui-port 18188
.\.apf-env\Scripts\apf.exe start --workspace D:\AstroPhotoFlow\workspace
.\.apf-env\Scripts\apf.exe status --workspace D:\AstroPhotoFlow\workspace
```

打开 `http://127.0.0.1:18188/` 的“天文”侧栏。运行环境位于 LocalAppData 下的 AstroPhotoFlow/runtime，业务数据位于指定 workspace。已安装的工作台启动资产服务后，ComfyUI 插件只连接该服务，不重复启动。

## CLI 与 MCP

```powershell
$env:ASTROPHOTOFLOW_CONFIG = 'D:\AstroPhotoFlow\workspace\config.toml'
.\.apf-env\Scripts\apf.exe import-photo D:\AstroData\photo.fit
.\.apf-env\Scripts\apf.exe task <task-id>
.\.apf-env\Scripts\apf.exe assets list
.\.apf-env\Scripts\apf.exe assets get <asset-id>
.\.apf-env\Scripts\apf.exe assets parameters <asset-id> --base-revision 1 --exposure-seconds 0
.\.apf-env\Scripts\apf.exe assets parameters <asset-id> --base-revision 2 --clear exposure_seconds
.\.apf-env\Scripts\apf.exe mcp-config --workspace D:\AstroPhotoFlow\workspace
```

使用响应中的当前 revision 继续更新，不能假定始终为示例数值。MCP 注册信息包含绝对命令路径和 workspace 配置；`apf mcp` 启动 stdio 服务。已有注册不需要重复添加；代码更新后重连该MCP服务器刷新工具清单，资料修改后刷新前端查看。完整58工具和领域命令见[操作参考](library-agent-tools.md)。

## 数据与维护

先 `apf stop --workspace ...`，再复制整份 workspace；重新启动时指定新目录。不要只复制 SQLite 主文件，原图、预览、令牌、WAL 和 ComfyUI 用户文件都属于该 workspace。MCP 连接需改用新配置路径。

```powershell
.\.apf-env\Scripts\apf.exe stop --workspace D:\AstroPhotoFlow\workspace
.\.apf-env\Scripts\apf-service.exe db status
.\.apf-env\Scripts\apf-service.exe db upgrade
```

服务启动不会自动升级已有数据库；显式 upgrade 沿用现有备份机制，当前 revision 是 `0007_setups_and_calibration`。诊断先看 workspace/logs/service.log、comfyui.log 和健康检查；不要输出 service.token 内容。

开发用历史数据库可按用户授权删除重建；原始照片和 ZIP 不属于可清理测试缓存。CI配置包含Linux的Python／构建检查，本轮未远端执行，不能声称Windows CPU安装流程已在Linux完成产品验收。
