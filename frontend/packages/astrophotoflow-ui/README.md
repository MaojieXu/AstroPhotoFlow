# @astrophotoflow/ui

私有 workspace 业务 UI 包，由原生前端作为 workspace 依赖编译，不作为独立应用运行或发布；公开入口只有 `src/index.ts`。

## 结构

`src/core` 提供共用 HTTP 与错误契约、查询客户端、宿主查询插件、国际化与工作台配置；`src/modules/{data,software,nodes}` 提供业务界面、客户端与查询；`src/generated/api` 是 OpenAPI 生成的客户端与 Zod 模型，不手写。

## 宿主集成

宿主在原生 Vue 应用安装 `PlatformQueryPlugin`，每个应用一份查询缓存、卸载时清理，查询键必须包含 workspace 身份。默认不重试、5 秒新鲜期、5 分钟缓存、关闭聚焦刷新；轮询按模块区分，如活动导入 1.5 秒、目录类 10 秒、软件运行中 1 秒。

## 国际化

`uiMessages` 提供中英 `apfUi` 消息，宿主合并进 vue-i18n；组件内翻译经 `configureUII18n` 注入的函数，未注入时抛错。

## 测试与检查

`tests/` 下用 Vitest 与 jsdom（`@ui` 指向 `src`）；根命令 `pnpm test`、`pnpm typecheck`、`pnpm check:boundaries`。整合方式见[前端子系统](../../../docs/subsystems/frontend.md)。
