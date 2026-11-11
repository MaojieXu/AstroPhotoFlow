# Agent Note: 在 workspace 绑定开发版 Bundle 源码

Status: Implemented

## Problem

开发适配器需要验证未发行源码和生成内容。

## Decision

增加显式 workspace 源码绑定，采用可核对的准备与生成结果。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

只影响选择的 workspace，已安装包和正式发布范围分别管理。

依据见 [提交 c1392711](https://github.com/MaojieXu/AstroPhotoFlow/commit/c139271125f49584313ef883c7250062e14cc85e)、[提交 bbb6f4a9](https://github.com/MaojieXu/AstroPhotoFlow/commit/bbb6f4a9f872fc1b79defa6dddf849247b5099d6)。
