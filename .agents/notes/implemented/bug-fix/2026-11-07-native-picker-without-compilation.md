# Agent Note: 直接调用 Windows 文件选择器

Status: Implemented

## Problem

素材导入依赖 PowerShell 临时编译 Windows 对话框辅助代码。当前预览的 Windows 会话在编译时拒绝访问，选择请求返回 503。直接打开原生对话框时，把它挂到另一进程的前台窗口也曾返回 `E_FAIL`。

## Decision

在短生命周期的 Python 子进程中用标准库 ctypes 调用 Windows Common Item Dialog。沿用支持的文件过滤、文件夹和保存模式，并按请求取消关闭自己的子进程。仅当有宿主的对话框返回 `E_FAIL` 时，用同一对话框尝试不绑定宿主。

## Alternatives considered

将编译临时目录移到仓库内仍需要当前会话缺少的编译权限。浏览器上传会引入另一条存储和导入路径。

## Consequences

独立浏览器预览已弹出 Windows 文件选择窗口，从网页取消后关闭窗口。导入与导出共用现有本机选择协议。
