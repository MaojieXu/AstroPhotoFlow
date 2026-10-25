# 开发与构建

需要 Python 3.12、Node.js 22.13+ 和 Corepack。前端保持 `package.json` 指定的 pnpm 版本，Python 使用根 `uv.lock`。以下命令在仓库根执行。

```powershell
corepack pnpm install --frozen-lockfile
corepack pnpm build
$env:UV_PROJECT_ENVIRONMENT = "$PWD/.artifacts/venvs/dev"
uv sync --locked --extra dev --python 3.12
uv run --locked --no-sync pytest -q
corepack pnpm test
```

根 Python 测试递归发现 `tests/`，前端测试只发现 `tests/frontend/`。已有代理测试的 aiohttp 依赖统一在 dev extra。测试报告、缓存与临时 workspace 放在 `.artifacts/`；原始本地 Astro Dataset 保持忽略，不进入 Git 或发行包。

```powershell
uv run --locked --no-sync python scripts/build_release.py
uv run --locked --no-sync python scripts/verify_distribution.py
```

发行脚本先构建前端，再生成 wheel 和 sdist；不清空整个 `dist` 或 `build`。Python 构建中间文件位于 `build/python`，前端输出独立位于 `build/frontend`。发行验证从源码目录外安装并启动实际 CLI／服务，另从 sdist 重建 wheel，检查迁移、插件与静态资源。

checkout 扩展启动时，ServiceManager 使用仓库根 uv 项目并要求依赖已同步；它不在 ComfyUI 启动时安装依赖或自动升级已有数据库。若使用上述自定义环境，启动 ComfyUI 的终端也应设置同一个 `UV_PROJECT_ENVIRONMENT`。

源码实现、测试和维护脚本分别放入 `src/astrophotoflow`、`tests`、`scripts`。新增需求先更新[测试矩阵](test-matrix.md)，当前上下文只维护[一份](current-context.md)；归档 Prompt 不作为新任务指令。
