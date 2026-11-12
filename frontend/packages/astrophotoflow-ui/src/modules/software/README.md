# 软件包界面

提供 `SoftwarePanel`、软件客户端与工作区组合式函数，入口由包 `src/index.ts` 导出。

## 行为

面板显示常驻软件的固定名称、就绪状态点与安装/卸载入口；服务报告新 Bundle 版本时显示更新入口，原因经状态点查看。安装卸载计划必须由原生确认弹窗批准（宿主注入 Button/Dialog，同一原生 WebSocket 回执），UI 不自行认定安装、加载或调用成功；未知受理结果先查询原操作。

## 数据访问

契约只从 `generated/api` 重导出；预览请求携带固定引用、参数与取消信号，并释放 keepalive。查询按 workspace、包与 operation_id 隔离并传取消信号，运行状态 1 秒、普通状态 10 秒轮询，发行版本只显式检查；写入无重试并失效原工作区缓存。

## 测试

包内 `tests/modules/software/`（根 `pnpm test`）。软件包行为见[软件子系统](../../../../../../docs/subsystems/software.md)。
