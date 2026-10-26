# Python 平台源码导航

- 先读 ../../docs/architecture/module-map.md 与根 AGENTS.md；按所属模块和 contracts 定位任务。
- core 为基础，modules 为业务能力，contracts 为公共数据定义，interfaces 为接入和装配。
- 根 client.py 和 cli.py 是保留的公开入口；comfyui/proxy.py 是固定引擎网关，vendor/ 是随包资源。
- 业务变化只进入所属模块；不恢复 backend、client_domains、agent_tools 等旧源码树。
- 未实现目录只有文档，不宣称能力可用。验证：`uv run --locked --no-sync pytest -q`。
