# @astrophotoflow/ui

私有workspace业务UI包，通过 [src/index.ts](src/index.ts) 公开导出，由原生网页编译；不独立运行或发布。实际导出包括素材Workspace、工作台配置、软件面板及节点／预览客户端，完整清单以代码为准。

`src/core`保存实际共用HTTP／错误和工作台配置；业务在`src/modules/data`、`software`、`nodes`、`workflows`。原生组件通过宿主注入，本包不导入原生Store、画布单例或`frontend/src`。

测试在`tests`，使用独立jsdom环境；测试、类型检查等命令见 [开发流程](../../../docs/development/README.md)，运行按用户当前要求。模块职责见 [架构](../../../docs/architecture/overview.md)，实现及验收见 [当前上下文](../../../docs/development/current-context.md)。
