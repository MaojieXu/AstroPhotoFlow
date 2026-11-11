---
name: astrophotoflow-backend
description: 在 AstroPhotoFlow 平台内部开发或修改 Python 后端、HTTP、MCP／CLI、原生桥接及联调时使用。按文件分类与任务路由定位责任层、公开入口、调用链和验证方式。外部 Bundle 实现不在范围内。
---

# 后端开发与联调

## 任务路由

| 当前任务 | 按需读取 |
| --- | --- |
| 判断文件归属、修改业务规则、共享类型或基础设施 | [后端导航](references/backend-map.md#文件分类与归属)对应行及该子树约定 |
| 修改 HTTP、Python 客户端、MCP／CLI 或原生桥接 | [调用链导航](references/backend-map.md#协议与调用链)，再读[契约同步](references/integration.md#契约与生成物) |
| 配置 workspace、排查端口、重载或跨进程联调 | [联调流程](references/integration.md#workspace-与运行目标) |
| 修改 ORM、初始化基线或重建测试 workspace | [数据库开发入口](references/backend-map.md#数据库开发)，数据保留规则以开发文档为准 |
| 选择测试、检查接口一致性或记录验证结果 | [验证入口](references/integration.md#验证与回执) |

本技能用于平台内部实现。平台 Bundle SDK、加载器和宿主适配从后端导航进入，Siril 等外部 Bundle 实现由其仓库维护。仅操作现有素材库时使用 [素材库技能](../astrophotoflow-library/SKILL.md)。涉及前端实现时使用 [前端技能](../astrophotoflow-frontend/SKILL.md)。

## 修改流程

1. 按任务定位责任层，读取该子树的 `AGENTS.md`、当前公开入口、代表调用者与测试。跨模块任务先核对架构中的状态归属和依赖方向。入口见[架构](../../../docs/architecture.md)。
2. 沿真实入口追踪输入校验、实际目标与参数、业务操作、持久化和返回值。已有行为满足需求时复用，行为缺口由责任层补齐，跨模块用例在既有装配层组合公开能力。
3. 模型或协议变更沿实际消费方核对省略、`null`、`0`、revision、成员顺序与错误回执，再按契约同步流程生成相关产物。字段和签名以源码及生成物为准。入口见[接口参考](../../../docs/references.md)。
4. 修改失败、取消、后台任务或跨进程回执时，按所属子系统核对失败后状态与安全继续条件，使用[错误处理技能](../astrophotoflow-error-handling/SKILL.md)。受端口、子进程、并发与清理影响的测试使用[测试可靠性技能](../astrophotoflow-test-reliability/SKILL.md)。
5. 按联调流程确认 workspace 与实际服务，选择受影响路径的最小充分验证。报告实际执行的检查、可观察结果与未验证部分。验证格式见[测试文档](../../../docs/testing.md)。

## 导航维护

只加载当前任务涉及的参考段落。新增、移动或改变已收录入口时更新对应导航与代表调用关系。入口失效时先检查仓库根是否存在 `.codegraph/`，存在则优先用 CodeGraph，否则用 `rg` 定向查找。索引保存定位与复用关系，模块规则仍由架构、局部约定和子系统文档维护。
