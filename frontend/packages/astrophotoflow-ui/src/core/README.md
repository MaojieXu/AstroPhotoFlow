# ① 前端公共基础

本目录当前只有 README／AGENTS，没有公共配置、诊断或通知实现。完整职责、十二类能力、交接链路与阶段验收统一见[①公共基础设施概要设计](../../../../../src/astrophotoflow/core/README.md)，此处只维护前端归属。

Vue、Pinia、主题和网页生命周期由原生应用提供。后续公共运行配置、状态及诊断界面进入①；多个业务模块实际共用的消费、错误或连接能力出现后再提取，现有数据 UI 保持所属模块，不提前创建工具函数或状态容器。

第⑤阶段B13已有配置与业务客户端这两个真实消费者：将现data/api/client.ts的FetchApi、ApiClientError、createApiClient窄移到拟新增core/client.ts，errorSchema归拟新增core/contracts.ts；data原入口直接重导出同一实现，领域DTO仍留所属模块，core不导入业务。只补已要求的错误fields，不新增transport文件、网络框架或另一类错误。该移动尚未实施，取舍见[实施批次ADR](../../../../docs/adr/WORKBENCH-PLAN-0061-executable-batches-and-shared-client.md)。

- 网页区分有效配置与待应用配置，保存不自动重启；服务端提供可修改范围、授权、生效及失败事实。启动因端口占用自动选择新地址时，展示实际地址及原因；前端不自行推导权限或业务就绪。自动选端口及地址交接尚未实现，取舍见[启动地址 ADR](../../../../docs/adr/WORKBENCH-FOUNDATION-0054-automatic-startup-endpoints.md)。
- 执行进度复用原生显示和连接；领域变化优先验证跨进程桥接。具体取舍见[原生进度与状态复用 ADR](../../../../docs/adr/WORKBENCH-FOUNDATION-0046-native-progress-and-status-reuse.md)。
- 本包不导入原生 Store、画布单例或引擎脚本；宿主挂载、消息适配和画布协调位于[原生产品桥接](../../../../src/platform/astrophotoflow)，经明确公开能力与本包交接。
- 消息提示后查询所属模块实际内容；连接恢复不代表画布已显示，当前图保存、运行与在线实际应用分别返回结果，不建立永久回执。
- 平台日志轮转、缓存占用及清理范围由服务端提供；清理经用户确认并再次检查引用，业务运行证据受所属模块保护。

当前没有本目录独立测试；首次实现时补对应界面及公开交接的实际测试，再更新模块导航。既有原生进度测试不代表公共状态桥接已验收。
