# Agent Note: 跨导入 API 验证预设快照

Status: Implemented

## Problem

独立分支的上传预设修复可能在接口合并后丢失。

## Decision

用合并后的导入 API 验证固定预设行为。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

验证覆盖合并接口，不能替代真实采集场景。

依据见 [提交 eaf936b8](https://github.com/MaojieXu/AstroPhotoFlow/commit/eaf936b88dc047308a95a268a9d23f23a4357658)、[提交 7a8dd439](https://github.com/MaojieXu/AstroPhotoFlow/commit/7a8dd439eb4a7db49e6921744e551be96ba23ced)。
