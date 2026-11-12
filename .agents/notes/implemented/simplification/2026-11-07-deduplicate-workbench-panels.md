# Agent Note: 精简工作台设置与素材侧栏

Status: Implemented

## Problem

工作台设置把工作区、端口和目录放在折叠区域，路径输入宽度固定。校准库在筛选标签下重复显示标题和说明图标，并有单独的从已有校准照片建组入口。项目侧栏的通用标题在原生页头和列表内部重复出现。

## Decision

工作台设置将工作区、端口和目录作为常显分组。路径各占一行，主机和端口按面板宽度并排或堆叠。校准库直接显示素材表，移除内部标题、说明和独立建组按钮，并清除该按钮专属的草稿状态。项目列表使用原生侧栏页头，进入项目素材或图像组时显示相应的子视图标题。 [工作台设置组件](../../../../frontend/packages/astrophotoflow-ui/src/core/WorkbenchSettings.vue) · [素材与项目工作区](../../../../frontend/packages/astrophotoflow-ui/src/modules/data/workspace/WorkspacePage.vue)

## Alternatives considered

保留折叠可以缩短首次显示的设置页，但查看路径和端口多一次展开操作。保留校准库与项目内部标题可以独立标注各区块，但原生导航已表达当前页面，重复标题增加了正文占用。

## Consequences

校准库沿用素材库的筛选和结果列表。批量导入继续提供图像组入口，已有集合仍通过原有列表访问。嵌入侧栏的项目列表有一个通用标题，独立工作区仍有自身的标题。设置控件继续走原有保存、重读和重启入口。
