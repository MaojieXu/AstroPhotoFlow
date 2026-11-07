---
name: astrophotoflow-library
description: Manage the local AstroPhotoFlow astronomy library through typed MCP tools or the generated apf CLI, including confirmed night imports, fixed versions, equipment, calibration, previews, explicit result saving and trash.
---

# AstroPhotoFlow library

Use the connected MCP server or apf with ASTROPHOTOFLOW_CONFIG set to the intended workspace config. Both use the same local HTTP services. Do not register global MCP, change the default workspace, write SQLite or modify managed files directly.

Known exact tools are directly callable. For unfamiliar capabilities use search_tools(query): built-in BM25 returns at most ten full definitions. It is keyword retrieval, not a semantic model. There is no domain gateway, discover or describe operation. Reconnect after schema/server changes.

Read [the operation guide](../../../docs/subsystems/library.md) for extended procedures. Live input schemas, apf call-tool TOOL --help and the [generated catalog](../../../docs/api/mcp-tools.json) define fields. Complex CLI arguments use JSON; do not maintain another parameter table.

```powershell
apf call-tool data_library_search --query '{"q":"M31","limit":50}'
apf call-tool data_assets_update --asset-id ASSET --body '{"base_revision":3,"parameters":{"gain":0,"exposure_seconds":null}}'
```

## Confirmed night import

1. data_imports_inspect observes sources without ingestion. Retain scan/group IDs and page data_imports_entries only as needed.
2. Show proposed groups, counts, dates, unknowns, conflicts and exclusions. Header facts outrank filename hints. Confirm scope, grouping, manual overrides and optional project before ingestion; never silently turn guesses into scientific metadata.
3. Submit data_imports_submit once with confirmed groups and a recorded request_id. Use group_id normally; explicit ordered member_ids are for confirmed splits/exclusions/reordering. Only confirmed overrides belong in options. A preset ID alone preserves preset priority. Project association requires its current revision.
4. Query unknown acceptance with data_tasks_status and the original request_id; do not create another ID or automatically replay. Changed sources require inspection and confirmation again.
5. data_tasks_wait observes all groups/stages/project links. Follow next_poll_seconds. Registration, originals, metadata and previews are separate outcomes. Read successful member details only on demand.

Resume interrupted work or retry eligible stages after fixing their cause. SOURCE_CHANGED requires source review. For project-link failure, reconcile revision and use data_projects_retry_import_links, not another import. data_imports_local retains direct/configured-root semantics; upload_one/upload reads client-machine files.

## Edit and organize

Read current revisions before writes. Omission preserves a field, supported null clears it, and zero remains zero. Re-read conflicts and reconcile intent; never blindly retry stale writes.

Use data_assets/datasets/projects/equipment/setups/presets tools. List queries share backend models. Dataset publication and project references use exact fixed versions and canonical member order. Setup member IDs and preset selections come from returned records, not guessed positions. Original-content acceptance requires the observed hash and revision. Preview bytes never become scientific inputs.

## Native canvas and results

ComfyUI owns workflow files, drafts, save/undo, queue, history, progress and cancellation entry. There is no project/workflow association, platform workflow lifecycle or save-before-run requirement.

Read graph_nodes_search/get/get_many before editing. graph_canvas tools require the exact user-requested page/workflow/graph and current content_token. Stop on target/content changes. Query graph_receipts_get using the original operation_id for unknown edits; do not replay or follow another graph. Editing does not execute.

software_calls tools inspect concrete native prompt/call IDs, outputs and analysis without rerunning. data_results_get inspects an actual Data execution. Save/export only user-selected complete members through data_exports_submit; record request_id first and query status for uncertainty. Formats/precision affect copies, not originals. Read current schemas for exact fields/combinations.

## Previews and cleanup

Use data_media_schedule/status/read for display previews; read returns an MCP image. Wait only for generating or known live work. Failed/unsupported are terminal observations. data_media_export exclusively creates a new JPEG file; never overwrite an existing path. software_previews_render uses exact fixed references, sample member, consumer and generation; release the consumer when done. Preview availability does not prove complete scientific output readiness.

Removal/recovery and permanent deletion are separate. Permanent cleanup requires a current preview/fingerprint and explicit user authorization. Explain dependencies and partial failures; do not delete beyond the confirmed scope. Equipment deletion likewise needs its impact preview and current fingerprint. Keep historical snapshots and originals. Distinguish cancellation accepted, actual process stopped and unknown; query existing requests rather than restarting work.
