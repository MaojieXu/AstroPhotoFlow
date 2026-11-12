# Workbench

English | [中文](workbench.md)

Configuration, workspace layout, process control and maintenance belong to the core module; there are only two resident processes, the native web page/engine and the FastAPI domain service. Module responsibilities are in [architecture](../architecture.en.md), and usage steps are in the [usage guide](../user/workbench.en.md).

## Responsibilities

- Resolve configuration and the default workspace, prepare the runtime, start, stop and query the two resident processes, and record the adopted configuration.
- Provide reading, saving and explicit restart of workbench configuration; saving never restarts automatically, and a restart uses saved values.
- Maintain the service token, logs and runtime files; core owns no business facts.

## Workspace layout

- `config.toml` and `data/`; data is resolved relative to the configuration and defaults inside the workspace.
- `data/` holds the SQLite database, managed originals, previews, upload staging and service.token.
- `input/`, `output/`, `logs/`, `context/`, `comfyui-user/`, `comfyui-data/` and `run/` hold native and runtime files; `input/` is not the library original directory.
- Detailed persistent content and cache ownership are in [architecture](../architecture.en.md).

## Startup and control

- Startup prepares the runtime and web directory, then starts the two processes; a port conflict selects the actual port.
- Saving configuration is refused when the system is busy or idleness cannot be confirmed; unsaved content is never used for a restart.
- Stop waits for tasks to drain; a timeout or unknown identity keeps the record and states that the stop is unconfirmed.
- Existing databases are not upgraded automatically; logs are in the workspace `logs/` and the service token is never printed.

## Inputs and outputs

- Inputs: configuration files, an explicit workspace and control commands, and workbench configuration changes.
- Outputs: the adopted configuration and ports, process records, maintenance results and configuration state.
- After a disconnect, existing requests are queried first and never resubmitted automatically.

## External contracts

- HTTP routes are in `src/astrophotoflow/interfaces/http/system.py` and `maintenance.py`; configuration and control are in `src/astrophotoflow/core/config.py` and `core/workbench/`.
- HTTP authentication and dependencies are in `src/astrophotoflow/interfaces/http/dependencies.py`; fields follow the [OpenAPI snapshot](../api/openapi.json).
- Local start and stop run outside the HTTP service, while business reads and writes still go through each module's public entry points.

## Tests and boundaries

- Tests are in `tests/core/` and `tests/packaging/`.
- Maintenance endpoints update running state through public entry points; business rules never enter core.
