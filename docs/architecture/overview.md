# 架构：职责与数据归属

AstroPhotoFlow复用ComfyUI的网页、图文件、画布和执行引擎，增加天文数据与软件能力。常驻进程只有原生网页／引擎与FastAPI领域服务两个；模块是代码职责，不是五个服务。

## 谁负责什么

| 模块 | 权威数据与责任 | 按需入口 |
|---|---|---|
| ① core | 配置、认证、数据库连接／迁移、进程与维护；少量文件记录最新配置、实际运行和最近启停 | [README](../../src/astrophotoflow/core/README.md) |
| ② data | SQLite素材／集合版本、项目资料、设备快照、校准、原件保护及用户选择结果；科学文件单独存放 | [README](../../src/astrophotoflow/modules/data/README.md) |
| ③ software | 固定软件包、安装／就绪、实际调用与停止观察；Siril实现来自独立Bundle | [README](../../src/astrophotoflow/modules/software/README.md) |
| ④ nodes | workspace JSON中的可编辑节点定义、更新差异及派生目录 | [README](../../src/astrophotoflow/modules/nodes/README.md) |
| ⑤ workflows | 原生图的项目关联、运行、完成预览和当前控制，协调公开能力；这些目标尚未全部实现 | [README](../../src/astrophotoflow/modules/workflows/README.md) |

## 三条链路

1. **编辑**：网页或MCP／CLI请求 → 共享HTTP与在线页面桥接 → 核对目标／内容／控制 → 原生节点、控件和连线操作 → 原生撤销／草稿／保存。原生workspace JSON是唯一可编辑当前图。
2. **处理**：⑤固定科学引用交②解析 → 原生转换与队列 → ③调用软件 → ②检查科学产物 → 原生展示。完整目标要求先保存当前图再提交，⑤持久记录当次内容；当前首个Bundle调用的JSON／日志不替代完整运行库。
3. **保存结果**：已执行图像节点的完成预览归⑤；用户选择完整结果后交②入库。运行快照不成为第二份当前图，预览不成为科学原件。

在线页面的消息和回执是当前连接观察。取消受理、实际停止、保存、画布应用、执行及素材登记分别表达；未知先查询，不自动重放。

## 依赖边界

- `contracts` 只依赖标准库／Pydantic；`core` 不依赖业务或接入层，显式Alembic元数据装配除外。
- 同进程通过公开入口合作，不读取其他模块私有ORM。⑤消费②③④；④测试由应用装配协调⑤，不反向依赖执行器。
- 网页、CLI、MCP共用HTTP业务能力；MCP协议和应用装配归`interfaces`。本机启停由core在HTTP服务外执行。
- 私有UI包只导出组件／客户端；原生Store、画布和转换协调在宿主桥接，UI不得反向导入原生单例。
- 原生图文件、④定义JSON、业务SQLite及科学文件各守其权威；不新增第二套编辑、调度、协作账本或通用恢复系统。

<a id="prototype-gates"></a>

## 尚须通过真实联调的边界

项目与原生图保存联动、所有运行入口保存后提交、持久运行记录、两类输入保证、目标范围与科学缓存、软件实际停止、逐节点多次预览和跨图归属、所选结果保存、真实Agent接管／明确交回、完整MCP迁移。节点热加载与更新不能靠刷新或定义文件存在推定成立。

哪些已有代码、哪些只缺验收见 [当前上下文](../development/current-context.md)；关键选择及原因见 [ADR](../decisions/README.md)。源码定位见 [源码导航](module-map.md)，产物规则见 [文件布局](repository-layout.md)。
