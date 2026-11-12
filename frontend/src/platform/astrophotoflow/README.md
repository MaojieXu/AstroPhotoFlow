# 原生平台集成

本目录把 `@astrophotoflow/ui` 接入 ComfyUI 原生前端：复用原生 Store、画布、侧栏与生命周期，业务 UI 只经包公开入口消费，UI 包不得反向依赖这里。

## 入口

`index.ts` 导出 `NativeShell` 与 `useLibrarySidebarTab`、`useProjectSidebarTab`、`useSoftwareSidebarTab`；`useNativeWorkspace` 提供共享传输身份与 workspace 解析。

## 集成点

- `canvas/`：`LibraryCanvasSource` 复用原生点击放置、拖拽与预览；`dataBridge` 与 `canvasDataBridge` 写入固定引用并使用一次原生撤销事务；`CanvasDataWidget` 经原生 widget 生命周期显示素材、成员与资料。
- `canvas/session.ts`：`useCanvasDataSession` 序列化当前图并生成 content_token，处理页面状态与 `apf.canvas_command`，校验 workflow、graph 与内容标记后应用编辑，回执区分已应用、目标变化与结果未知。
- `results/`：`DataRunWidget` 读取原生输出 Store 的实际 Data 回执；`DataExportDialog` 经公开客户端把完整成员保存到素材库或本机；`useAutomaticResults` 按 500ms 合并语义变化、复用原生队列并记录计算签名，`BundleResultWidget` 展示对应签名的结果。
- `media/`：`MediaViewer` 与 `mediaViewport` 处理概览、瓦片、视频与暂停源帧，经公开 Media 客户端消费，查看状态不写图。
- `sidebar/`：侧栏顺序为节点库、素材库、项目、工作流、软件包；`settings/` 在原生设置内提供工作台配置与真实版本信息。

## 不变量

保留常驻画布、侧栏关闭保护与设备入口；手动内容变化使旧请求失效，查看与缩放不改变内容标记，切图暂停后续写与提交，迟到结果不抢当前视图；图与工作流事实仍归 ComfyUI，本目录不复制服务端当前图。

## 测试

`tests/` 下的 Vitest 用例；根命令 `pnpm test`、`pnpm typecheck`。整体归属见[前端子系统](../../../../docs/subsystems/frontend.md)。
