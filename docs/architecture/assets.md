# 当前素材与存储行为

前端文件／文件夹上传，以及现有 CLI／MCP 的单图导入，使用托管复制；源文件保持原位。服务另有受配置导入根约束的 reference／managed 导入接口。

```text
workspace/
  config.toml
  data/
    astrophotoflow.sqlite3
    objects/<version-id>/source.<extension>
    previews/
    upload-staging/
    service.token
  input/
  output/
  logs/
  context/
  comfyui-user/
  run/
```

`data` 相对 `config.toml` 解析；`input` 是 ComfyUI 输入目录，不是素材库原图目录。前端组通过数据库关系管理，不镜像成物理文件夹。

资产有稳定身份、版本和 revision；数据集成员及项目引用可以固定到版本。参数修改区分未提供、显式 null 和零值，过期 revision 拒绝覆盖。资料编辑、批量操作、筛选、排序和组内浏览维持已接受实现。

回收站提供移除、恢复、永久清理预览和确认清理。真实清理进度意味着不可逆变化；组状态只依据当前待处理成员的真实记录，不因已恢复成员的历史待清理路径缺失误判损坏。损坏照片不能假报恢复，外部 reference 原图及其他资产仍使用的共享路径受到保护。

显示仅提供最长边 100 px 的 JPEG 缩略图，点击不打开详情预览；同条件组复用既有拉伸基准，科学原件只读。

| 格式 | 当前解析／预览范围 |
|---|---|
| FITS | HDU/Header 元数据；支持的 Mono、Bayer、明确 RGB 图像缩略图 |
| 常规图像／HEIF | 静态图像缩略图，具体编码由既有解码器支持 |
| 相机 RAW | rawpy 内嵌预览或既有半尺寸解码 |
| XISF | 第一幅支持的 Gray/RGB 图像 |
| SER／已录制视频 | 首帧静态封面，视频解码依赖现有 FFmpeg |
| NumPy | 内容登记与散列，不提供数组查看／预览 |

扩展名和实际解码规则以 backend 实现、[对应测试](../development/test-matrix.md)为准；历史双尺寸预览记录保留在归档，不作为当前规格。

FITS RGB 识别兼容显式 CTYPE 通道标记、既有 RA/DEC 三平面布局，以及 `PROGRAM=PixInsight …` 且未声明 CTYPE3 的三平面导出。明确声明其他第三轴的文件、其他来源的无标记三维数据保持不支持，不仅按维度长度猜测 RGB。已识别为 RGB 时不因残留 BAYERPAT 再做去拜耳。
