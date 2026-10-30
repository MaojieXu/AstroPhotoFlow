# 软件界面

`SoftwarePanel`常驻软件名称、红绿就绪点和安装／卸载入口；原因通过状态点查看，准确版本／来源／位置及保留说明进入原生确认弹窗。命令资料留API，不占据常驻页面。

宿主注入原生Button／Dialog，同一原生WebSocket确认具体计划，轮询查询实际结果；UI不自行认定安装、加载或调用成功。未登录／许可未完成仍给出实际原因，敏感内容由用户输入。

通过包公开导出接入，UI不导入原生源码。软件维护规则见 [需求](../../../../../../docs/requirements/README.md)，实现入口见 [software](../../../../../../src/astrophotoflow/modules/software/README.md)，进度／验收统一见 [当前上下文](../../../../../../docs/development/current-context.md)。
