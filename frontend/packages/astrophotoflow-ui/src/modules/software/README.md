# 软件界面

`SoftwarePanel`常驻软件名称、红绿就绪点和安装／卸载入口；服务报告存在新 Bundle 版本时显示更新入口。原因通过状态点查看，准确版本／来源／位置及保留说明进入原生确认弹窗。命令资料留API，不占据常驻页面。

宿主注入原生Button／Dialog，同一原生WebSocket确认具体计划，轮询查询实际结果；UI不自行认定安装、加载或调用成功。未登录／许可未完成仍给出实际原因，敏感内容由用户输入。

通过包公开导出接入，UI不导入原生源码。软件维护规则见 [需求](../../../../../../docs/requirements/README.md)，实现入口见 [software](../../../../../../src/astrophotoflow/modules/software/README.md)，进度／验收统一见 [当前上下文](../../../../../../docs/development/current-context.md)。

软件管理及Bundle PNG预览使用core/api独立客户端和生成SDK；HTTP契约只从generated/api导出，预览固定引用、参数、取消信号与释放keepalive保持。

目录、详情和发行版本读取归`queries.ts`，以真实workspace和包／operationId隔离缓存并传递取消信号；运行状态1秒、普通状态10秒，发行版本只显式检查。`mutations.ts`维护提案和原生确认的无重试写入及原工作区失效。组件只保留版本草稿、计划打开状态与操作回执目标校验，未知受理结果先查询原操作。
