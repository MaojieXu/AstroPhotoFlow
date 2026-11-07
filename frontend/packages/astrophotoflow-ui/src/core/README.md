# 前端公共基础

存放跨业务模块共用的 HTTP 与错误契约、查询客户端、宿主查询插件、国际化与工作台配置；单一业务模块使用的逻辑留在该模块。

## 入口

- `client.ts` 与 `contracts.ts`：`WorkbenchClient`（选择目录、读取/保存配置、重启与重启观察）及生成契约的公开名字；业务 DTO 不放这里。
- `query/client.ts`：`createPlatformQueryClient` 与 `PlatformQueryPlugin`；`query/identity.ts`：`useWorkspaceIdentity`，按连接身份验证服务与 workspace。
- `api/`：`createPlatformClient`、`FetchApi` 与 `ApiClientError`；`i18n.ts`：`uiMessages`、`configureUII18n` 与 `uiT`。

## 不变量

工作台配置保存不自动重启，未保存内容不用于重启；重启按 operation_id 轮询并校验回执身份；断连时只允许已有请求。共用逻辑不导入业务模块、原生 Store 或画布单例，也不创建第二个 Vue 应用或 Pinia 容器。

## 测试

包内 `tests/core/`（根 `pnpm test`）。集成关系见[前端子系统](../../../../../docs/subsystems/frontend.md)。
