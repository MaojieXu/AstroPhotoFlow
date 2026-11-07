# Architecture

English | [中文](architecture.md)

The platform builds on a pinned ComfyUI engine and the native web workbench; domain capabilities are provided by a FastAPI service in the same process. Each workspace runs two resident processes: the ComfyUI web page and engine, and the FastAPI domain service. Modules are code responsibilities, not separate services; per-subsystem behavior is in [Subsystems](subsystems/README.en.md) and product rules in [Product requirements](product/README.en.md).

## Modules and responsibilities

| Module | Responsibility | Source entry |
| --- | --- | --- |
| `contracts` | Cross-module types, enums, and validation; depends only on the standard library and Pydantic | `src/astrophotoflow/contracts` |
| `core` | Configuration, authentication, database connection and migration, workspace lifecycle, and local process control | `src/astrophotoflow/core` |
| `data` | Asset identity, fixed collection versions, equipment snapshots, calibration relations, user-selected results, and trash in SQLite; scientific files stored separately | `src/astrophotoflow/modules/data` |
| `software` | Pinned software packages and bundles, installation and readiness state, actual calls, and stop observation | `src/astrophotoflow/modules/software` |
| `nodes` | Editable node definitions in workspace JSON, update diffs, and derived catalogs | `src/astrophotoflow/modules/nodes` |
| `interfaces` | HTTP, CLI, MCP, native bridge, and cross-module use-case assembly | `src/astrophotoflow/interfaces` |
| Native ComfyUI system | Workflow editing, graph files, drafts, saving, undo, conversion, queue, execution history, progress, and cancellation | `engine/ComfyUI` |
| In-house UI and host bridge | Private Vue component package; native stores, canvas, and event coordination | `frontend/packages/astrophotoflow-ui`, `frontend/src/platform/astrophotoflow` |

## Data and state ownership

- The native workspace JSON is the only editable current graph; graph files, drafts, undo, and execution history belong to native ComfyUI mechanisms.
- `data` owns the business facts in SQLite; scientific files are stored separately and never written into the database.
- `software` owns the software package catalog, installation and readiness state, actual calls, and stop records, linking call facts by native execution UUID.
- `nodes` owns node definitions in workspace JSON and derived catalogs, and does not depend on executors in reverse.
- `core` owns configuration, authentication, database migration, and local workspace process control, with a few files recording the latest configuration and actual runtime state.
- Previews and thumbnails are derived caches, not scientific originals; query unknown results first instead of blindly rerunning.

## Dependency direction and invariants

- `contracts` depends only on the standard library and Pydantic; `core` does not depend on business modules, except explicit migration metadata assembly.
- Business modules cooperate through their public `public.py` entries and never read another module's private ORM.
- `interfaces` assembles use cases from `data`, `software`, and `nodes`, and owns neither graphs nor scheduling.
- HTTP, CLI, and MCP share service capabilities and never write SQLite directly; local start and stop go through `core` control entries.
- The in-house UI package consumes native package exports only and must not import native singletons in reverse.
- No second editing, scheduling, collaboration ledger, or generic recovery system is added.

## Cross-module assembly

- Saving results: native page presentation locates checked results in `data`; after the user selects complete members, they enter the library or are exported.
- Software calls: `software` stores call facts, `data` stores checked result-file facts, and `interfaces` composes both and exposes them.
- Canvas and agents: `interfaces` exposes shared canvas capabilities, the native page bridge performs node, widget, and link operations, and external agents observe and modify the current graph through MCP.
- Interface fields follow the generated artifacts (see [References](references.en.md)); Python module handoffs follow `public.py` and `contracts`.

## Runtime topology

- Two resident services: the ComfyUI web page and engine (pinned version, started under management) and the FastAPI domain service (`apf-service`).
- The web page reaches the domain service through the same-origin `/astrophotoflow/api/v1` proxy; the CLI and MCP use `/api/v1`.
- Each workspace stores its own configuration, database, objects, previews, and run records; the page address is returned by `core` and never assembled by hand.
- Vite is only for frontend hot reload during development and adds no resident service.

## External integrations

- Siril is a separate private bundle: the platform keeps the SDK, loading method, and directory snapshot, and does not bundle Siril sources or runtime files into the product wheel.
- The pinned engine is distributed as an archive inside the wheel; versions and hashes follow the inventory in `src/astrophotoflow/vendor`.
- External agents operate through the platform MCP stdio process; the platform embeds no chat, reasoning, or model sessions.

## Where details live

- Product rules and scope: `docs/product/*`; per-subsystem behavior: `docs/subsystems/*`.
- Environment and commands: [Development](development.en.md); tests and receipts: [Testing](testing.en.md).
- Interfaces and generated artifacts: [References](references.en.md); non-obvious decisions already made: `.agents/notes/README.md`.
