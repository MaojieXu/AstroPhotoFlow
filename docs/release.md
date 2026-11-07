# 发行

[English](release.en.md) | 中文

发行只做 `X.Y.Z-dev.N` 开发版本，版本号唯一来源是 `pyproject.toml` 的 `project.version`。构建产物是携带网页与固定引擎的 wheel 与 sdist；tag 由人工创建。

## 版本号

- 版本号只从 `pyproject.toml` 的 `project.version` 读取，打包与元数据都使用该字段。
- 只做 `X.Y.Z-dev.N` 开发版本，`N` 递增；不在文档或脚本中另立版本号。
- `main` 只接收来自 `dev` 的发布 PR；主分支合并与 tag 需用户另行授权。

## 构建

在已准备环境的仓库根运行：

```powershell
uv run --locked --no-sync python scripts/build_release.py
```

- 脚本要求 PATH 中有 Node 与 pnpm；先按锁文件安装前端依赖并构建前端，再调用 `python -m build`。
- wheel 携带网页产物与固定引擎归档，用户安装后不需要 Node。
- 产物写 `.artifacts/dist`，Python 中间产物在 `.artifacts/build/python`；脚本确认 wheel 与 tar.gz 都产出，缺失即失败。

## 发行验证

构建后运行：

```powershell
uv run --locked --no-sync python scripts/verify_distribution.py
```

- 校验 wheel 必需资源：网页、固定引擎归档及哈希、路由清单、Bundle 目录、数据库迁移与产品模块。
- 在仓库外临时环境安装 wheel，冒烟 CLI、导入与数据库迁移。
- 解包 sdist，在无 Node 环境重建 wheel 并复验。
- 报告默认写 `.artifacts/reports/packaging.json`；`--dist`、`--report`、`--rebuilt-wheel-dir`、`--temp-dir`、`--sdist-build-python` 可改路径与重建解释器。

## 发布流程

- 从 `dev` 向 `main` 发发布 PR，使用同一 CI 门禁与 1 名独立 reviewer。
- 合并后由人工在发布提交上打 tag；主分支推送、tag 与对外发布需用户明确授权。
