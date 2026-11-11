# Agent Note: 明确文件归属并解除平台的 Siril 特例

Status: Implemented

## Problem

源码、生成物、安装副本和缓存易被混用，平台仍有 Siril 专属处理。

## Decision

核对文件读写归属，平台保留通用 SDK 与目录，Siril 适配和运行资源留在独立 Bundle。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

平台发行不夹带独立软件实现。集成检查覆盖非 Siril 元数据保真，未发布新的 Siril tag。

依据见 [提交 9c2f7f24](https://github.com/MaojieXu/AstroPhotoFlow/commit/9c2f7f244febdd99bd957a40d6013b90b59f72fd)、[提交 3b43b043](https://github.com/MaojieXu/AstroPhotoFlow/commit/3b43b0430368b7433d00f55c3b7bdd4f8bcebf1e)、[提交 56c376ed](https://github.com/MaojieXu/AstroPhotoFlow/commit/56c376ed2ca784a18acbbd2e8ba39a778533f8a7)、[repository-layout.md](https://github.com/MaojieXu/AstroPhotoFlow/blob/a3857c745b63d830800dfe49362a39480fe69788/docs/architecture/repository-layout.md)。
