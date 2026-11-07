# 子系统

[English](README.en.md) | 中文

各页写单个子系统的行为、输入输出、失败方式与对外契约；模块划分、数据归属与依赖方向见[架构](../architecture.md)，产品规则见[产品需求](../product/README.md)。

## 索引

| 子系统 | 负责 |
| --- | --- |
| [导入流水线](import-pipeline.md) | 登记、内容托管、元数据与预览的阶段编排和任务报告 |
| [素材库](library.md) | 素材与集合的固定版本、设备快照、校准关系、结果保存与回收站 |
| [预览](previews.md) | 缩略图、显示配方、瓦片查看与派生缓存 |
| [外部软件](software.md) | 软件包目录、安装与就绪、实际调用和停止观察 |
| [节点](nodes.md) | workspace 节点定义、更新差异与派生节点目录 |
| [画布 Agent](canvas-agent.md) | 外部代理观察并修改当前原生画布 |
| [工作台](workbench.md) | 配置、workspace 目录、进程控制与维护 |
| [前端](frontend.md) | 私有 UI 包与原生桥接 |
| [ComfyUI](comfyui.md) | 固定引擎、受管启动与同源网关 |

## 约定

- 每页只写该子系统的行为与契约，不重复架构或产品内容。
- 接口字段以实际路由与 Pydantic 模型为准，生成物位置见[参考](../references.md)。
- 面向使用者的操作说明见[使用说明](../user/workbench.md)。
