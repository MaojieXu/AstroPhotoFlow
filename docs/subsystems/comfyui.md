# ComfyUI 集成

[English](comfyui.en.md) | 中文

ComfyUI 是固定上游引擎，平台保留其源码修改、受管启动与同源网关。运行拓扑与模块职责见[架构](../architecture.md)。

## 固定引擎

- `engine/ComfyUI` 是固定上游版本加平台修改的源码；正常启动执行 runtime 目录中的解压副本，不直接执行该目录。
- 版本、提交、归档与前端依赖记录在 `src/astrophotoflow/vendor/comfyui-source.json`。
- runtime 准备把归档解压到运行时目录，并使用独立 Python 环境。

## 受管启动

- 引擎使用独立环境启动，`PYTHONPATH` 指向平台包，以加载平台原生接入代码。
- workspace 的网页目录由初始化从包内复制，引擎以 `--front-end-root` 读取该目录。
- 启动与停止由工作台控制，不经业务 HTTP 接口。

## 同源网关

- `src/astrophotoflow/comfyui/proxy.py` 以 `/astrophotoflow/api/v1` 前缀转发公开路由。
- 白名单来自 `src/astrophotoflow/vendor/http-routes.json`，只注册明确清单，不做通配转发，也不暴露内部路径。
- 领域服务提供 `/openapi.json`，关闭 `/docs` 与 `/redoc`；网页、CLI 与 MCP 共用同一批业务能力。

## 失败方式

- 本机服务配置或令牌不可用时网关返回 503，并给出可读错误。
- 不在白名单的路径不转发；引擎停止只影响原生网页，不表示领域服务停止。
- 网页连接断开后先查询已有请求，不自动重复提交。

## 对外契约

- 网关代码在 `src/astrophotoflow/comfyui/proxy.py`；原生页面与消息在 `src/astrophotoflow/interfaces/native/`。
- 路由白名单与 OpenAPI 快照由生成脚本维护，位置见[参考](../references.md)。

## 边界

- 工作流、队列、历史、进度与取消归 ComfyUI 原生；软件调用归 software，已检查结果归 data。
