# 前端

[English](frontend.en.md) | 中文

原生 ComfyUI 网页承载界面，平台界面分为私有 UI 包与原生桥接两层。模块划分见[架构](../architecture.md)，界面操作见[使用说明](../user/workbench.md)。

## 私有 UI 包

- `frontend/packages/astrophotoflow-ui` 通过 `src/index.ts` 导出素材 Workspace、工作台配置、软件面板与节点/预览客户端；由原生网页编译，不独立运行或发布。
- `src/core` 提供共用 HTTP 与错误处理、查询缓存与工作台配置，业务在 `src/modules/data`、`nodes` 与 `software`。
- 本包不导入原生 Store、画布单例或 `frontend/src`；原生组件由宿主注入，完整导出清单以代码为准。

## 原生桥接

- `frontend/src/platform/astrophotoflow` 安装查询插件、注入翻译函数，并把业务控件接入侧栏与画布；保留常驻画布、侧栏顺序与未保存编辑保护。
- 固定数据引用使用一次原生撤销事务；运行回执按实际 Data 与来源连线核对；导出只写副本。
- 原生 Store、画布与转换协调在本目录，UI 包不反向依赖。

## 查询与轮询

- 共用应用级 Vue Query 客户端，查询键含 workspace 身份；默认不重试，允许断开互联网，关闭聚焦刷新。
- 可见任务每 10 秒发现跨入口任务；活动任务每 1.5 秒读取，结束后恢复目录频率并按 workspace 失效任务查询。
- 导入任务的服务数据归查询缓存，测试挂载使用同一插件。

## 失败方式

- 手动内容变化使旧请求失效；切图暂停后续写与提交，迟到结果不抢视图。
- 查看与缩放不改变内容标记；显示状态不序列化。
- UI 不直接操作数据库、不复制领域规则，未知结果交所属模块查询。

## 对外契约

- 公开入口是包导出与原生桥接；后端契约以实际路由与 Pydantic 模型为准，字段见 [OpenAPI 快照](../api/openapi.json)。
- 生成的前端 SDK 位于 `frontend/packages/astrophotoflow-ui/src/generated/api`，不手改。
- 测试使用 `pnpm test` 与 `pnpm typecheck`。

## 边界

- 工作流编辑、队列、执行历史与画布能力归 ComfyUI；领域规则归所属模块。
