# Development environment

English | [中文](development.md)

Development on Windows x64 is prepared through the fixed `scripts/bootstrap.ps1` entry: it selects and verifies tools and forwards arguments to `scripts/dev_prepare.py` (`--watch` goes to `scripts/dev_frontend.py`), without changing the global PATH, Python registrations, or the default workspace. Other platforms have no validated path.

## Environment and versions

| Dependency | Version | Notes |
| --- | --- | --- |
| Python | 3.12 | `pyproject.toml` requires `>=3.12`; bootstrap prefers a local 3.12, otherwise it installs a managed copy |
| uv | 0.13.5 | Python dependency and toolchain entry |
| Node.js | `>=26.8.2 <27` | Frontend build and tests |
| pnpm | 11.13.1 | Pinned by `packageManager` in `package.json` |

The lock files are the root `uv.lock` and `frontend/pnpm-lock.yaml`. The root `package.json` is the task entry; frontend dependencies and lock files live in `frontend`, and `pnpm install` is not run at the repository root.

## Fixed entry point

On Windows x64, `scripts/bootstrap.ps1` is the only startup entry:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 --workspace .artifacts/workspaces/dev --build --start
```

| Argument | Effect |
| --- | --- |
| `--workspace` | Required; an independent workspace directory |
| `--build` | Builds the frontend output from the current sources |
| `--frontend-assets` | Reuses a previously verified web output directory |
| `--start`, `--stop` | Starts both services; stops only that workspace |
| `--watch --port <port> --strictPort` | Runs Vite hot reload |
| `--service-port`, `--comfyui-port` | Domain service and ComfyUI ports, defaulting to 8190 / 8188 |
| `--runtime-dir`, `--cache-dir` | Private runtime and tool/package cache directories |
| `--offline` | Uses only local caches, no network |
| `--bundle-source`, `--clear-bundle-source` | Binds or unbinds a development bundle source |

Missing tools are downloaded as pinned archives into `.artifacts/toolchains` and verified; caches default to the main checkout's `.artifacts/cache` and can be overridden with `--cache-dir` or the `ASTROPHOTOFLOW_DEV_CACHE` environment variable. The receipt is written to `.artifacts/dev-prepare.json` and logs to `.artifacts/logs/dev-prepare/<run_id>`.

## Common commands

| Task | Command |
| --- | --- |
| Install development dependencies | `uv sync --locked --extra dev` |
| Prepare dependencies and a workspace | `pnpm dev:prepare --workspace .artifacts/workspaces/<name> --start` |
| Build the frontend output | `pnpm build` |
| Frontend hot reload | `pnpm build:watch --workspace .artifacts/workspaces/<name> --port 32589 --strictPort` |
| MCP development reload | `pnpm dev:mcp --workspace .artifacts/workspaces/<name> --port 8765` |
| Python tests | `uv run --locked --no-sync pytest -q --basetemp=.artifacts/pytest-<task>` |
| Frontend unit tests | `pnpm test` |
| Browser tests | `pnpm test:browser` |
| Architecture boundary check | `pnpm check:boundaries` |
| Documentation gate | `pnpm check:docs` |
| Interface artifacts | `pnpm docs:api` |

## Artifacts and receipts

- `.artifacts/build`: frontend, engine, and Python build artifacts; `frontend/build` is source, not an artifact.
- `.artifacts/dist`: distribution artifacts.
- `.artifacts/venvs/dev`, `.artifacts/toolchains`, `.artifacts/managed-python`, `.artifacts/cache`: development environment and caches.
- `.artifacts/workspaces/<name>`: an independent workspace with configuration, database, objects, previews, and run records.
- `.artifacts/dev-prepare.json`: arguments, stages, and result of the latest preparation.
- `.artifacts/logs/dev-prepare/<run_id>`: stage logs from bootstrap and preparation.

## Debug entry points

- The receipt's `completed` means the preparation request finished and `ready` means the services are ready; neither means the page has been displayed. Use the receipt's `web_url` as the page address.
- Point browser validation at your own receipt address with `APF_WEB_URL` and at your own workspace with `APF_TEST_WORKSPACE`.
- Native queue and restart scenarios require `APF_ALLOW_NATIVE_QUEUE=1` and `APF_ALLOW_WORKBENCH_RESTART=1` explicitly set; otherwise they are reported as skipped.
- Parallel pytest runs must each pass a distinct `--basetemp=.artifacts/pytest-<task>`.
- After changing Python or service code, explicitly restart your own instance; MCP hot reload does not restart the domain service.
