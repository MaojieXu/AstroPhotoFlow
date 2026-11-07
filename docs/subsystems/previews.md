# 预览与缓存

[English](previews.en.md) | 中文

缩略图与大图查看复用同一套派生缓存；缓存可重建，不作科学输入。实现归 data 模块的媒体与预览（`src/astrophotoflow/modules/data/media/`），模块职责见[架构](../architecture.md)。

## 缩略图

- 后台为可自动预览的图片生成最长边 100px JPEG，不阻塞导入。
- 固定组用固定版本排序第一成员的配方；独立素材各自计算，参考帧不可用时不改选。
- 网页按视口与邻近行提升取图优先级，单页最多 4 个请求，单元格在缓存键就绪后逐张替换。
- 已知失败或不支持的项停止重复取图，显式重试走批次接口；后端按批巡检丢失文件并支持重启恢复。

## 大图查看

- 复用已保存配方；缺失时只为明确参考帧计算，overview 按 512、1024 或 2048px 采样，放大瓦片按区域读取。
- `consumer_id` 与 `generation` 只用于取消当前查看请求，不写缓存、科学记录或工作流；切换时丢弃旧响应。
- 视频优先原生 HTML video 与 Range 流；不兼容编码与 SER 按需生成最长边不超过 1920px 的 H.264 代理。
- 无 FFmpeg、时间戳无法匹配或超出预算时明确报错，不自动下载工具。

## 缓存预算

- 浏览器保留 128 项 512px RGBA 瓦片，最多 128MiB；后端编码瓦片字节最多 256MiB。
- 磁盘最多 4GiB，含显示底图、瓦片、代理与帧映射，位于实际 `data_dir/previews/{version}/media/{key}/`。
- 只淘汰 previews 自有派生文件；原件与科学记录保持，生成中的所有权阻止并发永久清理。

## 状态与失败

- 状态为 `not_ready`、`generating`、`available`、`failed`、`unsupported`；生成中返回 202，否则返回当前状态。
- 失败缓存保留错误，可显式调度重试；启动把中断的 generating 标为可重试失败，退出时排空。
- X-Trans 或 Quad Bayer 未提供去马赛克时按原尺寸灰度马赛克查看，并明确说明。

## 显示配方

- 已知分类组在导入阶段用既定 MTF 与背景白平衡配方，其他来源保留百分位缩略图。
- RGB 先估背景白平衡再统一拉伸，Mono 只拉伸；配方存为预览记录，显示缓存不登记为科学素材。
- 配方按固定版本、HDU、尺寸与算法版本定位；同一版本生成中复用任务，等待旧配方的请求在其完成后补自动配方。

## 对外契约

- HTTP 路由在 `src/astrophotoflow/interfaces/http/data/previews.py` 与 `media.py`。
- 状态与请求模型在 `src/astrophotoflow/contracts/previews.py`，字段以 [OpenAPI 快照](../api/openapi.json) 为准。
- 共享作用域与项目作用域的查看地址由 `src/astrophotoflow/modules/data/media/links.py` 维护；测试在 `tests/modules/data/test_display_previews.py` 与 `test_auto_stretch.py`。
