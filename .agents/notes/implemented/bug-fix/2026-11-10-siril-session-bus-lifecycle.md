# Agent Note: Siril 无头调用的会话总线生命周期

Status: Implemented

## Problem

安装路径验证副本来自 Git 提交，没有包含开发目录尚未提交的 D-Bus 禁用配置。真实自动拉伸已经保存 FITS 并以退出码 0 结束，自动启动的 gdbus.exe _win32_run_session_bus 仍存活，整棵调用进程树无法确认停止，调用保留 unknown，后续调用被 SOFTWARE_BUSY 阻止。浏览器测试另行注入相同环境变量，掩盖了 Bundle 本身缺少配置的问题。

## Decision

复用 Siril 开发源码已有的 DBUS_SESSION_BUS_ADDRESS=disabled: 配置，给 Bundle 增加计划环境回归断言，并从浏览器测试移除额外环境变量注入。测试准备副本时包含被验证的工作目录配置。当前工作台改为显式绑定项目 Siril 开发源码，更新网页和服务。

原生桥接以不同异常类型传递软件占用阻止和调用状态未知，结果卡按机器身份显示对应状态，并移除这两种状态下的自动重试入口。进程树检查规则保留。旧调用按原调用 ID 通过取消接口请求清理，查询确认 active=false，原有结果文件保留，历史 unknown 不改写为成功。

## Alternatives considered

忽略存活子进程会破坏任务停止与输出就绪的边界。测试单独设置环境变量只能证明测试环境能够运行，无法证明实际 Bundle 已包含修复。按错误文字匹配前端状态会依赖语言和文案。

## Consequences

独立合成 FITS 验证中，两次真实 Siril 自动拉伸均 completed，第三次在进程启动后取消得到 cancelled；三次最终 active=false 且无软件占用，原始合成文件哈希保持一致。当前用户工作台保留素材、工作流和历史回执，安装分发仍需包含开发源码中的配置变更。
