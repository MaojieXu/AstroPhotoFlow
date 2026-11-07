# ComfyUI integration

English | [中文](comfyui.md)

ComfyUI is a fixed upstream engine, and the platform keeps its source modifications, managed startup and same-origin gateway. The runtime topology and module responsibilities are in [architecture](../architecture.en.md).

## Fixed engine

- `engine/ComfyUI` is fixed upstream source plus platform modifications; a normal start runs the extracted copy in the runtime directory, never this directory directly.
- Version, commit, archive and frontend dependency are recorded in `src/astrophotoflow/vendor/comfyui-source.json`.
- Runtime preparation extracts the archive into the runtime directory and uses a separate Python environment.

## Managed startup

- The engine starts in its own environment with `PYTHONPATH` pointing at the platform package, which loads the platform's native access code.
- Initialisation copies the workspace web directory from the package, and the engine reads it through `--front-end-root`.
- Start and stop are controlled by the workbench, not through business HTTP endpoints.

## Same-origin gateway

- `src/astrophotoflow/comfyui/proxy.py` forwards public routes under the `/astrophotoflow/api/v1` prefix.
- The allowlist comes from `src/astrophotoflow/vendor/http-routes.json`; only the explicit list is registered, with no wildcard forwarding and no exposure of internal paths.
- The domain service serves `/openapi.json` and disables `/docs` and `/redoc`; the web page, CLI and MCP share the same business capabilities.

## Failure modes

- When local service configuration or the token is unavailable, the gateway returns 503 with a readable error.
- Paths outside the allowlist are not forwarded; stopping the engine affects only the native web page and does not mean the domain service stopped.
- After a web disconnect, existing requests are queried first and never resubmitted automatically.

## External contracts

- Gateway code is in `src/astrophotoflow/comfyui/proxy.py`; native pages and messages are in `src/astrophotoflow/interfaces/native/`.
- The route allowlist and OpenAPI snapshot are maintained by generation scripts, listed in [references](../references.en.md).

## Boundaries

- Workflows, queues, history, progress and cancellation belong to ComfyUI; software invocations belong to software; checked results belong to data.
