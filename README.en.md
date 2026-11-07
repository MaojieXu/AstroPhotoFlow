# AstroPhotoFlow

English | [中文](README.md)

AstroPhotoFlow is a local astronomy imaging workbench: it turns captured FITS data into traceable assets, connects external-software operations into processing graphs on the native canvas, and lets you inspect, compare, and save results of real executions. The platform runs two resident services (the ComfyUI web page and engine, plus the FastAPI domain service); users work directly in the web page, while external general-purpose agents operate the same data and an explicitly authorized canvas through the platform MCP.

## Quickstart

Requires Windows x64, Git, and PowerShell. The entry point reuses compatible local tools from PATH; when a tool is missing it downloads a pinned archive into the project's `.artifacts` and verifies it, without changing the global PATH, Python registrations, or the default workspace.

```powershell
git clone --branch dev --depth 1 https://github.com/MaojieXu/AstroPhotoFlow.git
cd AstroPhotoFlow
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 --workspace .artifacts/workspaces/dev --build --start
```

The first run installs dependencies and builds the frontend; when it finishes, open the workbench at the actual address written to the receipt. A later run from the same source point can omit `--build` and reuse the existing output.

Frontend hot reload uses the same entry point:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 --watch --workspace .artifacts/workspaces/dev --port 32589 --strictPort
```

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
| Contribute and open pull requests | [Contributing](CONTRIBUTING.en.md) |
| Learn repository-level agent conventions | [AGENTS](AGENTS.md) |
