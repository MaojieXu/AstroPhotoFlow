# 当前开发上下文

现代化、设备精简与滤镜Channel累计候选已获用户集成/普通推送/清理及Chat归档授权；Manager独立审查、最小修复与必要验证已完成，见[集成记录](test-matrix.md#modernization-equipment-channel-integration)。以下各轮“未提交/未运行”为历史状态，不覆盖本次结果；最终远端SHA与清理情况见Manager交付报告。

当前设备Feature已增加只能手填的滤镜Channel，组合按通道＋可选带宽展示，选择器保留实际名称；单相机／单望远镜、多滤镜及精简预设规则继续有效。原optics-b数据与历史原文保留，最新预览及检查边界见[当前计划](implementation-plan.md)和[Channel记录](test-matrix.md#filter-free-text-channel)。

本轮纠正与收尾（2026-11-01）：前次完成判断遗漏旧浏览器入口及CI uv差异，现已补齐，并按[58项审计](modernization-audit.md)重新复核G1—G7。最新证据见[本轮收尾记录](test-matrix.md#modernization-g7-browser-closure)，未提交、合并或发布。

核对日期：2026-11-01。集成分支：`dev`；热更新与Siril SDK v2的本地验证分别见[热更新记录](test-matrix.md#hot-reload-integration)及[Siril记录](test-matrix.md#siril-sdk-v2-integration)。本文是有效状态摘要；实时服务状态以实际查询为准，历史端口和“已启动”记录不能代替当前观察。

G7审计发现G5曾把主体逻辑集中转入WorkspacePage，文件职责完成判断过早；现已按实际能力补拆，完整自研UI521项、当前宿主120项及13项浏览器均通过，文件清单与独立打包验证完成。详见[职责审计纠偏](test-matrix.md#modernization-g7-capability-audit)。

工作流归属见[有效需求](../requirements/README.md#native-workflow-ownership)：使用ComfyUI原生工作流，已取消并拆除自研workflows、项目图生命周期、完整运行库／图副本及先保存准入。[现代化计划](modernization-plan.md)与[文件计划](file-refactoring-plan.md)的G0—G7本地候选及授权验证已完成，见[最终记录](test-matrix.md#modernization-g7-browser-closure)。代码尚未提交、合入dev或发布；本轮只使用私有workspace和合成素材，真实Siril运行不等于用户真实天文素材或全部160节点科学验收。

## 已有什么

| 能力 | 当前事实 | 证据与限制 |
|---|---|---|
| 工作台基础 | 默认workspace、配置保存／采用值、自动端口回写、启停／重启及网页配置已集成；M1用户批准已有记录 | [M1](test-matrix.md#m1-foundation)；MCP控制及后续占用交接不能据此认定完成 |
| 数据 | 素材与集合固定版本、项目资料、设备快照、校准、导入／预览／回收站；固定科学输入、整夜递归确认导入／聚合等待、独立项目固定引用及Data完整成员显式保存／导出已集成dev | [双域MCP与Data验证](test-matrix.md#database-mcp-data-export-integration)；M2整体验收、复杂格式与完整产品验收未因此完成，本候选闭环范围见最终记录 |
| Siril Bundle | Siril 1.4.4／Bundle `0.2.0-dev.2`／SDK v2，160操作与节点、199命令覆盖；具名输入、多输出、分析／直方图、双语显示及官方固定版本选择，本Feature已移除SDK v1 | [科学接入验证](test-matrix.md#siril-sdk-v2-integration)、[双语与版本切换验证](test-matrix.md#agent-i18n-bundle-integration)；网页发现官方tag并显式确认安装／升级／回退，本Feature固定目录已采用SDK v2开发tag v0.2.0-dev.2；未宣称160节点逐项科学验收，seqprofile及外部依赖限制保留，完整M3／M4批准未完成 |
| 节点 | workspace JSON定义保存／更新差异及Bundle原生加载、HTTP／CLI／MCP发现已有实现 | Siril双语功能／命令名、两级分类、workspace开发源码绑定及显式目标自动完整结果已集成；[审查与验证](test-matrix.md#node-ui-bundle-integration)。通用编辑器、完整确认更新与端口重映射仍待补；Python／复合仍后续目标 |
| 在线画布 | 固定素材入图、绝对路径托管导入、读取实际图、加节点／调参数／连线／删除及直接MCP编辑已有窄实现；保留目标／内容校验、回执和原生撤销 | 画布HTTP／用例已归接入层；不能据此认定完整Agent闭环通过；项目图关联与独立运行库已取消 |
| 网页 | 菜单／设置精简、素材列表与原生拖拽、workspace内容跳转已合入dev | [三分支集成记录](test-matrix.md)：只做Git一致性核对，未重跑合并后应用验收；workspace分支没有额外新增实现 |
| 开发更新与Bundle维护 | workspace感知Vite前端更新、已安装Bundle的SDK Python适配器及声明JSON热加载、安装／更新／卸载刷新能力已实现；按用户要求取消运行／预览占用拒绝及在途旧实现保护 | [本地集成验证](test-matrix.md#hot-reload-integration)；平台后端Python仍显式重启，Node.js适配器加载未实现；长期可靠性及真实跨发布版本升级仍待验证 |

上述状态来自当前源码与已有记录；定向回归及合成数据实际运行不替代完整产品或用户验收。

## 仍然缺什么

- 本候选的原生草稿、保存／撤销、队列／历史、自动结果及科学处理闭环已有隔离验证；下一步是用户评审，获准后按流程进行独立审查与集成，不再建设自研工作流生命周期。
- 具体软件调用的跨重启实际观察、两类输入保证及活动输入保护、实际目标范围／缓存与停止核对。
- 各已执行图像节点的多次完成预览及跨图归属、网页选择完整结果交数据模块保存的完整闭环。
- 通用节点制作界面、影响确认与参数／端口更新的真实验证；本轮Bundle热加载已有定向覆盖，长期可靠性与真实跨发布版本升级仍待验证。
- 完整真实客户端的目标／内容冲突处理、切图暂停及运行准入；画布按明确指令直接编辑，不再要求接管／交回。本候选已采用data／software／graph类型化工具与BM25最多10项检索；Skill管理／反馈等未列入本轮的产品能力仍是后续任务。
- 完整比较、跨软件、个人偏好与交接摘要、固定结果经原生队列继续处理、Python／复合节点及完整Windows交付。Linux／WSL独立验收。
- 已实现代码的未验收项：合并后的设置视觉、简约列表窄侧栏、统一查看器及完整安装／卸载交互。不要从历史通过记录推定这些全部通过。

<a id="equipment-model-search-enhancement"></a>

器材型号搜索和未知型号手填待排期，保留现有字段；资料为`C:/Users/Administrator/Desktop/WorkSpace/信息采集/data/json/`，本轮不继续设计或实现。

## 怎么继续

[当前计划](implementation-plan.md)只细化下一项实际任务。用户已同意旧22 Batch仅作参考，后续按当前目标重新排序；编号、前置状态及旧“未开工”文字不再约束执行。未完成产品目标保留在 [需求](../requirements/README.md)，不能因归档而默认为取消。

## 本机开发约束

- Python `.artifacts/venvs/dev`，根`uv.lock`；Node26.8.2、pnpm11.13.1及`frontend/pnpm-lock.yaml`。固定本机工具在`.artifacts/redesign/bin`，先核对实际版本。
- 正常dev workspace为`.artifacts/workspaces/dev`，配置基线网页31388／服务31390；实际监听须查询。本轮未启停、更新或迁移它。
- 受限环境可能重定向`LOCALAPPDATA`；不要据此改产品路径解析或重建共享CPU runtime。
- Feature准备等级、预览展示和验证阶段按[开发流程](README.md)执行；文档链接检查和对应接口生成可随文档任务执行。不操作真实素材、全局MCP或默认指针。
- 不恢复旧restructure／redesign任务。当前只做开发构建，正式发布另行批准。

历史逐轮日志和结论按 [验证记录](test-matrix.md) 具体条目查；旧上下文原文可从Git `51046067:docs/development/current-context.md`查回，不再重复注入每个任务。
