# 后端导航

路径以本文件为基准。按问题选择入口，再沿当前 imports 与调用者确认实现。模块职责和状态权威见[架构](../../../../docs/architecture.md)，局部要求从[Python 包约定](../../../../src/astrophotoflow/AGENTS.md)进入。

## 文件分类与归属

| 要改的内容 | 源码入口与下一跳 |
| --- | --- |
| 跨边界模型、枚举与校验 | [contracts](../../../../src/astrophotoflow/contracts)按语义域选文件，先读其中的 AGENTS.md，再核对服务端与客户端消费方 |
| 配置、认证、数据库连接与生命周期 | [core README](../../../../src/astrophotoflow/core/README.md)定位 config、database、workbench；启停只经 [workbench 公开入口](../../../../src/astrophotoflow/core/workbench/__init__.py) |
| 素材、数据集成员、设备、校准、导入、预览、结果与回收站 | [data README](../../../../src/astrophotoflow/modules/data/README.md)和 [public.py](../../../../src/astrophotoflow/modules/data/public.py)定位能力，再沿导出进入所属目录；ORM 与 schema 装配从 persistence 进入 |
| 软件包、安装就绪、具体调用、取消与 Bundle 加载 | [software README](../../../../src/astrophotoflow/modules/software/README.md)和 [public.py](../../../../src/astrophotoflow/modules/software/public.py)定位 packages、execution、bundles 与 development |
| 节点定义、更新差异与派生目录 | [nodes README](../../../../src/astrophotoflow/modules/nodes/README.md)和 [public.py](../../../../src/astrophotoflow/modules/nodes/public.py)定位 definitions、changes、storage 与 catalog |
| HTTP、CLI、MCP、客户端与原生协议装配 | [interfaces README](../../../../src/astrophotoflow/interfaces/README.md)定位具体通道；跨模块用例从 [application](../../../../src/astrophotoflow/interfaces/application)进入 |
| 固定引擎网关、打包资源与接口生成物 | [comfyui/proxy.py](../../../../src/astrophotoflow/comfyui/proxy.py)、[接口参考](../../../../docs/references.md)与[构建命令](../../../../package.json)；修改生成来源后重新生成对应快照 |

业务内部先找当前责任函数或类型，跨模块调用从 `public.py` 进入。业务规则变更同时阅读所属[子系统](../../../../docs/subsystems/README.md)，按其契约选择测试。

## 协议与调用链

| 任务 | 当前入口与代表调用关系 |
| --- | --- |
| FastAPI 装配、依赖与 HTTP 适配 | [http/app.py](../../../../src/astrophotoflow/interfaces/http/app.py)装配路由，依赖从 [dependencies.py](../../../../src/astrophotoflow/interfaces/http/dependencies.py)进入；例如 [http/data/datasets.py](../../../../src/astrophotoflow/interfaces/http/data/datasets.py)的 create_dataset 经 data.public 调用所属业务 |
| Python 客户端与传输 | 包根 [client.py](../../../../src/astrophotoflow/client.py)组合 AssetClient；[client/transport.py](../../../../src/astrophotoflow/interfaces/client/transport.py)负责配置、实际运行地址、认证与请求；例如 [image_management.py](../../../../src/astrophotoflow/interfaces/client/image_management.py)的 image_datasets_create 请求 HTTP 数据集入口 |
| MCP 工具定义、组合与会话 | [mcp/server.py](../../../../src/astrophotoflow/interfaces/mcp/server.py)组合 data、graph、software 工具；[lifespan.py](../../../../src/astrophotoflow/interfaces/mcp/lifespan.py)提供会话共享客户端；例如 [mcp/data/datasets.py](../../../../src/astrophotoflow/interfaces/mcp/data/datasets.py)的 create 通过 AssetClient 调用上述 HTTP 能力 |
| 生成业务 CLI 与本机控制命令 | 包根 [cli.py](../../../../src/astrophotoflow/cli.py)进入 [cli/main.py](../../../../src/astrophotoflow/interfaces/cli/main.py)，组合 generated 业务命令与 local 本机命令；业务 CLI 从 MCP 目录生成，通过 stdio MCP 调用共享客户端；local 经 core 控制入口管理工作台 |
| 领域服务进程命令 | [http/cli.py](../../../../src/astrophotoflow/interfaces/http/cli.py)提供 apf-service，服务创建与数据库操作沿实际调用进入 core |
| 原生节点与软件调用装配 | [native/bootstrap.py](../../../../src/astrophotoflow/interfaces/native/bootstrap.py)和 [native/bundles](../../../../src/astrophotoflow/interfaces/native/bundles)加载宿主节点；node.py 请求领域服务，[http/software_calls.py](../../../../src/astrophotoflow/interfaces/http/software_calls.py)委托 [application/software_calls.py](../../../../src/astrophotoflow/interfaces/application/software_calls.py)组合 software 调用与 data 结果能力 |
| 页面消息与当前画布操作 | [native/canvas.py](../../../../src/astrophotoflow/interfaces/native/canvas.py)、[http/canvas.py](../../../../src/astrophotoflow/interfaces/http/canvas.py)与 [application/canvas.py](../../../../src/astrophotoflow/interfaces/application/canvas.py)；页面端沿前端技能进入 session 与桥接实现，协议定义从 [http/schema.py](../../../../src/astrophotoflow/interfaces/http/schema.py)核对 |

追踪返回路径时同时检查协议错误适配与客户端错误类型。业务 CLI 输入来自 MCP 工具 schema，修改生成命令时回到工具定义及生成器。生成入口见[契约同步](integration.md#契约与生成物)。

## 数据库开发

v1／v2 阶段与测试 workspace 替换规则由[开发文档](../../../../docs/development.md#目录)维护。ORM 变化先定位 [data/persistence.py](../../../../src/astrophotoflow/modules/data/persistence.py)，再检查 [database/schema.py](../../../../src/astrophotoflow/core/database/schema.py)和 [generate_database_baseline.py](../../../../scripts/generate_database_baseline.py)。生成器从空内存数据库生成当前初始化基线，审查生成约束后运行[基线一致性测试](../../../../tests/core/test_image_management_migration.py)。

同一 revision 下修改基线后，已有数据库仍需按开发文档按需重建。以新建数据库与 ORM 的一致性验证 schema 变化。
