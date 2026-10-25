# AstroPhotoFlow 第二阶段资产格式与显示支持矩阵

**状态：**实现范围与测试样本说明。导入阶段只按以下扩展名选择候选文件；扩展名不证明文件内容有效。

## 格式与识别

| 类型 | 扩展名 | 导入与内容散列 | 第二阶段解析／预览 |
|---|---|---|---|
| FITS | `.fits`、`.fit`、`.fts`、`.fits.fz`、`.fit.fz` | 支持引用或复制托管，导入时计算 BLAKE3 | 保存各 HDU 描述和按顺序保留的 Header；自动选择首个支持的图像 HDU；生成 Mono、四种 Bayer 或明确 RGB 预览；X-Trans／Quad Bayer 保存 CFA 元数据，马赛克预览暂不支持 |
| 常规图像 | `.jpg`、`.jpeg`、`.png`、`.tif`、`.tiff`、`.bmp`、`.webp`、`.heic`、`.heif`、`.hif` | 支持入库并计算 BLAKE3 | 仅生成最长边 100 px 的 JPEG；高位深灰度图在同条件组内复用拉伸数值；HEIF 使用 Pillow HEIF 插件读取静态主图和方向信息，不解码 Live Photo 动态部分或 HDR 增益图 |
| 相机 RAW | `.cr2`、`.cr3`、`.nef`、`.arw`、`.dng`、`.raf`、`.orf`、`.rw2`、`.pef`、`.srw` | 支持入库并计算 BLAKE3 | rawpy／LibRaw 优先取至少 100 px 的内嵌预览，否则以半尺寸解码为 8-bit sRGB；实际机型和编码支持取决于 LibRaw |
| XISF | `.xisf` | 支持入库并计算 BLAKE3 | 读取第一幅 Gray 或 RGB 图像；Gray 必须为单通道，RGB 必须为三通道；不猜测数据通道轴；继承 FITS 的 1–99 百分位显示拉伸 |
| NumPy | `.npy`、`.npz` | 支持入库并计算 BLAKE3 | 暂不支持解析／预览、数组成员或切片 |
| 已录制视频 | `.ser`、`.mp4`、`.mov`、`.avi`、`.mkv` | 支持入库并计算 BLAKE3 | 从首个可解码帧生成最长边 100 px 的 JPEG 静态封面；SER 支持 MONO、四种 Bayer、RGB／BGR；不提供播放器或逐帧查看 |
| 其他文件 | 未列出的扩展名 | 文件夹导入时跳过并记入报告；不能从文件选择器作为受支持素材选择 | 不支持 |

格式识别清单由 `service/src/astrophotoflow_service/files.py` 的 `SUPPORTED_EXTENSIONS` 提供。浏览器文件夹选择只接收所选文件夹第一层的常规图像、FITS、RAW、XISF 和视频文件，并忽略子文件夹及其他格式；整次选择生成一个托管数据集。文件选择与文件夹选择均上传至本机资产服务，源文件不被改写。

### FITS 支持判定

- 二维图像默认作为 Mono；存在四种已知 Bayer 排列时作为 Bayer。CFA 可以来自 Header，或由用户在导入／资料表单明确填写。
- Bayer 仅接受 `RGGB`、`BGGR`、`GRBG`、`GBRG`。
- CFA 元数据另可登记 `MONO`、`XTRANS`、`QUAD_BAYER`。X-Trans 和 Quad Bayer 暂不解码或生成马赛克彩色预览，不套用 Bayer 算法；已解码 RGB 照片不受此限制。
- 厂商公开资料用于说明格式类型：[QHY 型号表](https://www.qhyccd.com/astronomical-camera-qhy533/)列出四种 Bayer 排列，[Fujifilm X-Trans](https://www.fujifilm-x.com/nl-nl/stories/x-trans-cmos-het-geheime-recept-achter-de-beeldkwaliteit-van-fujifilm/)为不同的 6×6 CFA，[Sony Quad Bayer](https://www.sony-semicon.com/en/technology/mobile/quad-bayer-coding.html)为同色 2×2 像素单元。本表登记的排列是素材文件元数据，不通过品牌型号推断。
- RGB 通道优先要求明确标记：`CTYPE3` 或 `CTYPE1` 为 `RGB`／`COLOR`，且对应轴长度为 3。按用户确认，对 47 Tucanae / Karl - result_3570s 来源中 `NAXIS3=3`、`CTYPE1` 为 RA 轴、`CTYPE2` 为 DEC 轴且无 `CTYPE3` 的 FITS，三个平面按 RGB 预览；其他未标记的三维 FITS 仍不推断为 RGB。
- 从 HDU 顺序中选择首个受支持图像 HDU。生成该 HDU 预览失败时记录失败，不回退尝试后续 HDU。
- 解析保留数值类型、形状、BITPIX、BSCALE、BZERO、BUNIT 和所有 Header 卡片；重复 COMMENT／HISTORY 按原顺序保存。若命中 `IMAGETYP`、`IMAGETYPE`、`OBSTYPE`、`FRAMETYP` 或 `FRAME`，原样保存一项 `file_classification_header` 供详情查看；它不覆盖用户当前分类，也不阻塞导入。
- Header 中的 `CCD-TEMP` 单独记录为 `sensor_temperature_setpoint_c`；不把制冷设定值写入人工可编辑的 `sensor_temperature_c` 实测字段。

### 新格式验收样本（旧版双尺寸方案的历史记录）

- 本地 `test/reports/astro-dataset-source-manifest-2026-10-24.json` 中的 11 个 XISF（Gray 与 RGB）全部进入完成态；两档预览均可读取，JPEG 的最长边分别为 100 px 和 1024 px，项目固定引用返回同一版本预览。
- RAW 验收使用 CC0 1.0 的 Canon EOS 5D Mark IV `.CR2`、Nikon Z 6 `.NEF` 与 DJI Mavic 3 Pro `.DNG` 样本；来源和 SHA-256 清单保存在忽略的 `test/workspace/preview-raw-samples/`，样本不会进入 wheel 或 sdist。前两者采用足尺寸内嵌 JPEG，DNG 的 960×720 内嵌 JPEG 改走 half-size 解码，结果为 2016×1512；另用损坏 NEF 验证内容入库成功但预览标记失败并附具体原因。
- HEIF 验收在忽略的 `test/workspace/preview-heif-sample/` 生成小型 HEIC 编码图像，并以 `.heic`、`.heif`、`.hif` 三种扩展名验证入库和两档 JPEG。该样本验证静态 HEIF 解码，不代表对任意手机机型、HDR 增益图或 Live Photo 动态部分的支持。

## 固定显示预设

| 参数 | 固定值或规则 |
|---|---|
| 派生格式 | JPEG，quality 80，`optimize=false` |
| 预览规格 | 仅 `thumbnail`，最长边 100 px；`detail` 不再生成或提供 |
| 尺寸 | 等比例缩小，不放大小图 |
| 采样 | 依据最长边计算步长，再缩放到目标上限；Bayer 使用奇数采样步长保留 CFA 相位 |
| Mono／RGB 拉伸 | 同次导入、同条件组的第一张成功预览确定有效像素第 1 与第 99 百分位黑白场；组内后续线性 FITS、XISF 和高位深灰度图复用该数值 |
| 同条件组 | 文件类型、图像布局、亮场／校准场、相机、滤镜、曝光、增益、偏移与 binning；每个导入任务独立分组，缺失值不推断 |
| Bayer 显示 | 从已确认 CFA 排列进行 5×5 邻域插值，再使用同一百分位拉伸 |
| 版本 | `auto-stretch-2`；导入任务保存分组与基准值，逐预览记录算法版本、实际黑白场、基准版本、步长和 CFA 信息 |
| 科学原件 | 只读；预览仅为派生显示文件，不写回 FITS |

FITS 预览实现位于 `service/src/astrophotoflow_service/fits_preview.py`；普通图片、XISF、RAW 与 HEIF 预览在 `service/src/astrophotoflow_service/ingestion.py` 解码。导入与 `apf-service previews backfill` 仅保存最长边 100 px 的 JPEG 小图；素材列表只展示这份小图，点击图片不打开预览。视频仍只显示 100 px 首帧。SER 按[公开 SER V3 规范](https://free-astro.org/images/5/51/SER_Doc_V3b.pdf)读取第一帧的通道平面及字节序。原始文件只读。

### 新增解码依赖与许可证

根包和服务包都锁定 `xisf 0.9.7`（GPL-3.0）、`rawpy 0.27.1`（MIT；随包的 LibRaw 可选择 LGPL-2.1 许可）和 `pillow-heif 1.1.1`（Python wrapper BSD-3-Clause）。该 `pillow-heif` Windows wheel 的 bundled-license 记录标为 GPLv2，并列出 libheif/libde265（LGPL-3.0）、x265（GPLv2）和 libaom（BSD-3-Clause）。x265 3.4 上游授权允许采用 GPL v2 或任一后续版本；依 GNU GPL 兼容性表，可选择 GPLv3 条款与本产品 GPL-3.0-or-later 组合。rawpy 0.27.1 和 pillow-heif 1.1.1 提供 CPython 3.12 Windows x64 wheel；xisf 为纯 Python sdist。具体锁定及安装结果以 service/uv.lock 和发行包验收为准。

## 合成测试样本记录

样本由测试在临时目录中生成，无第三方素材、许可或外部来源。每次运行重建样本，测试断言记录于：

| 测试样本 | 确定性内容 | 验证内容 |
|---|---|---|
| `星云 #1.fits` | 6×8 `int16` 图像；包含 EXPTIME、GAIN、RGGB 和两条重复 COMMENT；附加 3×4 ImageHDU | 中文和特殊字符路径、Header 保留与重复卡片、人工值优先、零曝光、BLAKE3、原件不变及 1024 档不放大 |
| 手动 CFA FITS | 1200×2400 `uint16` 图像，无 CFA Header；导入侧显式提供 BGGR | 识别 Bayer、100／1024 px 预览上限、不放大、固定拉伸与原件字节不变 |
| 首个 HDU 显示失败 | 首个二维 HDU 全为 NaN，第二个二维 HDU 有效 | 首个支持 HDU 固定选中；预览失败不回退到第二个 HDU |
| RGB FITS | 无图像的 PrimaryHDU 加形状为 3×20×30 的图像 HDU，`CTYPE3=RGB` | 只接受明确 RGB 轴，生成 30×20 预览 |
| 普通 PNG | 320×180 RGB 照片 | 生成 100×56 与 320×180 JPEG，原件不变；缺失缩略图回填时保留 detail 文件 |
| SER 首帧 | 合成 120×80 灰度 SER 与缺失图像数据的无效 SER | 生成两档 JPEG；坏帧仍完成内容入库；素材库／项目引用预览可读；补齐时单项失败不阻止后续素材 |
| 损坏 FITS | `.fits` 后缀、非 FITS 字节 | 内容可入库并保留散列；解析失败独立告警，选定项重试不新建 Asset |

对应测试为 `service/tests/test_ingestion.py` 和 `service/tests/test_fits_preview.py`。这些是行为测试样本，不是随产品安装的演示资产。

实际扩展映射和实现能力以该文档对应分支代码及测试结果为准；格式能力未通过对应测试时不得宣称已支持。
