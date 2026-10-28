# ① 前端公共基础

本目录已有M1工作台配置表单、具名客户端及共用HTTP／错误契约；公共诊断／通知仍待后续实现。完整职责、十二类能力、交接链路与阶段验收统一见[①公共基础设施概要设计](../../../../../src/astrophotoflow/core/README.md)，此处只维护前端归属。

Vue、Pinia、主题和网页生命周期由原生应用提供。后续公共运行配置、状态及诊断界面进入①；多个业务模块实际共用的消费、错误或连接能力出现后再提取，现有数据 UI 保持所属模块，不提前创建工具函数或状态容器。

第⑤阶段B13已有配置与业务客户端这两个真实消费者：将现data/api/client.ts的FetchApi、ApiClientError、createApiClient窄移到拟新增core/client.ts，errorSchema归拟新增core/contracts.ts；data原入口直接重导出同一实现，领域DTO仍留所属模块，core不导入业务。只补已要求的错误fields，不新增transport文件、网络框架或另一类错误。该移动已在B13候选实施，data和core共用同一错误类；表单经宿主传入真实翻译函数，保留原生主题与画布。取舍见[实施批次ADR](../../../../docs/adr/WORKBENCH-PLAN-0061-executable-batches-and-shared-client.md)。

- 网页区分有效配置与待应用配置，保存不自动重启；服务端提供可修改范围、授权、生效及失败事实。启动因端口占用自动选择新地址时，展示实际地址及原因；前端不自行推导权限或业务就绪。自动端口及地址交接已在M1隔离实例验证，用户人工批准仍待完成；取舍见[启动地址 ADR](../../../../docs/adr/WORKBENCH-FOUNDATION-0054-automatic-startup-endpoints.md)。
- 执行进度复用原生显示和连接；领域变化优先验证跨进程桥接。具体取舍见[原生进度与状态复用 ADR](../../../../docs/adr/WORKBENCH-FOUNDATION-0046-native-progress-and-status-reuse.md)。
- 本包不导入原生 Store、画布单例或引擎脚本；宿主挂载、消息适配和画布协调位于[原生产品桥接](../../../../src/platform/astrophotoflow)，经明确公开能力与本包交接。
- 消息提示后查询所属模块实际内容；连接恢复不代表画布已显示，当前图保存、运行与在线实际应用分别返回结果，不建立永久回执。
- 平台日志轮转、缓存占用及清理范围由服务端提供；清理经用户确认并再次检查引用，业务运行证据受所属模块保护。

配置行为测试位于`tests/core/workbench.test.ts`，共用HTTP回归继续复用data/api测试，真实浏览器场景位于仓库`tests/browser/platform-workflows.mjs`。独立状态桥接、通知和诊断未因此完成；M1技术证据及人工批准见[矩阵](../../../../../docs/development/test-matrix.md#m1-foundation)。

2026-10-28 demo设置入口调整：工作台配置迁入原生设置窗口，宿主传入原生FormItem／Button／Input组件，UI包不导入原生源码。正常状态简化为“配置已生效”，工作区／端口／目录与运行信息按普通section直接显示，输入与当前生效值不同时显示差异；全部字段和整组保存语义保留。M1验收反馈的网页重启按钮、当前网页地址链接及未保存提示继续保留；长期逻辑仍留core。前端先生成请求编号，只提交一次，断连期间仅查询既有回执。跨网页端口自动重连暂不支持，界面明确显示新配置入口与CLI核对方式。

2026-10-28 demo悬停提示调整：工作台说明、配置文件路径、默认工作区说明与完整输入、数据目录说明及已保存绝对路径、重启说明和导入目录完整路径统一使用原生Button tooltip；字段侧通过FormItem的name-suffix挂载。长路径限宽换行，已保存路径与当前输入分别标明。运行地址、区块和操作状态直接显示。保存成功提示仅在实际编辑时清除，查看提示不触发保存／重启。
