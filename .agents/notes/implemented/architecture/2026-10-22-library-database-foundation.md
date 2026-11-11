# Agent Note: 建立素材库数据库与迁移基础

Status: Implemented

## Problem

素材、分组和元数据需要可持久查询并具备可升级的存储结构。

## Decision

第一阶段引入领域服务数据库、Alembic 迁移和素材管理基础，实现与扩展前端协作。

## Alternatives considered

初版规划把领域记录交给服务保存，画布保有编辑状态。

## Consequences

后续搜索、导入恢复及版本管理建立在数据库基础上。

依据见 [提交 ce8404e7](https://github.com/MaojieXu/AstroPhotoFlow/commit/ce8404e7b2bb177af739fd005df83a98a406d169)。
