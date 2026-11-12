# Agent Note: 上传登记前冻结预设

Status: Implemented

## Problem

上传任务登记和后续处理之间可能遇到预设改动。

## Decision

在登记任务成员前固定上传使用的预设。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

后续阶段读取快照，避免重读已变动的设置。

依据见 [提交 7a8dd439](https://github.com/MaojieXu/AstroPhotoFlow/commit/7a8dd439eb4a7db49e6921744e551be96ba23ced)、[提交 9df88132](https://github.com/MaojieXu/AstroPhotoFlow/commit/9df881326d14a567b4bb9e179c7b9e44c5d39e0b)。
