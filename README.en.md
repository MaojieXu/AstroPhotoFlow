# AstroPhotoFlow

English | [中文](README.md)

AstroPhotoFlow is a local astronomy imaging workbench: it turns captured FITS data into traceable assets, connects external-software operations into processing graphs on the native canvas, and lets you inspect, compare, and save results of real executions. The platform runs two resident services (the ComfyUI web page and engine, plus the FastAPI domain service); users work directly in the web page, while external general-purpose agents operate the same data and an explicitly authorized canvas through the platform MCP.

## Quickstart

For the first development session, have Git, uv, Node.js, and pnpm available. See the [development environment](docs/development.en.md) for versions. Install dependencies, build the web assets, and open the development workbench.

```sh
git clone --branch dev https://github.com/MaojieXu/AstroPhotoFlow.git
cd AstroPhotoFlow
uv sync
pnpm -C frontend install
pnpm build
pnpm web
```

Use the same launch command for subsequent development sessions.

```sh
pnpm web
```

On the Vite page, frontend changes hot-reload on save and Python changes restart the workbench. Day-to-day source edits require no additional `pnpm build`.

## Documentation map

| I want to… | Read |
| --- | --- |
| Browse all docs and task entries | [Documentation entry](docs/README.en.md) |
| Understand product requirements and boundaries | [Product requirements](docs/product/README.en.md) |
| Locate modules, data ownership, and dependencies | [Architecture](docs/architecture.en.md) |
| Set up the environment and run local commands | [Development](docs/development.en.md) |
| Run tests and write validation receipts | [Testing](docs/testing.en.md) |
| Build and release development versions | [Release](docs/release.en.md) |
| Look up HTTP, MCP, and CLI interfaces | [References](docs/references.en.md) |
| Use the workbench | [User guide](docs/user/workbench.en.md) |
| Contribute and integrate changes | [Contributing](CONTRIBUTING.en.md) |
| Learn repository-level agent conventions | [AGENTS](AGENTS.md) |
