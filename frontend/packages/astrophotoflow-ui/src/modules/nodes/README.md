# 节点界面

提供节点目录与定义的读取客户端与类型；节点制作、参数编辑与画布操作不在本模块，原生注册、控件、连线与子图协调属宿主桥接。

## 结构

`client.ts` 的 `createNodeClient` 经 core 的 `createPlatformClient` 与生成 SDK 读取 `list` 与 `get`；`NodeCapability`、`SavedNode`、`NodeParameter` 直接从生成契约重导出，不手写模型。

## 边界

定义权威在 Python `nodes` 模块；本模块不写工作流 JSON、不执行节点、不操作画布，也不缓存定义副本。

## 测试

包内 `tests/modules/nodes/`（根 `pnpm test`）。
