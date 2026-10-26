# ① 公共基础设施

配置与启动器分别位于 config.py、workbench.py；database/ 提供连接、共享 Base、迁移工具及历史迁移；http.py 提供认证和请求会话依赖，errors.py 提供应用错误。

基础库依赖公共契约，不导入业务模块。database/alembic/env.py 是迁移装配入口，明确加载 data.models 以注册实际元数据；不把这一例外扩展到其他基础文件。

启动器从安装包根定位 web/ 和 vendor/，不会把 core/ 当作资源根。图执行仍由固定 ComfyUI 引擎承担。

验证：`uv run --locked --no-sync pytest tests/core tests/packaging -q`。
