# 当前计划

## 当前任务：累计候选集成交付

Manager已按用户授权完成独立审查、最小修复及必要验证，准确源码与检查结果见[集成记录](test-matrix.md#modernization-equipment-channel-integration)；推送和清理结果以Manager交付报告为准。以下为开发时需求与历史记录。

用户已确认新增Channel且只能手填，不提供下拉、建议列表或名称推断。带宽保持可选，组合标签显示Channel＋带宽；未知通道明确标示并保留原名。选择器共用同一格式再附实际名称，成员ID与顺序不变，同通道不合并。预设保存名称、FITS FILTER及科学处理规则继续使用既有含义。

- 类型化FilterSpecs新增可空channel；去除首尾空白、全空白清为未知，省略PATCH不改旧值。使用既有specs JSON持久化，无新增SQL列、表或旧数据转换；历史JSON不补写默认通道，后续真实选择快照自动冻结新资料。
- 前端纯文本框、组合标签、组合／预设候选、只读标签预览共用filterLabels.ts。滤镜排序以首个显示成员通道、数值带宽及完整原名摘要确定顺序，再以组合名和ID稳定排序；未知在后。
- OpenAPI、Hey API六份生成物和97项MCP／CLI已更新。UI及宿主类型检查、完整前端构建、后端语法／本轮Ruff、diff检查通过。必要回归用例已编写，按Feature流程未执行套件。
- 原optics-b库已停服完整备份到`.artifacts/backups/filter-channel/before-channel.sqlite3`，未运行SQL转换或通道回填。恢复后21张表所有原数据及schema完全一致：6设备、1组合、5成员、0预设，4片旧滤镜Channel均未知；完整性及外键检查通过。证据`.artifacts/reports/filter-channel/`。
- 固定恢复回执`d5a7df785e814251a5b5e1b248ec64b8`，completed/ready，37.023秒。当前预览http://127.0.0.1:32689/#/workflows。浏览器实际观察纯文本Channel输入，以及Ha＋7生成Ha 7nm的只读预览；只是未保存的新建草稿，没有修改旧滤镜或新增设备。
- 待用户手动检查并在集成阶段回归：保存／清空Channel、注册与内联、多片同通道、排序、跨入口刷新及新快照冻结。正常dev、默认workspace、旧modernization-current和独立Bundle未操作。

本轮结果见[Channel记录](test-matrix.md#filter-free-text-channel)。用户已授权本地待审提交，现代化与设备改造累计候选一并封存；不推送、不合并，交接后暂停修改。准确提交见聊天最终 Brief。

## G7入口收尾基线

本轮已迁移旧浏览器有效断言、删除旧执行路径、切换默认入口、统一CI uv并完成58项G1—G7复核。当前未提交、推送、合并或发布；获准集成后才由Git Manager组织独立审查与必要验证。最新证据见[本轮收尾](test-matrix.md#modernization-g7-browser-closure)，逐项实现／验证映射见[58项审计](modernization-audit.md)。

证据与限制统一见[最终验证记录](test-matrix.md#modernization-g7-browser-closure)；实际1155项文件／7401项函数、728项基线处置、目标签名、依赖及静态调用方见[source-inventory.json](source-inventory.json)。工具与schema事实源仍为代码及生成物，不以清单代替运行验证。

隔离预览：http://127.0.0.1:32588，服务32590；workspace `.artifacts/workspaces/modernization-current`，runtime `.artifacts/runtimes/modernization-preview`。前轮固定入口回执（本轮浏览器真实重启之后另核对实时健康）`2274fea7a5c1495bb7cf001c106f55c4` ready，24.909秒；网页健康200、原生队列运行／等待均0。其他Feature、正常dev、默认workspace和全局MCP未操作。

平台：`codex/equipment-image-mcp`，HEAD `bbb6f4a9f872fc1b79defa6dddf849247b5099d6`，dirty。独立Bundle：`.artifacts/bundles/AstroPhotoFlow-Siril`，`codex/modernization`，HEAD `f4f11b34587f989fb026607b483b740ee3b74cac`，dirty；app二进制未改。采用的发布目录快照为既有SDK v2开发tag `v0.2.0-dev.2`（`5d16fb6fc10b4ee57de428d6eba522c918b1b441`），实际开发适配器为本地源码及指纹，不将两者写成相同SHA。

保留固定输入／成员、原件保护、设备快照、画布目标／内容校验及真实取消。两笔历史unknown调用保留原事实，未重发。全部160操作逐项科学验收、用户真实素材、长期热加载及跨发布升级可靠性、Linux／WSL验收不据本轮代表性验证宣称完成。
