# ComfyUI-AstroPhotoFlow

AstroPhotoFlow 是一个基于 ComfyUI Extension 的本地天文图像处理工作台，目标是让用户和 Agent 在同一项目中组织天文素材、构建处理流程、调用外部天文软件并追溯运行结果。

## 当前状态

本仓库处于需求基线和 Extension 脚手架阶段。产品范围、架构约束与验收目标见 [`docs/AstroPhotoFlow_Requirements_v1.0`](docs/AstroPhotoFlow_Requirements_v1.0/README.md)。文档定义的是开发目标，不代表功能已经实现或验收。

本仓库保留 ComfyUI 官方 Cookiecutter Extension 模板结构，供 AstroPhotoFlow Extension 开发使用。

## 生成 Extension 项目

需要 Python 和 Cookiecutter：

```bash
python -m pip install cookiecutter
cookiecutter .
```

默认项目名为 `ComfyUI-AstroPhotoFlow`，Python 模块名为 `astrophotoflow`。运行 Cookiecutter 时可按需修改默认值。

生成后，将 Extension 项目放入 ComfyUI 安装目录的 `custom_nodes/`，然后重启 ComfyUI。集成测试宿主路径为 `/home/maojiexu/Workshop/ComfyUI`。

## 参考项目

可借鉴的上游仓库清单与许可证边界记录在需求文档的 [开源项目借鉴与许可证](docs/AstroPhotoFlow_Requirements_v1.0/06_开源项目借鉴与许可证.md) 和 [调研来源与核验记录](docs/AstroPhotoFlow_Requirements_v1.0/08_调研来源与核验记录.md) 中。参考源码应单独克隆和审阅，不要放入本仓库提交。

## License

本仓库保留上游模板的 GPL-3.0 许可与版权声明。复用或分发第三方代码时，请同时遵守其原始许可证。
