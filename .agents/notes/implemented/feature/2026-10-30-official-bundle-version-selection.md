# Agent Note: 发现并确认官方 Bundle 固定版本

Status: Implemented

## Problem

用户需要可核对地安装、升级或回退包版本。

## Decision

从官方来源发现合格标签，确认绑定具体 tag、提交与 manifest，网页展示安装计划。

## Alternatives considered

历史实验标签与当前正式发现范围分开。

## Consequences

选择令牌验证实际目标，语言及 latest 标记不构成包身份。

依据见 [提交 1e47a035](https://github.com/MaojieXu/AstroPhotoFlow/commit/1e47a035d42564034985aa9f480015e2e108f35b)、[提交 0b8fb710](https://github.com/MaojieXu/AstroPhotoFlow/commit/0b8fb7109475ee0ce545e7f1c1ec4b1db5d9932c)、[提交 711bd850](https://github.com/MaojieXu/AstroPhotoFlow/commit/711bd850b122ca64e1f147c645ba6fc0015c42ab)。
