# 前端公共基础

`WorkbenchSettings.vue`展示保存值、实际采用值及显式重启；`client.ts`／`contracts.ts`保存配置客户端与实际共用HTTP／错误类型。业务DTO留所属模块，data客户端复用同一实现。

保存不自动重启，未保存内容不用于重启；断连只查询已有请求。隐藏的`import_roots`在整组保存中保留。跨端口自动重连尚不支持，实际地址从回执／status查询。

不创建第二个Vue应用或Pinia容器，不导入业务模块或原生Store。公共能力只在真实复用时提取；宿主组件和设置挂载在 [原生桥接](../../../../src/platform/astrophotoflow)。配置规则见 [需求](../../../../../docs/requirements/README.md)，状态统一见 [当前上下文](../../../../../docs/development/current-context.md)。
