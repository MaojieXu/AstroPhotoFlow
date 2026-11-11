# 测试与验证

[English](testing.en.md) | 中文

测试分层覆盖文档、Python、架构、前端、浏览器与发行；本地和 CI 使用同一组命令。实现、自动验证、真实运行与用户验收分别说明，不能互相代替。

## 测试分层

| 层 | 范围 | 入口 |
| --- | --- | --- |
| 文档 | 预算、配对、换行、链接与 notes/skills 检查，以及门禁自身行为 | `pnpm check:docs`；`pytest tests/docs` |
| Python | 单元、模块、接口、集成、核心与打包布局 | `uv run --locked --no-sync pytest -q` |
| 架构 | Python 导入边界与前端依赖方向 | `pnpm check:boundaries` |
| 前端 | UI 包与原生桥接的单元测试 | `pnpm test` |
| 浏览器 | 真实服务上的 Playwright 端到端测试 | `pnpm test:browser` |
| 发行 | wheel/sdist 资源、仓库外安装与无 Node 重建 | `python scripts/verify_distribution.py` |

## 门禁与 CI

- `docs` job 在 Ubuntu 上运行文档门禁与 `pytest tests/docs`。
- `product` job 在 Ubuntu 和 Windows 上按项目锁文件安装依赖、构建前端、发现浏览器用例、运行 Python 与前端测试，并构建和验证发行物。
- `product` job 的 Python 测试包含语言覆盖守卫：网页 `en`/`zh` 目录键集一致，平台错误全部经消息目录渲染。
- `checks` job 汇总前两者，状态名 `all checks passed`，供分支保护引用。

## 回执写法

- 合入 `dev` 前在交付说明中记录实际执行的命令与结果；发布 PR 写入 Testing。未执行的相关检查写明原因。
- 完整日志放 `.artifacts/reports`，例如 `python.xml`、`browser/` 与 `packaging.json`。
- 实现、自动验证、真实运行与用户验收分别说明，不能互相代替。
- 已通过的检查不重复跑；改动范围变化后再补受影响检查。

## 浏览器测试边界

- 浏览器测试只在本机自选的 workspace 上运行：`APF_WEB_URL` 必须是回环地址，并与 `APF_TEST_WORKSPACE` 指向同一 workspace；`dev` 与 `default` 共享 workspace 被拒绝。
- CI 只执行 `pnpm test:browser --list` 发现用例，不启动服务。
- 默认配置运行原生网页、布局与工作台设置用例；`pnpm test:browser:modernization` 与 `pnpm test:browser:native` 是独立配置，按改动范围选择。
- 报告写入 `.artifacts/reports/browser/`。并行浏览器测试用 `APF_BROWSER_REPORT` 分配独立子目录，并行 pytest 用 `--basetemp=.artifacts/pytest-<task>` 分配独立临时目录。
- worker 为 1、失败不自动重试；失败保留 trace 与截图，原生队列与重启场景未显式启用时记为 skip，不记为通过。

## 真实素材

`tests/real_data/` 使用五个原始素材目录，显式分组清单在 `tests/fixtures/real-data-catalog.json`。清单包含 30 组子帧与 10 个独立 Master，共 514 个文件。用例检查全部头部、代表样本导入、当前成员、共享校准、接口一致性、可读目录、JSON 同步及状态传播。

素材根目录通过 `--real-data-root` 指定。省略时相关用例说明跳过原因，显式指定后缺失目录或基线差异按失败报告。源文件只读，副本、数据库和故障注入使用 pytest 临时目录。完整复制单独要求 `--run-full-import`。

```powershell
uv run --locked --no-sync pytest tests/real_data --real-data-root "E:/AstroPhotoFlow/Erellaz" -m "not full_import"
uv run --locked --no-sync pytest tests/real_data --real-data-root "E:/AstroPhotoFlow/Erellaz" --run-full-import -m full_import
```

标记使用 `real_data`、`full_import`、`plan_a`。回执写入 `.artifacts/reports/real-data/`，保存来源、任务 ID、阶段、错误与通过／失败／跳过数量。状态传播用受控成功回执验证，真实软件处理另记实际执行情况。

## 验证边界

- 自动测试证明实现与契约；真实运行证明服务、引擎与原生页面状态；用户验收由用户在真实素材与工作台上完成。
- 不把预览、合成探针或 skipped 场景写成通过。
- 打包验证必须在仓库外安装，并在无 Node 环境重建 wheel。
