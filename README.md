# ComfyUI-AstroPhotoFlow

AstroPhotoFlow 是一个基于 ComfyUI Extension 的本地天文图像处理工作台，目标是让用户和 Agent 在同一项目中组织天文素材、构建处理流程、调用外部天文软件并追溯运行结果。

## 当前状态

本仓库包含可直接接入 ComfyUI 的 AstroPhotoFlow Extension 最小测试，以及供后续开发使用的官方 Cookiecutter Extension 模板。当前侧栏测试只显示天文页签和静态文字。

产品范围、架构约束与验收目标见 [`docs/AstroPhotoFlow_Requirements_v1.0`](docs/AstroPhotoFlow_Requirements_v1.0/README.md)，开发顺序见 [`docs/开发计划.md`](docs/开发计划.md)。

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

## 前端侧栏通过性测试

当前 Extension 会在 ComfyUI 左侧栏注册“天文”按钮。前端使用 Vue 3、TypeScript、Vite 和 Tailwind CSS 4，构建产物写入 Extension 的 `web/`，由根目录 Python 入口的 `WEB_DIRECTORY` 加载。

固定工具版本为 Vue 3.5.44、TypeScript 6.0.3、Vite 8.3.5、Vue 插件 6.0.10、Tailwind CSS 及其 Vite 插件 4.3.2、vue-tsc 3.3.11、pnpm 11.13.1。字体和颜色继承宿主，扩展只生成布局工具类，不加载全局 CSS reset 或定义宿主主题变量。

在 WSL 中使用已安装的 Node 22.22.2 安装依赖、检查类型并构建：

```bash
cd /home/maojiexu/Workshop/ComfyUI-AstroPhotoFlow
export PATH="/home/maojiexu/.nvm/versions/node/v22.22.2/bin:$PATH"
npm exec --yes --package=pnpm@11.13.1 -- pnpm install --dir "$PWD/frontend" --frozen-lockfile
npm exec --yes --package=pnpm@11.13.1 -- pnpm --dir "$PWD/frontend" typecheck
npm exec --yes --package=pnpm@11.13.1 -- pnpm --dir "$PWD/frontend" build
bash scripts/link-comfyui.sh
```

链接脚本仅创建 `/home/maojiexu/Workshop/ComfyUI/custom_nodes/ComfyUI-AstroPhotoFlow` 软链接。目标已存在（包括悬空链接）时明确失败，保留原目录；已经完成链接的环境不需要再次执行。

使用已安装的 uv 为宿主建立独立 Python 3.12 环境并安装 CPU 依赖。以下环境创建命令用于首次准备；已有 `.venv` 时直接使用现有环境：

```bash
cd /home/maojiexu/Workshop/ComfyUI
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python --torch-backend cpu -r requirements.txt
.venv/bin/python -c 'from importlib.metadata import version; assert version("comfyui-frontend-package") == "1.57.1"'
.venv/bin/python main.py --cpu --listen 127.0.0.1 --port 8188
```

首次接入或修改 Python 入口后重启 ComfyUI，再访问 [本机 ComfyUI](http://127.0.0.1:8188/)。点击星形“天文”按钮，提示文字为 `AstroPhotoFlow`，面板显示 `这里astrophotoflow.`。

后续修改 `frontend/src/` 后重新执行 `build` 并刷新页面；开发时也可使用持续构建：

```bash
cd /home/maojiexu/Workshop/ComfyUI-AstroPhotoFlow
export PATH="/home/maojiexu/.nvm/versions/node/v22.22.2/bin:$PATH"
npm exec --yes --package=pnpm@11.13.1 -- pnpm --dir "$PWD/frontend" build:watch
```

浏览器加载构建产物，因此持续构建完成后仍需刷新页面。`web/` 和依赖目录不提交，前端锁文件随源码提交。当前 Python 入口没有业务节点或额外业务依赖。

验收步骤和截图见 [前端侧栏验收记录](test-results/astrophotoflow-sidebar.md)。
