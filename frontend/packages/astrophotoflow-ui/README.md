# @astrophotoflow/ui

AstroPhotoFlow 私有 workspace 组件包，通过源码导出由原生网页应用编译，不独立运行或对外发布。

公开入口为 src/index.ts，目前导出 Workspace；其既有 props、事件和已暴露方法保持。实现位于 src/modules/data，其他模块与 core 目前仅有文档。

本包使用原生 workspace 锁定的 Vue、Pinia 和 Zod；测试独立使用 jsdom，不加载原生画布的全局 setup。tests/modules/data 保存 19 份既有组件测试，tests/fixtures 保存真实 API 样例。

命令：仓库根 `pnpm test`、`pnpm typecheck`；单项测试可使用 `pnpm --dir frontend --filter @astrophotoflow/ui test tests/modules/data/...`。

本轮仅迁移已有逻辑，保留原有组件、样式和业务断言；未进行大组件拆分或整体国际化改写。
