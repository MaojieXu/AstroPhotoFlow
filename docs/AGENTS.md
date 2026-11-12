# 文档规则

本文件是 `docs/`、`.agents/` 与各层 `AGENTS.md` 的唯一规则页。改文档前读本页；改代码时只需读改动范围附近适用的 `AGENTS.md`。

## 单一出处

每类事实只写在一处，其他文档链接它。下表是默认归属，出现新事实时先放回对应层，再决定是否加链接。

| 文档 | 负责的事实 |
| --- | --- |
| `docs/product/*` | 用户要什么、必须保持的产品规则、已确认的范围边界 |
| `docs/architecture.md` | 模块职责、数据与状态归属、依赖边界、跨模块装配、运行拓扑 |
| `docs/subsystems/*` | 单个子系统的行为、输入输出、失败方式与对外契约 |
| `docs/development.md` | 本机环境、bootstrap、常用命令、调试入口 |
| `docs/testing.md` | 测试分层、门禁、回执写法、浏览器测试与验证边界 |
| `docs/release.md` | 版本号、构建产物、tag、dev→main 发布流程 |
| `docs/references.md` | 生成物位置与查询方式（OpenAPI、MCP、CLI） |
| `docs/user/workbench.md` | 面向使用者的操作说明 |
| `docs/i18n/README.md` | 三件套结构、记录文件与翻译门禁 |
| `.agents/notes/**` | 已发生决定的取舍与后果 |
| `.agents/skills/**` | 按需加载的操作步骤 |
| `AGENTS.md` 各层 | 该目录的局部约束与入口提示 |
| 代码与生成物 | 接口字段、签名、schema 的最终事实 |

不手抄接口表、字段清单、目录列表；指向生成物或代码。生成物由脚本维护，不手改。

## 写作规则

- 只写当前状态。历史、放弃的方案和讨论过程写进 Agent Notes 或提交信息，不留在正文。
- 一段一行，不硬换行；段落之间空一行。
- 链接用相对路径，锚点保持稳定；同一事实已在别处时用链接而不是复述。
- 删除过期内容时直接删除，不留“已废弃”“以后再说”一类占位。
- 中文主文档按 `docs/i18n/README.md` 维护英文配对，两边一起改。
- 直述事实，不写推理过程、不堆强调、不用隐喻；术语全仓库一致。

## 预算

每页有非空白字符上限，清单是 `scripts/doc-budgets.json`。`pnpm check:docs` 或 `python scripts/verify_docs.py all` 校验。超限先删重复与低价值内容，再考虑更换归属；确需提高上限时在 PR 说明理由，且之后只降不升。新增页面先确定预算再写正文。

## AGENTS.md 分层

- 层级是根 → 子目录；子层只写本目录特有、阅读上级无法推出的规则，不复制上级规则。
- 只有子树存在独立且不显然的约束时才新增 `AGENTS.md`；否则并入上级或写成模块 README。
- 默认上限 4000，`frontend/AGENTS.md` 与 `engine/**` 是外部代码，不纳入检查。
- `AGENTS.md` 不放状态、计划与历史；入口和事实交给 `docs/`。

## Agent Notes

- 路径即状态：`.agents/notes/implemented/<class>/YYYY-MM-DD-slug.md`，class 取 `feature`、`bug-fix`、`simplification`、`architecture`、`process`、`testing`。
- 写完一个非显然的决定、修复或简化后补一条；只写已经发生的事，不写计划。
- 固定头 `# Agent Note: <title>`、空行、`Status: Implemented`，正文按 Problem → Decision → Alternatives considered → Consequences 排列。
- 禁止 `INDEX.md`，禁止在笔记里写 Proposal、Plan、验收标准；笔记一旦写就视为不可变，后续改变另写一条并链接前一条。

## Skills

- 位置 `.agents/skills/<kebab-name>/SKILL.md`；frontmatter 必含 `name` 与 `description`，name 与目录同名。
- 正文写触发条件、步骤、入口命令，细节链接 `docs/`；单个技能正文不超过 8000 非空白字符。
- 技能是按需加载的过程说明，不重复文档事实，不内嵌大段接口表。

## 门禁

- 日常入口 `pnpm check:docs`；CI 执行同一命令，规则：预算、配对、换行、链接、notes、skills。
- 失败必须修内容，不能用 `--report` 绕过 CI；`--report` 只用于本地预览。
- `scripts/doc-link-exceptions.json` 只登记无法修改的外部或历史目标，每条必须有 `source`、`target`、`reason`；例外失效即删除，由门禁报“过期”。
- 新增或修改配对文档后运行 `python scripts/verify_docs.py pairing --write <中文主文件>` 重记哈希。

## 反模式

重复上级规则；保留历史段落；手抄目录或清单；写推理过程和背景故事；一段拆成多行；用加粗和感叹号代替结构；把计划写进笔记或正文。
