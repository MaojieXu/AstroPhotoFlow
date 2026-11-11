# AstroPhotoFlow

English | [中文](README.md)

AstroPhotoFlow is a local astronomy imaging workbench: it turns captured FITS data into traceable assets, connects external-software operations into processing graphs on the native canvas, and lets you inspect, compare, and save results of real executions. The platform runs two resident services (the ComfyUI web page and engine, plus the FastAPI domain service); users work directly in the web page, while external general-purpose agents operate the same data and an explicitly authorized canvas through the platform MCP.

## Quickstart

Have Git, uv, Node.js, and pnpm available. See the [development environment](docs/development.en.md) for versions. Install dependencies in a single checkout.

```sh
git clone --branch dev --depth 1 https://github.com/MaojieXu/AstroPhotoFlow.git
cd AstroPhotoFlow
uv sync --locked --extra dev
pnpm --dir frontend install --frozen-lockfile --ignore-scripts
```

To open the workbench for the first time, build the web assets, initialize the development workspace, then start the services.

```sh
pnpm build
uv run --locked --no-sync apf init --workspace .artifacts/workspaces/dev --frontend-assets .artifacts/build/frontend --no-activate
uv run --locked --no-sync apf start --workspace .artifacts/workspaces/dev
```

Once the workbench is ready, `start` shows the actual web address in interactive terminals. Add `--open` to launch the default browser. Scripts can still read `web_url` from the JSON on standard output. To update the workbench web assets, stop that instance before building and initializing again.

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
