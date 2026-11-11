# Agent Note: 对齐原生外壳与前端契约

Status: Implemented

## Problem

网页切换到原生宿主后，部分外壳行为与组件契约不匹配。

## Decision

修正宿主外壳与前端控件的对接。

## Alternatives considered

现存材料未记载该项决定曾比较的其他方案。

## Consequences

原生网页沿用前端约定的输入和行为。

依据见 [提交 0dc78f74](https://github.com/MaojieXu/AstroPhotoFlow/commit/0dc78f74c29d960a824daf121b90af092987cedb)。
