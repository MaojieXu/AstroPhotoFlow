# Development environment

English | [中文](development.md)

Develop in a single Git checkout. See the [Quickstart](../README.en.md#quickstart) for installation and startup. The full workbench is validated on Windows x64.

## Tools and dependencies

| Dependency | Version | Notes |
| --- | --- | --- |
| Python | 3.12.15 | Managed by uv according to `.python-version` |
| uv | 0.13.5 | Installs Python dependencies and runs commands in the project environment |
| Node.js | `>=26.8.2 <27` | Frontend build and tests |
| pnpm | 11.13.1 | Pinned by `packageManager` in the root `package.json` |

The root `uv.lock` governs `.venv`, and `frontend/pnpm-lock.yaml` governs `frontend/node_modules`. pnpm uses its hoisted layout so Windows terminals without directory symlink permissions can resolve dependencies. The package managers own their download caches.

## Directories

- `.artifacts/build/frontend` holds built web assets and `.artifacts/dist` holds distribution artifacts. `frontend/build` is source code.
- `.artifacts/runtime` holds the fixed CPU engine for a source checkout. The first `apf init` prepares it, and later runs verify and reuse it. To isolate the engine, set `ASTROPHOTOFLOW_RUNTIME` to an absolute path.
- `.artifacts/workspaces/dev` holds the daily workbench configuration, database, assets, and workflows. `apf init` copies the web assets into that workspace's `web` directory, and `--no-activate` preserves the default workspace pointer. Preserve the workbench directory when cleaning build outputs.

The database is currently in v1 development, and all existing workspace contents are replaceable test data. Schema changes update the single initialization baseline directly. Replace or rebuild test workspaces as needed, without preserving old test contents or writing migrations for earlier development versions. When database v2 development formally begins, preserve v1 data and design and validate upgrade migrations. Here, v1 and v2 refer to database development stages.

After changing the ORM, run `pnpm generate:database-baseline`, review the generated constraints, and use `tests/core/test_image_management_migration.py` to verify that a fresh database matches the ORM. Before rebuilding in place, stop the target instance through the core control entry point and verify the absolute target path and cleanup scope. Confirmed v1 test workspaces may be replaced directly as part of development tasks. Original assets outside the workspace remain subject to original-file protection rules.

## Common commands

| Task | Command |
| --- | --- |
| Open the development workbench | `pnpm web` |
| Stop the development workbench services | `pnpm web:stop` |
| Check the development workbench service status | `pnpm web:status` |
| Start Vite separately for a running development workbench | `pnpm web:vite` |
| MCP development reload | `pnpm dev:mcp --workspace .artifacts/workspaces/<test> --port 8765` |
| Development Bundle sources | `uv run --locked --no-sync python scripts/dev_bundle_sources.py --help` |
| Python tests | `uv run --locked --no-sync pytest -q --basetemp=.artifacts/pytest-<task>` |
| Install Python test and packaging tools | `uv sync --locked --extra dev` |
| Frontend unit tests | `pnpm test` |
| Architecture boundary check | `pnpm check:boundaries` |
| Documentation gate | `pnpm check:docs` |
| Interface artifacts | `pnpm docs:api` |
| Check the development environment (run `uv sync` first) | `pnpm doctor` |
| Prune expired temporary artifacts | `uv run --locked --no-sync python scripts/prune_artifacts.py` (`--apply` deletes) |

## Develop against Bundle sources

At the repository root, enable source discovery for a prepared test workspace, then check out development repositories into direct children of `bundles/`. Each checkout has its own Git history.

```powershell
uv run --locked --no-sync python scripts/dev_bundle_sources.py --workspace .artifacts/workspaces/bundle-test --repo-bundles
git clone --branch dev https://github.com/MaojieXu/AstroPhotoFlow-Siril.git bundles/siril
```

After saving an adapter, the next run or preview uses the new code. After declarations change, the open page refreshes the node catalog. Existing instances whose parameters or ports changed appear unavailable. Add the new node from the catalog. Use `--clear-repo-bundles` to clear the directory binding or `--bundle-source <id>=<path>` to bind a specific directory.

## Debugging

- Use the `web_url` from `pnpm web:status` for the backend-served page. Vite prints its own URL in the terminal. The workspace's `run/processes.json` records the actual backend ports, and `config.toml` holds the preferred ports.
- Use an isolated test workspace in the checkout for browser and MCP validation. See [Testing](testing.en.md) for browser and parallel test settings.
- `pnpm web` opens the Vite page and watches platform Python source. When the workbench is busy, the terminal reports what blocked the restart. Save again or restart explicitly once the work finishes. Ctrl+C stops Vite and the watcher. `pnpm web:stop` shuts down the workbench services.
- Stop your own instance before updating dependencies, the engine, or static web assets. When using `pnpm web:vite` separately, restart the workbench explicitly after Python changes. MCP hot reload only refreshes the MCP process.
