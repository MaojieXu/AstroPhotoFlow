# ③ 外部软件接入与环境概要设计

2026-10-29 Auto Stretch 静态格式扩展候选：输入接受 fits、xisf、image、raw，完整原件交由 Siril 自身 load 解码；具体编码支持由安装的 Siril 报告。非 FITS 快速预览首次 load 原件后 resample -maxdim=1024，先保存未拉伸 linear.fit 再执行 autostretch；成功且原件大小/mtime 未变化后发布样本缓存，后续调参复用。FITS 保持既有条带采样。正式结果继续 FITS，显示不二次拉伸。视频、数值数组及指定 HDU/切片仍未接入。补写格式转发、原生解码顺序和缓存复用用例，未运行测试或实际软件处理。Python语法编译通过；仅后端及包描述变更，沿用现有前端构建；隔离重启证据见 .artifacts/implementation/siril-formats-20261029。用户预览待验收。

2026-10-29 安装故障修复候选：安全验证ZIP成员后直接解压到独占创建的固定app目录，再从正式位置检查准确版本；避免Windows下移动已检查程序目录。失败通过类型化ErrorDetail记录终态，保留部分目录及未验证版本事实，允许用户确认卸载已知失败的部分安装。原有真实网页确认和token规则保持，不自动重试；新增测试仅编写未运行，实际安装由用户验收。


2026-10-29 实时预览候选：preview_autostretch 只消费平台生成的低分辨率线性样本，使用同版本三个参数及专用CLI进程，取消按该进程句柄处理；不通过预览提交科学运行或登记素材。预览占用参与维护互斥。正式invoke继续处理完整原件。节点HTTP会话改为执行循环内拥有，避免跨循环复用。相关测试未运行，实际效果待用户验收。


本轮状态（2026-10-29）：B31 首操作锁定 Auto Stretch，B32 程序副本安装／卸载与网页确认、B33 真实 invoke／inspect／cancel／usage 已形成候选。单件／有序组 FITS 在一次 CLI 脚本处理；日志和输出保留在本次运行目录，原件只读。软件页仅保留安装／卸载与就绪点，命令目录 API 保留。首个 V3 节点通过 interfaces/siril_node.py 接入；新增测试全部未执行，M3 用户验收待完成。完整范围及证据见[本轮任务卡](../../../../docs/development/batches/03-software.md)。


具体交接见[③接口契约](../../../../docs/api/platform-contracts.md#software)及[文件级详细设计](../../../../docs/api/platform-contracts.md#software-design)：清单安装、网页计划确认、准备、更新及实际调用观察。MCP请求返回待确认动作，用户在平台网页确认具体计划后才执行。

[数据设计](../../../../docs/architecture/data-models/03-software.md)记录已确认的软件包方向。B31 已加入 Siril 1.4.4 固定清单、只读 HTTP 包查询、版本绑定的官方命令目录和逐命令平台评估，以及一份经真实 CLI 验证的 Auto Stretch 配套定义；命令资料继续通过准确版本 HTTP 查询；软件包页面仅显示安装／卸载和红绿状态点，具体计划在原生弹窗确认。未知及未审查状态保持显式。命令可浏览不表示已生成安全节点、由ComfyUI加载或逐项真实运行。B32已有安装计划／准备查询、SoftwarePanel和同WS页面事件传输候选。真实下载安装、用户确认、原生节点加载、MCP发现和真实工作流调用仍**未验证**。原生运行与现有58个数据MCP工具不能作为其实现证据。

<a id="scenarios"></a>
## 用户场景

用户从项目维护的列表在网页选择安装，或让外部 Agent 通过 AstroPhotoFlow MCP 安装。一次安装取得固定版本软件的专用副本及配套节点；节点出现在前端，也可由 Agent 发现并加入工作流。实际软件处理由⑤协调。支持哪些软件及操作，须在实施任务中锁定并真实验证。

<a id="authority"></a>
## 职责与边界

③管理软件包及可用状态，调用软件并报告实际观察。④拥有节点定义，⑤统一拥有工作流、运行记录、执行协调和Agent交互；①提供公共资源机制，②提供科学输入及用户选择后的素材登记。各模块通过公开能力交接，不复制另一模块的权威。

Agent 只需连接平台 MCP。软件内部采用 CLI、API、桥接或其他方式留待逐软件验证，不要求 Agent 自行连接下游 MCP。安装和节点发现不启动科学处理。

<a id="objects"></a>
## 必要信息

软件包名称、已安装版本、安装位置及当前可用状态；项目维护列表与下载地址。无需预设独立的安装、检测、连接或会话数据表。软件依赖、许可和实际运行条件按具体软件处理，不把节点可见当作软件已就绪。

<a id="capabilities"></a>
## 安装、准备与运行

软件包一次安装软件副本及配套节点。需要登录或许可时，节点仍可见并提示原因；Agent 通过准备工具引导，用户在软件或平台界面输入敏感内容，Agent 不读取具体内容。依赖缺失、安装失败或软件不可用应明确说明。

④提供节点定义，⑤保存当前图并核对输入及环境，协调③调用，记录实际软件版本和执行事实；软件返回不等于整条工作流成功。用户选择结果时由②登记素材。详细文件交接、取消和软件桥接按具体任务验证。

<a id="flows"></a>
## 更新与卸载

更新前列出受影响工作流和参数变化，用户确认后更新；软件正在处理时等运行结束后再允许更新。新版软件及其配套节点替换旧版，参数发生变化时采用新版默认值；新版不提供的节点保留并提示用户处理。卸载保留图中节点并提示未安装，重装后按实际兼容性使用。

这些规则只适用于软件包配套节点，不改变用户自制节点的版本设计。历史运行保留实际版本和参数记录，旧软件不承诺长期并存，也不保证更新后一定可复现旧运行。更新中对⑤当前图的具体交接见[③接口契约](../../../../docs/api/platform-contracts.md#software)，仍待实现与验证。

<a id="handoffs"></a>
## 交接与验证

| 交接 | 未来验收 |
|---|---|
| ①③⑤ | 网页和 Agent 安装同一软件包，状态与缺失原因一致 |
| ③④⑤ | 安装后的节点可见、可加入图；更新先列影响并确认，缺失节点保留 |
| ②③⑤ | 科学输入交给真实软件，记录实际运行；结果由用户选择后登记 |
| ①③⑤ | 软件运行期间不更新；停止、失败和未知按实际观察表达 |

<a id="frontend"></a>
## 前端与后端

前端展示软件列表、版本绑定命令目录、安装／更新／卸载入口、可用状态及未就绪原因；平台统一 MCP 暴露受控操作，调用共享业务能力。软件包内部方式、安装机制和认证界面留待实际适配。

<a id="verification"></a>
## 当前源码与验证位置

当前源码包括`public.py`、`routes.py`、固定下载验证和只读查询。查询读取`workspace/software/siril/state.json`中的已安装版本、路径、可用状态、最近操作、错误和包定义ID；无状态文件时不会将用户下载目录中的便携副本冒充为平台已安装。SoftwarePanel提供精简状态、安装／卸载计划与显式确认入口，但页面WS真实操作尚未由浏览器验收；命令目录尚未接入MCP。按FR-03／13和AT-02／03／25／33继续完成安装、真实软件、网页和MCP联调。

<a id="phases"></a>
## 阶段

S2 建立首个软件包安装及发现基础；S3 与④⑤联调配套节点；S4 真实处理；S5 网页与 Agent 一致；S6 扩展软件与维护。各阶段以真实验收为准，不因设计成文而宣称交付。

<a id="decisions"></a>
## 已确认决定与参考

用户确认使用统一 MCP 和可选软件包，更新时确认影响并替换配套节点。这取代历史上软件包旧版本须并存及旧图始终使用旧实现的要求；历史 ADR 保留原文。自定义节点另按[④数据设计](../../../../docs/architecture/data-models/04-nodes.md)确认更新，正在执行内容及历史运行事实保持。

### PixInsight源码参考及验证限制

以下为2026-10-26已读取的固定提交，均是外部项目源码观察；没有在本项目安装运行，也不是已经选定的依赖或性能证据。

| 项目与固定提交 | 已核对机制 | 对本项目的意义及限制 |
|---|---|---|
| [AstroPilot cb899bb](https://github.com/ncarlinix/astro-pi-mcp/tree/cb899bbf2b98146c2f105859a8f299a1bb73596a) | [后端](https://github.com/ncarlinix/astro-pi-mcp/blob/cb899bbf2b98146c2f105859a8f299a1bb73596a/src/backend/pixinsight.ts)连接用户已启动的PixInsight；[PJSR watcher](https://github.com/ncarlinix/astro-pi-mcp/blob/cb899bbf2b98146c2f105859a8f299a1bb73596a/pjsr/astropilot-watcher.js)经文件交换命令和结果 | 可参考脚本桥接；该后端不启动应用，不能由此声称平台已能自动准备会话 |
| [iftahs/pixinsight-mcp 1d06872](https://github.com/iftahs/pixinsight-mcp/tree/1d0687282e1d26dd7631c4b2dabd21f5f2e20ece) | [启动器](https://github.com/iftahs/pixinsight-mcp/blob/1d0687282e1d26dd7631c4b2dabd21f5f2e20ece/src/bridge/launcher.ts)按需启动应用并检查进程／心跳；[daemon](https://github.com/iftahs/pixinsight-mcp/blob/1d0687282e1d26dd7631c4b2dabd21f5f2e20ece/pjsr/daemon.js)处理文件任务；[取消](https://github.com/iftahs/pixinsight-mcp/blob/1d0687282e1d26dd7631c4b2dabd21f5f2e20ece/src/bridge/client.ts)区分排队移除与帧边界请求 | 可参考专用应用会话；阻塞处理、实际退出及恢复仍须验证，不直接照搬上游停止回执或清理策略 |
| [pardovot/pixinsight-mcp dc2eacb](https://github.com/pardovot/pixinsight-mcp/tree/dc2eacb6a711233806243db38226a91c1273a519) | [说明](https://github.com/pardovot/pixinsight-mcp/blob/dc2eacb6a711233806243db38226a91c1273a519/README.md)及[模块桥接](https://github.com/pardovot/pixinsight-mcp/blob/dc2eacb6a711233806243db38226a91c1273a519/module/src/BridgePoller.cpp)通过应用内原生模块轮询并调用脚本，按实例区分桥接目录 | 另一种待验证方案，增加模块安装、构建及签名维护；不把其跨平台说明或响应性声明当作本项目验收 |


以上仅是上游源码参考，不代表已选定或实现某种接入方式。[Siril命令行文档](https://siril.org/docs/man/)与[ASTAP官方文档](https://www.hnsky.org/astap.htm)可供候选适配参考，具体命令、版本和许可须在实际接入时核对。软件包格式、下载地址、具体发行方式、更新协议和物理存储留到实施设计。
