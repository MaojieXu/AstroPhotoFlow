# Agent Note: 用捕获资料投影计算数据集诊断

Status: Implemented

## Problem

项目数据集列表生成拍摄参数诊断时加载完整素材 ORM 对象。现有回归用例在读取同一个数据集引用时观测到 Asset 加载。

## Decision

用单次查询读取诊断使用的列，并将查询行交给已有的拍摄资料比较逻辑。以相同的项目数据集读取路径和 ORM 加载事件作为验证口径。

## Alternatives considered

在列表中省略诊断会改变响应内容。缓存诊断需要维护额外的失效边界。

## Consequences

项目引用仍返回当前成员及拍摄差异。查询只物化诊断所用列；验证记录的是 ORM 加载事件。
