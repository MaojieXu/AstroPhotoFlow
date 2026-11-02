# G1—G7逐项复核

本表按现代化计划与文件计划列出可检查的交付项。2026-11-01新增浏览器收尾；旧“完成审计”遗漏默认入口的结论撤回。本轮不以文件存在、manifest无缺路径或单次绿灯替代需求覆盖。

代码路径相对`src/astrophotoflow/`或前端／独立Bundle；报告统一在`.artifacts/reports/modernization/`。未改变的产品代码在核对字节一致后复用前轮验证，不宣称重新执行。本轮58项逐条核对完成；补齐旧默认入口和CI uv版本两个实际遗漏，最终状态以验证矩阵本轮记录为准。

## G1 数据模型与业务服务

| ID | 核对项 | 实现依据 | 验证依据 | 状态 |
|---|---|---|---|---|
| G1.01 | 模型／服务／HTTP归属分离、项目同名覆盖消除 | modules/data各所有者；interfaces/http/data | 完整平台回归、架构检查 | 已核对完成 |
| G1.02 | 新0001_baseline；旧库不自动转换 | core/database/schema.py及alembic/versions | 新workspace健康、分发独立初始化 | 已核对完成 |
| G1.03 | Asset当前资料／AssetVersion文件事实及观察快照分属 | data/assets/models.py；contracts/metadata.py | 数据模型／元数据纠正回归 | 已核对完成 |
| G1.04 | 常用资料列化、格式开放JSON、HDU科学资料 | data/assets/models.py；data/formats | 完整Data回归及格式负向样本 | 已核对完成 |
| G1.05 | kind判别设备规格／快照，不使用EAV | contracts/equipment.py；data/equipment | 设备、快照及SDK判别联合验证 | 已核对完成 |
| G1.06 | 稳定组合成员ID／顺序；注册和组合内来源互斥 | data/equipment/models.py | CheckConstraint与组合成员回归 | 已核对完成 |
| G1.07 | 预设默认／明确禁用／选定成员；稀疏省略/null/0 | data/equipment；contracts/setups.py | 多滤镜、零增益、选择关系回归及浏览器 | 已核对完成 |
| G1.08 | 删除影响确认，清除当前选择但保留快照 | data/equipment；interfaces/http/data | 删除预检／确认回归及浏览器 | 已核对完成 |
| G1.09 | 固定集合成员版本／顺序；默认校准和成员覆盖关系 | data/datasets/models.py及calibration.py | 固定输入、校准、继承／禁用回归 | 已核对完成 |
| G1.10 | 项目仅资料与固定素材／集合引用，调用方同步 | data/projects；生成契约 | 真实MCP域流程及项目GUI／草稿 | 已核对完成 |

## G2 SQL查询与摘要

| ID | 核对项 | 实现依据 | 验证依据 | 状态 |
|---|---|---|---|---|
| G2.01 | SQL可见范围、回收站、EXISTS筛选、聚合、稳定排序／计数／limit-offset | data/library/queries.py | 查询与分页回归 | 已核对完成 |
| G2.02 | LibraryItemSummary不嵌套完整成员 | contracts/assets.py及library查询 | 响应大小／大集合规模证据 | 已核对完成 |
| G2.03 | 成员独立分页，组合条件先于分页；删除前端全成员分页 | datasets查询；UI datasets/queries | 1001成员回归、52成员实际翻页 | 已核对完成 |
| G2.04 | 一致／混合或缺失／全未知摘要；SQL筛选选项 | library摘要和聚合 | 混合资料、空集合、缺失值回归 | 已核对完成 |
| G2.05 | 组合成员关系筛选／排序、Unicode casefold、稳定ID及索引 | equipment查询、search模型及baseline | Unicode与稳定分页／EXPLAIN | 已核对完成 |
| G2.06 | 1千／1万／10万合成元数据；SQL数、ORM数、大小及查询计划 | scripts/benchmark_library.py | g2/library-benchmark-current/report.json；复杂查询秒级如实保留 | 已核对完成 |

## G3 契约／SDK

| ID | 核对项 | 实现依据 | 验证依据 | 状态 |
|---|---|---|---|---|
| G3.01 | 请求、查询模型、JSON及原生响应明确类型／operationId | contracts；interfaces/http | 完整平台及生成边界样例 | 已核对完成 |
| G3.02 | 健康／能力／选择／上传回执及媒体类型、空响应完整 | OpenAPI及真实HTTP路由 | 协议／媒体回归及真实浏览器 | 已核对完成 |
| G3.03 | 统一ErrorEnvelope、字段诊断和request_id | contracts/common；HTTP及client/errors | 真实MCP错误UUID与HTTP错误回归 | 已核对完成 |
| G3.04 | OpenAPI本地生成TS／Fetch／Zod4／Query配置及响应验证 | scripts/export_openapi.py；UI openapi-ts.config.ts | 22产物字节一致；可空／可选／联合／数组／日期／二进制样例 | 已核对完成 |
| G3.05 | 消除重复HTTP DTO／路径，薄客户端配置与传输生命周期 | UI core/api、data/api；Python interfaces/client | 类型、客户端及请求取消验证 | 已核对完成 |
| G3.06 | 画布／软件包／原生消息／结果契约替代workflows占位 | contracts/canvas.py、packages.py、native.py及结果契约 | 旧类型／占位字段清理与完整平台回归 | 已核对完成 |

## G4 FastMCP／CLI

| ID | 核对项 | 实现依据 | 验证依据 | 状态 |
|---|---|---|---|---|
| G4.01 | FastMCP4.1.4，data/software/graph本地mount分层 | interfaces/mcp/server.py | 97工具真实stdio及schema回归 | 已核对完成 |
| G4.02 | 类型化工具共享HTTP客户端，不访问ORM；Siril按节点目录发现 | interfaces/mcp各能力；interfaces/client | 递归边界和全业务域协议 | 已核对完成 |
| G4.03 | 删除双网关／Registry／动态参数模型／手工参数树 | MCP和CLI当前文件树 | 旧入口搜索、协议和CLI生成验证 | 已核对完成 |
| G4.04 | BM25最多10项完整schema，双语检索、已知名直达 | FastMCP搜索视图 | 代表性检索及直接调用 | 已核对完成 |
| G4.05 | 完整目录生成call-tool；Cyclopts本机管理；无token／绝对路径生成物 | scripts/generate_cli.py；interfaces/cli | 两进程一致及真实CLI流程 | 已核对完成 |
| G4.06 | 错误／图片统一；未知受理不自动重放 | mcp/errors.py及强类型返回 | HTTP/MCP错误、SDK v2图片内容、回执查询 | 已核对完成 |
| G4.07 | 离线工厂、官方--reload及重新连接；更新Skill／示例 | server工厂；Skill和文档 | mcp-real-reload-final-tests.log；stdio重连 | 已核对完成 |
| G4.08 | 只读Resource视图不作第二数据库；无绕过原生队列整图入口 | MCP职责及实际注册目录 | 架构约束／工具目录核对 | 已核对完成 |

## G5 前端请求／页面职责

| ID | 核对项 | 实现依据 | 验证依据 | 状态 |
|---|---|---|---|---|
| G5.01 | Vue Query服务数据／Pinia界面草稿／原生Store画布分工 | UI core/query及能力queries/mutations；宿主桥接 | UI521／宿主120及边界检查 | 已核对完成 |
| G5.02 | workspace/资源/参数/分页查询键，取消过期读取并传AbortSignal | query keys、view input、SDK传输 | 快速切页、工作区和异步视图回归 | 已核对完成 |
| G5.03 | always、零重试、5秒新鲜、5分钟回收、不聚焦刷新 | core/query/client.ts | 配置与浏览器断网查询 | 已核对完成 |
| G5.04 | 列表10秒刷新、活动任务1.5秒／终态停止、资源失效与Bundle事件 | imports任务及资源queries/mutations | 任务终态、跨入口变更及原生事件 | 已核对完成 |
| G5.05 | 后台刷新／错误／旧写入回执不覆盖草稿，不盲目重发 | record editor、inline save及能力编辑hooks | 组件与真实revision冲突／草稿测试 | 已核对完成 |
| G5.06 | 移除WorkspaceContext／RecordData及重复请求槽／定时器 | WorkspacePage与独立编辑／选择／导航／显示能力 | 当前函数清单、UI／浏览器及循环检查 | 已核对完成 |
| G5.07 | 显式props/emits；原生仅经包导出；无workflow UI归属 | UI能力组件与宿主canvas/results/media | 边界检查、原生草稿／撤销／查看器 | 已核对完成 |
| G5.08 | 预览／缩略图／视频与租约由明确所有者维护 | media hooks与宿主MediaViewer/viewport | 媒体释放、查看、取消和PNG真实预览 | 已核对完成 |

## G6 Siril／原生执行与开发基础

| ID | 核对项 | 实现依据 | 验证依据 | 状态 |
|---|---|---|---|---|
| G6.01 | 删除workflow模块／图副本／项目图生命周期及先保存准入 | modules当前树、contracts和native接入 | 未命名草稿真实队列；旧路由／模型负向断言 | 已核对完成 |
| G6.02 | 具体调用归software，已检查结果／IMAGE固定化归data，装配归interfaces | software/execution、data/results、interfaces/application | 完整平台、真实Data→Siril→Data闭环 | 已核对完成 |
| G6.03 | 参数／版本／输入顺序／日志事实及精确执行/端口/成员引用 | 调用记录与结果契约 | 科学输入哈希、所选结果保存／导出 | 已核对完成 |
| G6.04 | 取消受理／实际停止／unknown分别表达；不猜退出码、不重放 | execution/processes、runner、records | 真实Siril与原生interrupt、竞态确定性回归 | 已核对完成 |
| G6.05 | Siril1.4.4保留，typed recipes、职责拆分及有限模式处理 | Bundle adapter/recipes及planning/analysis等 | 独立Bundle56与实际科学场景 | 已核对完成 |
| G6.06 | SDK v2唯一，移除v1与单输入／输出转换；同源目录生成 | Bundle与平台SDK、tools/catalog | 160操作／199命令；322生成物不变 | 已核对完成 |
| G6.07 | 完整自有模块树重新加载，helper／同大小快速修改不取旧字节码 | Bundle loader与源指纹 | 包加载／helper变更／真实热更新回归 | 已核对完成 |
| G6.08 | watchfiles范围／防抖／生成失败可见、避免生成事件循环 | development及native/bundles/watcher | 新增删除声明、生成失败与生命周期验证 | 已核对完成 |
| G6.09 | workbench、native context/bootstrap/pages、格式／科学／导入／媒体／清理分责 | 各当前所有者；公开入口 | 完整平台及源码依赖边界 | 已核对完成 |
| G6.10 | HTTPX lifespan、配置Pydantic/TOML、uv0.13.5统一及Ruff | HTTP lifespan、core/config、bootstrap/CI | 客户端关闭／配置状态、Ruff、固定版本核查 | 已核对完成 |

## G7 验证／清理／交接

| ID | 核对项 | 实现依据 | 验证依据 | 状态 |
|---|---|---|---|---|
| G7.01 | 旧3脚本有效断言转Playwright Test并删除执行路径 | native-web/native-layout/workbench-settings.spec.ts及fixture | default-browser-isolated-report.log：8通过、0跳过，含真实重启／恢复 | 已核对完成 |
| G7.02 | 默认test:browser及专项入口、README和迁移映射一致 | package.json；开发流程；browser-test-migration.md | --list发现8；无手动chromium.launch／旧入口 | 已核对完成 |
| G7.03 | 隔离URL/health/config/data路径验证；拒绝dev/default；fixture释放 | native.fixtures.ts | 正向默认8及保护工作区预期失败 | 已核对完成 |
| G7.04 | 完整平台／UI／宿主／Bundle、类型及依赖检查 | 对应已执行日志及当前产品hash | 964通过16skip；521／120／56；未变化产品证据复用 | 已核对完成 |
| G7.05 | 原生保存／撤销／历史／队列、旧内容／切图／关闭／未知回执 | 原生和画布专项 | 真实浏览器与MCP回执；无自动重放 | 已核对完成 |
| G7.06 | 合成输入实际Siril及所选完整结果查看/保存/导出 | 科学专项与新上传fixture | AutoStretch、校准、配准/叠加、分析、压缩、多输出、缺依赖及取消 | 已核对完成 |
| G7.07 | 全部自研文件／函数／原始基线及删除合并处置 | source-inventory、file-refactoring-transitions | 独立路径／符号／hash／删除解释复核 | 已核对完成 |
| G7.08 | 完整生成／官方资料／本地链接一致性 | 固定生成入口及官方manifest | 22／322生成物、254原文hash及文档链接 | 已核对完成 |
| G7.09 | 独立wheel/sdist/Node-free重建与模块完整性 | build_release、verify_distribution | 已执行分发报告；本轮仅测试/入口/文档变更，产品字节比对 | 已核对完成 |
| G7.10 | 最终两仓库HEAD/dirty、版本/入口、预览和限制交接 | 当前计划／验证矩阵及本表 | 提交／合并／发布不在授权内；最终核对后才标记完成 | 已核对完成 |

## 范围与未验证事项

以下不混记为代码开发欠项或已通过：用户真实素材／160操作逐项科学验收、长期热加载与跨发布升级、Linux/WSL；seqprofile仅128×128单帧窄场景；10万复杂查询仍秒级。两笔历史unknown保留原事实，不重发。本轮的原生配置真实重启及恢复单独验证，不据此宣称运行中软件调用的所有跨重启恢复场景已验收。用户评审、独立集成审查、提交、合并与发布尚未执行。
