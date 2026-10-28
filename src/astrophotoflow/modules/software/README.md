# ③ 外部软件接入与环境概要设计

具体交接见[③接口契约](../../../../docs/api/platform-contracts.md#software)及[文件级详细设计](../../../../docs/api/platform-contracts.md#software-design)：清单安装、网页计划确认、准备、更新及实际调用观察。MCP请求返回待确认动作，用户在平台网页确认具体计划后才执行；操作均未实现或注册。

[数据设计](../../../../docs/architecture/data-models/03-software.md)记录已确认的软件包方向。本模块当前只有文档，软件安装、节点接入、更新和真实调用均**尚未实现**；原生运行与现有58个数据MCP工具不能作为其实现证据。

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

前端展示软件列表、安装／更新／卸载入口、可用状态及未就绪原因；平台统一 MCP 暴露受控操作，调用共享业务能力。软件包内部方式、安装机制和认证界面留待实际适配。

<a id="verification"></a>
## 当前源码与验证位置

本目录及[前端模块](../../../../frontend/packages/astrophotoflow-ui/src/modules/software)目前只有文档；[模块导航](../../../../docs/architecture/module-map.md#module-3)说明平台基础及现有测试，不能证明本模块已实现。未来按 FR-03／13 和 AT-02／03／25／33 执行真实软件、网页和 MCP 联调。

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
