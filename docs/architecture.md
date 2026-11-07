# 架构

[English](architecture.en.md) | 中文

平台基于固定版本的 ComfyUI 引擎与原生网页工作台，领域能力由同进程的 FastAPI 服务提供。每个 workspace 运行两个常驻进程：ComfyUI 网页与引擎、FastAPI 领域服务。模块是代码职责划分，不对应独立服务；各子系统的行为见[子系统](subsystems/README.md)，产品规则见[产品需求](product/README.md)。

## 模块与职责

| 模块 | 负责 | 源码入口 |
| --- | --- | --- |
| `contracts` | 跨模块公共类型、枚举与校验；只依赖标准库与 Pydantic | `src/astrophotoflow/contracts` |
| `core` | 配置、认证、数据库连接与迁移、workspace 生命周期与本机进程控制 | `src/astrophotoflow/core` |
| `data` | SQLite 中的素材身份、集合固定版本、设备快照、校准关系、用户选择结果与回收站；科学文件独立存放 | `src/astrophotoflow/modules/data` |
| `software` | 固定软件包与 Bundle、安装与就绪状态、实际调用与停止观察 | `src/astrophotoflow/modules/software` |
| `nodes` | workspace JSON 中的可编辑节点定义、更新差异与派生目录 | `src/astrophotoflow/modules/nodes` |
| `interfaces` | HTTP、CLI、MCP、原生桥接与跨模块用例装配 | `src/astrophotoflow/interfaces` |
| 原生 ComfyUI 体系 | 工作流编辑、图文件、草稿、保存、撤销、转换、队列、执行历史、进度与取消 | `engine/ComfyUI` |
| 自研 UI 与宿主桥接 | 私有 Vue 组件包；原生 Store、画布与事件协调 | `frontend/packages/astrophotoflow-ui`、`frontend/src/platform/astrophotoflow` |

## 数据与状态归属

- 原生 workspace JSON 是唯一可编辑的当前图；图文件、草稿、撤销与执行历史由 ComfyUI 原生机制持有。
- `data` 拥有 SQLite 中的业务事实；科学文件单独存放，不写入数据库。
- `software` 拥有软件包目录、安装与就绪状态、实际调用与停止记录，调用事实按原生 execution UUID 关联。
- `nodes` 拥有 workspace JSON 中的节点定义与派生目录，不反向依赖执行器。
- `core` 拥有配置、认证、数据库迁移与本机 workspace 进程控制，少量文件记录最近配置与实际运行状态。
- 预览与缩略图是派生缓存，不是科学原件；未知结果先查询，不盲目重跑。

## 依赖方向与不变量

- `contracts` 只依赖标准库与 Pydantic；`core` 不依赖业务，显式迁移元数据装配除外。
- 业务模块通过各自的 `public.py` 公开入口合作，不读取其他模块的私有 ORM。
- `interfaces` 装配 `data`、`software`、`nodes` 的用例，不拥有图或调度。
- HTTP、CLI、MCP 共用服务能力，不直接写 SQLite；本机启停使用 `core` 控制入口。
- 自研 UI 包只消费原生包导出，不能反向导入原生单例。
- 不新增第二套编辑、调度、协作账本或通用恢复系统。

## 跨模块装配

- 保存结果：原生页面展示定位 `data` 中已检查的结果，用户选择完整成员后入库或导出。
- 软件调用：`software` 保存调用事实，`data` 保存已检查结果文件事实，`interfaces` 组合两者并对外暴露。
- 画布与 Agent：`interfaces` 暴露共享画布能力，原生页面桥接执行节点、控件与连线操作；外部 Agent 经 MCP 观察并修改当前图。
- 接口字段以生成物为准（见[参考](references.md)）；Python 模块交接以 `public.py` 与 `contracts` 为准。

## 运行拓扑

- 两个常驻服务：ComfyUI 网页与引擎（固定版本、受管启动）和 FastAPI 领域服务（`apf-service`）。
- 网页经 `/astrophotoflow/api/v1` 同源代理访问领域服务；CLI 与 MCP 访问 `/api/v1`。
- 每个 workspace 独立保存配置、数据库、对象、预览与运行记录；页面地址由 `core` 返回，不自行拼接。
- Vite 只用于开发期前端热更新，不增加常驻服务。

## 外部集成

- Siril 是独立私有 Bundle：平台保留 SDK、加载方式与目录快照，不把 Siril 源码或运行文件打进产品 wheel。
- 固定引擎以归档随 wheel 分发，版本与哈希以 `src/astrophotoflow/vendor` 清单为准。
- 外部 Agent 通过平台 MCP stdio 进程操作；平台不内置聊天、推理或模型会话。

## 细节归属

- 产品规则与范围：`docs/product/*`；单个子系统行为：`docs/subsystems/*`。
- 环境与命令：[开发](development.md)；测试与回执：[测试](testing.md)。
- 接口与生成物：[参考](references.md)；已做的非显然取舍：`.agents/notes/README.md`。
