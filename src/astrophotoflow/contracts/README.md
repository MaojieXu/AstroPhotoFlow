# 跨边界契约

`astrophotoflow.contracts` 定义服务端、Python 客户端、CLI、MCP 与前端生成 SDK 共用的请求/响应模型，是这些边界上的唯一契约来源；不含编排、IO 或业务规则。

## 组织

模型按语义域分文件（如 `assets.py`、`datasets.py`、`imports.py`、`nodes.py`、`software.py`、`workbench.py`），共享基础类型在 `common.py`；新模型放入所属语义文件，不按消费方拆分。

## 依赖与消费

只依赖标准库与 Pydantic。HTTP 路由、`AssetClient`、`apf` 命令、MCP 工具与前端 `generated/api` 消费同一模型；改动同步影响这些边界，前端 SDK 与 `docs/api/openapi.json` 由根 `pnpm generate:sdk` 重新生成，不手改生成物。

## 生成物

`docs/api/openapi.json` 是 HTTP 契约快照，`docs/api/mcp-tools.json` 是 MCP 工具快照，`src/astrophotoflow/vendor/http-routes.json` 是路由清单；查询接口与字段以生成物和代码为准，见[参考](../../../docs/references.md)。

## 测试

跨边界行为在 `tests/integration/` 验证；导入边界由 `tests/architecture/test_import_boundaries.py` 检查。
