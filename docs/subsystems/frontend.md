# 前端

[English](frontend.en.md) | 中文

原生 ComfyUI 网页承载界面，平台界面分为私有 UI 包与原生桥接两层。模块划分见[架构](../architecture.md)，界面操作见[使用说明](../user/workbench.md)。

## 私有 UI 包

- `frontend/packages/astrophotoflow-ui` 通过 `src/index.ts` 导出素材 Workspace、工作台配置、软件面板与节点/预览客户端；由原生网页编译，不独立运行或发布。
- `src/core` 提供共用 HTTP 与错误处理、查询缓存与工作台配置，业务在 `src/modules/data`、`nodes` 与 `software`。
- 本包不导入原生 Store、画布单例或 `frontend/src`；原生组件由宿主注入，完整导出清单以代码为准。

## 原生桥接

- `frontend/src/platform/astrophotoflow` 安装查询插件、注入翻译函数，并把业务控件接入侧栏与画布；保留常驻画布、侧栏顺序与未保存编辑保护。
- 数据引用使用一次原生撤销事务；运行回执按实际 Data 与来源连线核对；导出只写副本。
- 原生 Store、画布与转换协调在本目录，UI 包不反向依赖。

本地网页使用 AstroPhotoFlow 的菜单、启动与安装标志，以及项目文档和反馈入口。菜单、快捷键与设置隐藏上游账户、生成模板和模型管理入口。节点目录展示运行时注册的节点。

## 画布节点

- Data 从素材库共用的系统文件选择入口取得单个文件路径并导入，手动路径输入折叠；取消、失败或节点被替换时保留已有绑定。单张名称只在标题显示，集合保留当前成员名称，完整资料在详情中查看。
- 节点预览按内容适配高度，单张隐藏翻页。保存到素材库与导出到本机继续使用已检查的完整数据；预览分辨率与通道只改变显示。
- 软件结果卡使用原生通道下拉框，日志和完整文件下载收入更多菜单。重置按钮恢复实例定义的全部参数，包含高级参数，以一次原生撤销事务提交；自动模式合并提交一次，手动模式等待运行。
- 原生控件在撤销重建同 ID 节点后重新解析实例归属，自动浮点精度能够表示声明默认值，恢复默认值不受编辑回调舍入影响。

## 语言资源

- 网页只发布 English 与简体中文：`frontend/src/locales/localeConfig.ts` 的 `localeDefinitions` 决定可用语言，其他语言的目录不上线。
- 原生文案在 `frontend/src/locales/{en,zh}` 的 `main`、`settings`、`commands` 与 `nodeDefs` 目录；业务文案由 `@astrophotoflow/ui` 的 `uiMessages` 合并进同一 vue-i18n 实例。
- 语言存为 workspace 设置的 `Comfy.Locale`，网页切换即时生效；领域错误由服务按同一语言渲染，Bundle 文案按 Bundle 语言边界单独处理。
- 新增或修改文案必须同时提交英文与中文；`tests/core/test_frontend_locale_coverage.py` 校验两侧键集一致，后端错误目录由 `tests/core/test_error_localization_coverage.py` 校验。
- 自动翻译入口是 `pnpm locale`（需要 `OPENAI_API_KEY`），离线检查用 `pnpm locale:check`；合入以守卫测试为准。

## 查询与轮询

- 共用应用级 Vue Query 客户端，查询键含 workspace 身份；默认不重试，允许断开互联网，关闭聚焦刷新。
- 可见任务每 10 秒发现跨入口任务；活动任务每 1.5 秒读取，结束后恢复目录频率并按 workspace 失效任务查询。
- 导入任务的服务数据归查询缓存，测试挂载使用同一插件。

## 失败方式

- 手动内容变化使旧请求失效；切图暂停后续写与提交，迟到结果不抢视图。
- 查看与缩放不改变内容标记；显示状态不序列化。
- UI 不直接操作数据库、不复制领域规则，未知结果交所属模块查询。

## 对外契约

- 公开入口是包导出与原生桥接；后端契约以实际路由与 Pydantic 模型为准，字段见 [OpenAPI 快照](../api/openapi.json)。
- 生成的前端 SDK 位于 `frontend/packages/astrophotoflow-ui/src/generated/api`，不手改。
- 测试使用 `pnpm test` 与 `pnpm typecheck`。

## 边界

- 工作流编辑、队列、执行历史与画布能力归 ComfyUI；领域规则归所属模块。
