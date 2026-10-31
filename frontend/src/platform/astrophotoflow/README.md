# 原生应用桥接

本目录可使用原生Store、组件、画布及生命周期，通过`@astrophotoflow/ui`公开入口消费业务UI；UI包不得反向依赖这里。领域数据和业务规则留所属模块，不直接操作数据库。

| 集成点 | 入口与责任 |
|---|---|
| 工作台挂载 | `NativeShell`、`LibrarySidebarTab`保留原生画布、侧栏与主题，注入业务控件 |
| 素材放置 | `LibraryCanvasSource`复用原生点击放置／拖拽／预览；`canvasDataBridge`写固定引用，使用一次原生撤销事务 |
| 素材节点显示 | `dataReferenceDisplay`、`CanvasDataWidget`通过原生widget生命周期显示图片、成员与资料；reference仍是科学引用，显示状态不序列化 |
| 在线图与编辑 | `useCanvasDataSession`及`canvasNodeBridge`承接实际页面、局部图操作、内容标记与当前回执；按用户指令直接编辑，核对明确目标，不复制服务端当前图 |
| 软件目录／预览 | `bundleCatalog`连接同一节点目录；`sirilPreviewDisplay`／`SirilPreviewWidget`只做显示样本预览，不提交科学运行或接管Agent |
| 自动结果计算 | `useAutomaticResults`按500毫秒合并语义变化，复用原生队列与显式目标，使用草稿计算快照；`BundleResultWidget`展示原工作流、对应签名的完整结果，旧结果保留并标记待更新 |
| 共用查看器 | `MediaViewer`／`mediaViewport`处理概览、瓦片、视频与暂停源帧；通过公开Media客户端消费，不把查看状态写图 |
| 设置与关于 | `settingsPresentation`维护本地可见性，工作台配置在原生设置内；真实平台版本从构建读取 |

保留节点库→素材库→工作流→软件包顺序、常驻画布、侧栏关闭保护和设备入口。手动内容变化使旧请求失效，查看／缩放不改变内容标记；切图暂停后续写／提交，迟到结果不抢视图。

完整保存后运行、项目图关联及运行持久记录仍须后续实现／联调；实际状态只维护在 [当前上下文](../../../../docs/development/current-context.md)，规则见 [需求](../../../../docs/requirements/README.md)。不从某个桥接文件存在推定完整闭环。
