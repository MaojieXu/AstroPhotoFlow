# Interface references

English | [中文](references.md)

Interface fields, types, required flags, and status codes follow the actual routes and Pydantic models; docs do not hand-copy schemas and point to the generated artifacts instead.

## Generated artifacts

| Artifact | Content | Generator |
| --- | --- | --- |
| `docs/api/openapi.json` | HTTP contract | `scripts/export_openapi.py` (`pnpm docs:api`) |
| `src/astrophotoflow/vendor/http-routes.json` | Public route inventory used by the same-origin proxy | same |
| `docs/api/mcp-tools.json` | MCP tool snapshot | `scripts/generate_cli.py` |
| `src/astrophotoflow/interfaces/cli/generated.py` | Business CLI commands | same |
| Frontend SDK | TypeScript and Zod client generated from OpenAPI | `pnpm generate:sdk` |

## Query entry points

- HTTP: the domain service serves `/openapi.json`; Swagger `/docs` and ReDoc `/redoc` are disabled.
- The web page reaches the domain service through the same-origin `/astrophotoflow/api/v1` proxy, while the CLI and MCP use `/api/v1` directly.
- CLI: `apf --help` lists commands and `apf call-tool TOOL --help` shows one tool's inputs.
- MCP: the service's `tools/list` returns registered tools and their actual input schemas.
- Native page messages: the `x-apf-native-messages` component of the same OpenAPI document, sourced from `src/astrophotoflow/interfaces/http/schema.py`.
- Python cross-module handoffs: each module's `public.py` and `src/astrophotoflow/contracts`.

## Consistency

- Regenerate and commit the artifacts after interface changes; never edit them by hand.
- The consistency test `tests/modules/data/test_service.py::test_openapi_snapshot_matches_service_and_proxy_allowlist` compares the actual schema, the snapshot, and the proxy allowlist, and runs in CI.
