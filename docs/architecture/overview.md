# 架构：职责与数据归属

AstroPhotoFlow复用ComfyUI的网页、图文件、画布和执行引擎，增加天文数据与软件能力。常驻进程只有原生网页／引擎与FastAPI领域服务两个。2026-10-31目标调整为core、data、software、nodes及interfaces；模块是代码职责，不对应常驻服务。有效工作流归属见[需求](../requirements/README.md#native-workflow-ownership)。

## 谁负责什么

| 模块 | 权威数据与责任 | 按需入口 |
|---|---|---|
| ① core | 配置、认证、数据库连接／迁移、进程与维护；少量文件记录最新配置、实际运行和最近启停 | [README](../../src/astrophotoflow/core/README.md) |
| ② data | SQLite素材／集合版本、项目资料、设备快照、校准、原件保护及用户选择结果；科学文件单独存放 | [README](../../src/astrophotoflow/modules/data/README.md) |
| ③ software | 固定软件包、安装／就绪、实际调用与停止观察；Siril实现来自独立Bundle | [README](../../src/astrophotoflow/modules/software/README.md) |
| ④ nodes | workspace JSON中的可编辑节点定义、更新差异及派生目录 | [README](../../src/astrophotoflow/modules/nodes/README.md) |
| interfaces | HTTP／MCP／CLI、原生画布桥接和具体跨模块用例装配；不拥有图或调度 | [入口](../../src/astrophotoflow/interfaces/README.md) |
| ComfyUI原生体系 | 工作流编辑、图文件、草稿、保存、撤销、转换、队列、执行历史、进度和取消入口 | [接入导航](module-map.md) |

原`modules/workflows`目录已删除：软件调用事实归`software/execution/records.py`，已检查文件事实归`data/results/`，原生执行组合归`interfaces/application/software_calls.py`，HTTP分别归`interfaces/http/software_calls.py`与`interfaces/http/data/`。原生prompt和具体execution／call UUID标识调用／结果，不建立平台Workflow或完整Run聚合；结果消费不扫描软件私有记录。本Feature已移除SDK v1；其他G6内部拆分仍在进行。

## 三条链路

1. **编辑**：用户明确指令后的网页或MCP／CLI请求 → 共享HTTP与在线页面桥接 → 核对页面／工作流／画布／内容 → 原生节点、控件和连线操作 → 原生撤销／草稿／保存。不维护接管／交回会话；原生workspace JSON是唯一可编辑当前图。
2. **处理**：原生转换与队列 → 原生节点／接入装配 → data解析固定科学输入 → software执行具体调用 → data检查科学产物 → 原生展示。未命名草稿按ComfyUI机制提交；具体调用固定输入、参数和版本，图／prompt记录使用原生历史。
3. **保存结果**：原生展示按原生workflow／prompt／节点定位data的已检查结果；用户选择完整成员后交data入库或导出。software保存进程及调用事实，data保存结果文件事实，预览不成为科学原件。

在线页面的消息和回执是当前连接观察。取消受理、实际停止、保存、画布应用、执行及素材登记分别表达；未知先查询，不自动重放。

## 依赖边界

- `contracts` 只依赖标准库／Pydantic；`core` 不依赖业务或接入层，显式Alembic元数据装配除外。
- 同进程通过公开入口合作，不读取其他模块私有ORM。interfaces具体用例装配data、software和nodes；data不扫描software私有记录，软件执行器接收已解析输入，不读data私有模型。nodes不反向依赖执行器。
- 网页、CLI、MCP共用HTTP业务能力；MCP协议和应用装配归`interfaces`。本机启停由core在HTTP服务外执行。
- 私有UI包只导出组件／客户端；原生Store、画布和转换协调在宿主桥接，UI不得反向导入原生单例。
- 原生图文件、④定义JSON、业务SQLite及科学文件各守其权威；不新增第二套编辑、调度、协作账本或通用恢复系统。

<a id="prototype-gates"></a>

## 尚须通过真实联调的边界

两类输入保证、目标范围与科学缓存、软件实际停止、完成预览和跨图归属、所选结果保存、真实Agent目标／内容冲突处理、FastMCP跨原生画布的完整联调，以及取消完整图快照后的原生草稿／队列／历史闭环。节点热加载与更新不能靠刷新或定义文件存在推定成立。

哪些已有代码、哪些只缺验收见 [当前上下文](../development/current-context.md)；关键选择及原因见 [ADR](../decisions/README.md)。源码定位见 [源码导航](module-map.md)，产物规则见 [文件布局](repository-layout.md)。
