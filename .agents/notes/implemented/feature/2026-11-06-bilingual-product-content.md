# Agent Note: 产品文案的中英双语覆盖

Status: Implemented

## Problem

文档已经全部中英配对，但产品内容只配置了一部分：43 处 `ApiError` 直接传英文文案、不带 `message_key`，服务端只能原样返回，无法按 workspace 语言渲染；原生网页 `zh/main.json` 相对 `en/main.json` 缺 264 个键、多 17 个过期键。业务 UI 包（`apfUi`）与后端 `errors.json` 目录本身已完整，但仓库自带的 `tests/core/test_error_localization_coverage.py` 因此是红的；前端既没有键集守卫，CI 也不运行 `pnpm locale:check`——按上游策略它只报告待翻译，不失败。

## Decision

补齐两处内容并加一道可执行的守卫：为 43 处错误构造补上 `message_key`，新增 42 个 `errors.json` 目录键（en 文案沿用原字面量，补 zh 翻译，两处站点共用一个键）；用一次性脚本按现有 zh 兄弟顺序插入 264 条中文、删除 17 条过期键，不改写整个 zh 文件。新增 `tests/core/test_frontend_locale_coverage.py`，用 pytest 守护 `frontend/src/locales/{en,zh}` 的四个目录与 `@astrophotoflow/ui` 两个语言文件的键集一致；守卫放 Python 层，是因为 `product` job 只运行 Python 测试与根 `pnpm test`（仅 UI 包），不执行前端 vitest 与 `pnpm locale:check`。

## Alternatives considered

- 依赖发布期的 `pnpm locale` 自动翻译：需要 `OPENAI_API_KEY`，且 `--check` 允许待翻译项，无法保证每次改动后立即可用。
- 把守卫写进前端 vitest：CI 不执行该层，等于没有守卫。
- 只翻译代码里实际引用的键：键集一致才是可维护的不变量，未被引用的键也随上游同步保留。
- 整文件重写 zh 目录：zh 的父子键顺序与 en 有上千处不同，会产生无意义的大 diff，所以按位置插入。
- 把自动翻译流程放进 CI 必过项：它依赖外部服务与密钥，不适合作为合并门禁。

## Consequences

- 以后新增或修改界面文案必须在同一次改动里提交英文与中文，否则 `product` job 失败；发布期的自动翻译仍可用于批量补译。
- 手改 zh 目录不会改动 `.source-manifest.json`，该清单只记录 en 源文件的 blob 哈希。
- 守卫只比较键集，不比较值：专有名词、URL、`dataTypes` 等技术标识与 `errorCatalog` 的 `{nodeName} - {inputName}` 占位符在中英文里本来就相同。
- 界面诊断文本（如 `WorkbenchError` 原文）仍按诊断透传，不进入消息目录。
