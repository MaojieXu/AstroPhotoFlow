# 原生网页版本

日期：2026-10-25。实施分支 `branch/redesign`；起点为 dev b6759ab 及当时未提交的单图自动拉伸改动。旧 Extension 方案由本页记录的新决策替代；冻结需求原文保留。

运行实现候选为 `0dc78f74c29d960a824daf121b90af092987cedb`，构建 manifest 记录该提交。后续交付文档不改变运行代码。[前端架构决策](../../frontend/docs/adr/WORKBENCH-NAV-0044-native-pages-and-graph-location.md)记录页面、图定位及服务分层的取舍。

## 架构与来源

采用天文专用多页面工作台，默认进入素材库，另有工作流与设置。原生 Vue 应用直接编译已有业务组件，共用 Vue/Pinia；画布首次访问初始化，之后保持挂载，切页保留节点、草稿及视口。

ComfyUI 引擎固定0.42.0，提交 `1a82e6d01f395b43275c77acd289af1eb7090bb9`；前端固定1.57.1，提交 `c875ee420aa027a359b2953361eb3b356b7bef00`。完整源码分别位于 engine/ComfyUI 与 frontend。来源、原始及定制归档散列见 vendor 清单，上游许可保留。

原生引擎启动直接注册同源业务网关。FastAPI 保留为内部领域服务，工作台统一管理两个进程。旧 custom_nodes 插件安装、侧栏应用挂载和插件服务管理器已退役。CLI/MCP 使用同一领域 API，58个工具及业务契约保持。

## 路由、主题与数据

- 页面使用 `#/library`、`#/workflows`、`#/settings`。ComfyUI 原有子图定位改存 `graph` 查询参数，顶级导航保留该参数，避免覆盖页面 hash 或切页重置视口。
- 首页使用同一主题服务初始化颜色，加载已保存语言或浏览器语言；不必先打开画布。
- 网页 `/astrophotoflow/api/v1` 与内部 `/api/v1` 保持，令牌仅由网关在服务端添加；路径白名单、来源、流式上传和错误 request ID 规则保留。
- schema仍为0009，不增加业务迁移，不清库、不重新导入原件。设备快照、固定版本、校准关联、回收站保护和自动预览配方保持。
- 新运行目录 native-web-0.1.0 与旧CPU runtime分离。工作台默认禁用外部Custom Nodes和API节点，直接提供完整网页资源。
- 原生停止使用认证的内部关闭入口排空领域任务；既有旧工作区仍沿用原停止方式。迁移已有工作区时先停止旧实例，再初始化原生网页资源并启动。

## 构建与复现

Node `>=26.8.2 <27`、pnpm11.13.1，Python3.12。安装根业务测试依赖和 frontend 的锁定依赖后执行 `pnpm build`。`scripts/build_engine.py` 从受版本管理的源码生成确定性归档；前端输出完整 HTML、JS分块、CSS与静态资源。

发行包携带完整网页、定制引擎、迁移资源和许可证；sdist可以在没有Node的环境重建wheel。标准命令见[开发流程](README.md)与[工作台使用](workbench.md)。

本轮隔离实例为 `.artifacts/workspaces/redesign`，网页32388、领域服务32390；不激活默认workspace。测试使用合成PNG，原有dev实例、数据、配置与全局MCP注册保留。

## 已取得的验证

| 范围 | 证据 |
|---|---|
| Python产品回归 | 最终281 passed / 1 skipped；报告 `.artifacts/redesign/python-final.xml` |
| 既有前端组件 | 143 passed；报告 `.artifacts/redesign/frontend.xml` |
| 子图定位与视口 | 最终60 passed，保留原行为断言并迁移为graph查询参数；navigation-final.log |
| 原生类型检查、生产构建与定向lint | 通过；frontend-final-build.log、native-lint.log、native-eslint.log |
| 浏览器端到端 | 5组场景通过，无页面异常或外部网络请求；`.artifacts/reports/native-web/results.json` |
| 工作台与发行布局定向回归 | 13 passed，含旧工作区停止与原生任务排空；native-lifecycle.xml |
| CLI/MCP/网页一致性与真实重启 | 58工具、同一资产ID集合、停止后端口释放、重启保留身份、默认workspace指针不变；runtime-verification.json |
| 网页资源与令牌边界 | 完整682文件与构建一致，入口资源HTTP逐字节一致，网页无内部令牌；runtime-verification.json |
| wheel源码目录外安装 | 通过；`.artifacts/reports/packaging.json` |
| sdist无Node重建与重装 | 通过，PATH中node不可用，重建wheel重新安装检查通过；packaging.json |

浏览器实际验证默认页面和网关、项目创建、取消离开时保留草稿、画布与视口跨页保留、工作流保存加载、一次真实CPU执行、浏览器上传、缩略图、自动大图、回收站恢复和刷新。原件为96×64合成PNG，未导入整套真实素材；普通引擎执行不代表已实现天文软件处理或完整来源追溯。

唯一跳过项为本机不可用的FFmpeg视频用例；已有SQLAlchemy循环外键排序warning保留。首轮实际运行环境为Windows/Python3.12/CPU；未执行的平台不视为验收通过。

发行脚本完整执行通过。最终wheel SHA256为 `c2946600bbe45a030bfae37b0175ccec3c1522b809b05d05ba0924a4674f8adc`；sdist重建wheel为 `b9baa07be4d65adb39a487373bb9599a463c67b301bbe76fbdc3cad1536e3219`。两份wheel的完整网页资源均通过目录与字节一致性检查；容器元数据与时间信息不要求散列相同。

定制引擎归档与固定上游的文件集合一致，唯一内容变化为server.py内置注册业务网关。冻结需求文件未修改。原始0.1.0 CPU依赖被只读复用于独立原生运行目录，未覆盖旧引擎源码。

完整Agent、天文软件适配、项目托管工作流、结果比较和项目记忆仍属于后续范围。
