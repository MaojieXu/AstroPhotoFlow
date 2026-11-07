# 业务 UI 包约束

- 原生应用只通过包导出（`src/index.ts`）使用本包；本包不得导入 `frontend/src`、`@/` 别名、原生 Store、画布单例或引擎脚本。
- 画布与宿主协调留在 `frontend/src/platform/astrophotoflow` 桥接；本包只提供组件、客户端与查询逻辑，不承担连线、执行或调度。
- 复用宿主 Vue、Pinia 与 vue-i18n，不创建第二个 Vue 应用或 Pinia 容器；消息经 `uiMessages` 合并，翻译函数经 `configureUII18n` 注入。
- 契约不手写：请求/响应模型从 `generated/api` 重导出；生成入口是根 `pnpm generate:sdk`，不手改生成物。
- 包内测试用 `@ui` 别名指向 `src`，生产消费 `@astrophotoflow/ui`；在仓库根运行 `pnpm test`、`pnpm typecheck`，依赖边界跑 `pnpm check:boundaries`。
