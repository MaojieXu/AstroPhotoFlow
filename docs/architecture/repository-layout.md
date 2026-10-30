# 文件布局

职责和依赖只在 [架构](overview.md) 维护，功能入口只在 [源码导航](module-map.md) 维护。本页只说明目录用途。

| 目录 | 用途 |
|---|---|
| `engine/ComfyUI` | 固定上游引擎源码 |
| `frontend` | 原生前端workspace、实际依赖与唯一前端锁文件 |
| `frontend/packages/astrophotoflow-ui` | 私有业务UI包，不独立启动或发布 |
| `frontend/src/platform/astrophotoflow` | 原生宿主集成 |
| `src/astrophotoflow` | 平台Python源码；`core`、`contracts`、四个业务模块、`interfaces`及网关 |
| `src/astrophotoflow/vendor` | 随包资源、来源清单和Bundle发布目录快照 |
| `.artifacts/build/frontend`、`.artifacts/build/python` | 网页及Python构建产物 |
| `.artifacts/dist` | wheel／sdist |
| `.artifacts/verification`等 | 检查日志、报告和隔离数据，不作产品源码 |

根`package.json`只作任务入口，根不安装前端依赖。`frontend/build`是上游辅助源码，不能当产物清理。保留上游完整workspace，不在功能任务中搬迁源码根。

用户workspace与程序资源分离：素材／SQLite、原生图、`nodes`定义、`software`平台专用副本各有归属。Siril Bundle安装在`workspace/software/siril/bundle`；开发checkout可位于`.artifacts/bundles/AstroPhotoFlow-Siril`，是独立Git仓库。路径存在不表示安装、加载或运行已就绪。
