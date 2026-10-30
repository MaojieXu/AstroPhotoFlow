# 去哪里改代码

先按本表定位，再读该目录AGENTS.md、代码、实际类型和相关测试。职责以 [架构](overview.md) 为准，实现状态以 [当前上下文](../development/current-context.md) 为准；不在这里维护逐函数清单。

| 任务 | 实现入口 | 验证位置 |
|---|---|---|
| 配置、启停、维护 | [core](../../src/astrophotoflow/core/README.md) | `tests/core`、`tests/packaging` |
| 导入、素材、设备、预览、科学交接 | [data/public.py](../../src/astrophotoflow/modules/data/public.py)、[routes.py](../../src/astrophotoflow/modules/data/routes.py) | `tests/modules/data` |
| 软件包、Bundle安装和调用 | [software/public.py](../../src/astrophotoflow/modules/software/public.py)、[bundles.py](../../src/astrophotoflow/modules/software/bundles.py) | `tests/modules/software` |
| 节点定义及目录 | [nodes/public.py](../../src/astrophotoflow/modules/nodes/public.py)、[catalog.py](../../src/astrophotoflow/modules/nodes/catalog.py) | `tests/modules/nodes`、`tests/modules/software/test_node_catalog.py` |
| 在线画布、软件调用协调、实时预览 | [workflows](../../src/astrophotoflow/modules/workflows/README.md) | `tests/modules/workflows` |
| 公共类型及校验 | [contracts](../../src/astrophotoflow/contracts) | 随消费者验证 |
| HTTP装配、CLI／客户端、MCP、原生节点注册 | [interfaces](../../src/astrophotoflow/interfaces)、[client.py](../../src/astrophotoflow/client.py)、[cli.py](../../src/astrophotoflow/cli.py) | `tests/interfaces`、`tests/integration` |
| 自研业务界面 | [UI包](../../frontend/packages/astrophotoflow-ui) | 包内`tests` |
| 原生Store／画布／事件桥接 | [宿主桥接](../../frontend/src/platform/astrophotoflow) | 同目录组件／桥接测试 |
| 固定引擎与同源代理 | [engine/ComfyUI](../../engine/ComfyUI)、[comfyui/proxy.py](../../src/astrophotoflow/comfyui/proxy.py) | `tests/interfaces/comfyui`、原生前端相关测试 |
| Siril程序与适配器 | 独立仓库`MaojieXu/AstroPhotoFlow-Siril`；主平台只维护SDK、加载和发布快照 | 独立Bundle测试与真实集成证据 |

HTTP字段从 [OpenAPI](../api/openapi.json) 查；Python内部交接从`public.py`及`contracts`查；原生页面消息从实际桥接类型查。旧文件规划不是创建文件的指令。

常用开发和验证命令见 [开发流程](../development/README.md)。
