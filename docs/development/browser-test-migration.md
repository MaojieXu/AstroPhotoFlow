# G7 浏览器测试收尾

2026-11-01复核发现：新Playwright场景通过，但旧手动启动脚本及默认入口仍保留，前次G7完成判断过早。本轮在原有未提交候选上完成入口迁移和断言对账，不提交、合并或发布。执行结果写入[本轮验证记录](test-matrix.md#modernization-g7-browser-closure)，本页只维护去向和运行规则。

根`pnpm test:browser`调用[Playwright配置](../../tests/browser/playwright.config.mjs)，浏览器／页面／上下文由Test fixture管理，统一trace、截图、报告、单worker和零自动重试。环境变量与实际隔离路径验证见[开发流程](README.md#验证入口)。

| 旧来源及有效断言 | 当前场景／fixture |
|---|---|
| native-web：默认原生路由、侧栏顺序／宽度、画布位置、关闭重开／刷新、代理鉴权、不泄漏Authorization、请求标识 | `native-web.spec.ts`侧栏／代理测试；新数据库期望改为0001_baseline，不保留旧0009修订号 |
| native-web：项目GUI创建、拒绝／接受丢弃草稿、切换侧栏后原生节点与视口不变 | `native-web.spec.ts`项目／草稿测试；使用专属双节点／连线和非默认视口，结束归档自己的项目并恢复原图 |
| native-web：原生LoadImage→SaveImage、图文件保存／读取、queuePrompt及历史成功 | `native-web.spec.ts`原生图片队列测试；APF_ALLOW_NATIVE_QUEUE显式启用，只使用唯一命名的测试输入／输出，不经自研workflow API |
| native-web：上传、缩略图、完整查看器、回收站恢复、原件字节与刷新后可见 | `native-web.spec.ts`二进制上传／查看／恢复测试；复用`scientificAssets.ts:uploadAssetBytes`的真实上传接口。旧“上传文件”浏览器控件已被本机选择器替代，不恢复旧UI、不自动打开系统文件窗口；本场景不声称验证真实OS选择窗口 |
| m2-layout：1280／900像素，素材与设备区域同左边界／同宽度、设备组合／我的设备切换及左对齐 | `native-layout.spec.ts`两个独立场景，截图作为Test附件 |
| platform-workflows：工作台在原生设置内、目录／端口输入可见、无横向溢出、loopback校验、隐藏设置不出现在搜索、语言设置可用、关闭仍保留原生画布 | `workbench-settings.spec.ts`原生设置测试；高级字段先展开，开发选项通过搜索定位，遵循当前界面；Comfy.DevMode在当前settingsPresentation.ts及有效需求的本地精简规则下隐藏，旧正向断言改为搜索中不可见，不恢复已隐藏功能 |
| platform-workflows：保存不立即改变采用值、第二页面409保留草稿、真实重启采用保存值／重新连接、网页地址链接 | `workbench-settings.spec.ts`配置冲突／重启测试；APF_ALLOW_WORKBENCH_RESTART显式启用，验证空队列及无既有待采用配置，结束恢复本轮改变的并发值。未知重启先查询，不盲目重发 |
| 三脚本的页面错误、禁止外网、受控workspace、浏览器释放 | `native.fixtures.ts`；实际health／config必须匹配APF_TEST_WORKSPACE，拒绝dev／default；错误／外网请求检查及fixture销毁 |

旧`native-web.mjs`、`platform-workflows.mjs`、`m2-layout.mjs`已删除，不保留可执行兼容入口。删除前源码只在本机`.artifacts/reports/modernization/g7/legacy-browser-before/`保存审计副本，不属于测试发现或产品源码。

既有现代化素材／原生专项仍通过各自配置执行，根入口分别为`test:browser:modernization`和`test:browser:native`。它们的旧验证证据保留；16条环境型skip与专项显式运行结果分别统计。
