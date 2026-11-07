# 画布 Agent

[English](canvas-agent.en.md) | 中文

外部 Agent 通过平台接入层观察并修改当前原生画布；图文件、队列、历史与取消入口归 ComfyUI。接入职责与依赖边界见[架构](../architecture.md)。

## 职责

- 列出在线画布页面及其工作流、子图与 `content_token`。
- 在用户明确要求下把固定素材或集合加入准确页面，或执行一次添加节点、修改参数、连线和删除节点。
- 修改通过原生撤销、草稿与保存承接，不执行整图。

## 输入与输出

- 输入：页面、工作流与子图标识，当前 `content_token`，以及用户指定的修改内容。
- 输出：操作回执与当前页面状态；未知结果按原 `operation_id` 查询，不重发。
- 删除节点通过原生撤销移除节点与连线，保留源素材。

## 约束与失败方式

- 修改前核对准确目标；页面离线、切图或内容变化即停止。
- 无法确认画布结果时返回连接未知，并要求查询同一 `operation_id`，不自动重放。
- 修改不改变平台侧的素材、集合或项目引用；加入画布不复制科学原件。
- 迟到回执不写入其他图，也不在用户未指定的画布上继续操作。

## 数据引用

- 固定素材或集合以固定版本引用进入画布，显示状态不序列化为科学数据。
- 画布 widget 通过原生生命周期显示数据，宿主保留原有画布与主题。
- 数据引用与内容标记以当前页面回执为准。

## 对外契约

- HTTP 路由在 `src/astrophotoflow/interfaces/http/canvas.py` 与 `interfaces/http/data/canvas.py`。
- 契约在 `src/astrophotoflow/contracts/canvas.py`、`inputs.py` 与 `native.py`；页面消息纳入 [OpenAPI 快照](../api/openapi.json) 的 `x-apf-native-messages`。
- 原生回执与客户端在 `src/astrophotoflow/interfaces/native/`；查询入口见[参考](../references.md)。

## 测试与边界

- 测试在 `tests/interfaces/`。
- 工作流编辑、队列与执行历史归 ComfyUI；软件调用归 software；已检查结果归 data。
