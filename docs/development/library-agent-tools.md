# Library agent tools

The Python `AssetClient`, `apf` CLI and `apf mcp` stdio server share explicit domain operations over the authenticated local HTTP service. They use the same workspace config/token and business rules as the UI. They do not open SQLite or change workspace activation/MCP registration. Existing `client.py` imports, transport/context manager, `ServiceApiError`, `apf`/`apf-service` entrypoints and workbench flags remain compatible. MCP clients must reconnect to use the two domain tools; flat names have been replaced.

## Structure and request contracts

- `client.py` owns config, authentication, HTTP transport, request serialization and service errors.
- `interfaces/client/imports.py`, `library.py`, and `organization.py` own named business methods and endpoint paths.
- `interfaces/cli/commands.py` maps named CLI commands to those methods; `interfaces/mcp/tools/` contains explicit typed MCP functions over the same methods.
- Pydantic request models from `contracts/` are reused directly; the old backend schema paths are retired. `PhotoImportOptions` describes upload metadata only; file names and sizes are built from supplied local paths and validated by `UploadImportCreate`.

Complex CLI requests use `--data '<JSON>'` or `--data '@request.json'` for UTF-8 JSON. MCP requests use a typed `body` object, except `imports.upload_one`/`imports.upload` use optional `options`, and the original `assets.update_parameters` retains `asset_id`, `base_revision`, `parameters`. Operation describe results contain the full nested backend contracts, including equipment discriminators and revision fields; top-level tool schemas do not embed them. Unknown fields fail validation before HTTP.

Serialization uses `model_dump(mode="json", exclude_unset=True)` recursively. Omitted fields remain omitted; explicit null and numeric zero survive. A stale revision fails with the backend's `REVISION_CONFLICT`, HTTP status, field details and request ID. The CLI prints a failure to stderr and exits 1; MCP returns a tool error preserving that information. No blind conflict retries or fallback values are introduced.

Use `ASTROPHOTOFLOW_CONFIG` to select an already configured workspace:

```powershell
$env:ASTROPHOTOFLOW_CONFIG='C:/APF/workspace/config.toml'
apf imports roots
apf imports browse science --path '2026-10-25' --limit 50 --offset 0
```

There is no arbitrary-HTTP MCP tool. Legacy capture-profile endpoints, FITS HDU/header inspection, every numeric library filter and service-admin endpoints are not exposed as dedicated MCP tools. Existing service administration commands remain available.

## Active canvas editing

Read `canvas.pages` and `canvas.get` to locate the user's exact active graph. On an explicit user edit request, use `canvas.edit` or `canvas.add_data` directly with the current target and content; no handoff or control marker is required. CLI equivalents are `apf canvas pages`, `get`, `edit`, `add-data` and `result`. Discover processing nodes with `nodes.search` / `nodes.get` before adding or configuring them. Canvas editing does not execute the workflow.

`canvas.edit` supports `delete_node` for one explicit node. It removes that node and attached links through the native change/undo lifecycle, retaining other nodes and source assets. Missing nodes and native deletion-protected nodes fail without changing the graph.

Stop if the page, graph or content changes; do not automatically follow a new graph or overwrite manual changes after rereading. For an unknown result, query `receipts.get` with the original operation ID instead of replaying. Request fields and schemas remain defined by the published contracts.

## Command and tool inventory

List commands accept `--limit/--offset`. Searchable registries accept `--q/--status/--sort-by/--order`; asset lists additionally accept `--frame-type/--role`; equipment accepts `--kind`; presets accept `--equipment-setup-id`. `apf <group> <command> --help` lists the actual supported flags. `tasks get` has `--items-limit/--items-offset` for member paging. `library list` offers `--frame-class` in addition to frame type/role/name/order. Reference lists, version lists, calibration targets and trash retain their own paging scope.

MCP exposes only `data_management(operation, arguments)` and `node_canvas_management(operation, arguments)`. Existing flat MCP names are removed; reconnect clients to refresh their tool lists. HTTP and CLI commands retain their existing contracts.

Data groups: `imports`, `import_tasks`, `library`, `assets`, `datasets`, `projects`, `equipment`, `calibration`, `previews`, `trash`. Node/canvas groups: `nodes`, `canvas`, `receipts`, `runs`. Call known operations directly. `discover` accepts `query`, `group`, `limit` (1–10) and `offset`; exact matches include the full definition. `describe` accepts `operations: [names]` (1–10). Definitions, examples and validation come from the fixed Python registry and existing contracts, not this document. There are no empty Skill/feedback tools and no arbitrary HTTP/SQL/code gateway.

For a user-confirmed night import, call data `imports.inspect` with `body: {paths: [absolute paths], recursive: true}`; retain the returned `scan_id` and suggested group IDs. Header facts take priority over filename clues. Show source/date range, group counts, unknowns/conflicts/exclusions and ask for confirmation before importing. Read additional groups with `imports.entries(kind="groups")`; file details and exclusions are paged only as needed.

Submit once through `imports.submit`: `body: {scan_id, request_id, groups: [{name, group_id}]}`. Explicit ordered `member_ids` replace `group_id` when reorganizing. Only confirmed manual metadata goes into `options`; no guessed values are written automatically. Optional project association requires `project_id` and current `project_revision`. All source stamps are checked before acceptance; registration/copy checks retain the inspected stamps. This flow makes managed copies; direct `imports.local` folder scope and configured-root reference semantics are unchanged.

Retain `request_id` before submitting. The same ID/body returns the accepted mapping; changed content conflicts. Query unknown acceptance by that ID; do not submit a new ID blindly. `import_tasks.wait(body={request_id, wait_seconds:20})` observes the whole batch, returns early on completion and otherwise reports `next_poll_seconds`. Registration, original/metadata/preview states and project linking remain separate. `projects.retry_import_links(request_id, body={base_revision})` retries only project association after reconciling the current project, never re-imports. Manifests live in workspace data; accepted batch mappings live in existing task reports. Service restart does not discard them.

`nodes.search` returns at most ten summaries; `nodes.get/get_many` reads explicit full definitions. `previews.read` returns native MCP image content; routine data operations return structured metadata without embedded images. Existing CLI preview exports continue to create files exclusively and preserve an existing destination.

## Night import and automatic/manual classification

Data nodes also accept either an upstream `APF_SCIENCE` reference or a native floating `IMAGE` batch. Connected inputs take precedence over local reference controls; conflicting inputs fail. Native IMAGE is fixed to complete FITS members in its native run directory (float16 promoted to float32, float32/64 retained), without registering assets. Only Data becomes a native output/preview node; File retains its original contract. Execution does not save to the library or export to the computer automatically.

For an actual Data execution, `data_management` operation `exports.inspect` takes `run_id` and `execution_id`. `exports.submit` accepts `body` with a stable `request_id`, `source:{run_id,execution_id}`, ordered `member_indexes`, and `target:"library"|"local"`; local exports additionally require an absolute `destination` (a file for one member, a directory for several). `exports.status/cancel` observes/cancels the existing request. Unknown acceptance must be queried/recovered with the same ID and unchanged body, never by re-running the graph. Receipts retain each member's outcome, destination or registration task ID, and conversion facts; cancellation preserves completed members. Interrupted jobs are observed, not automatically replayed.

The default is complete original-file copying. Explicit conversion supports FITS, XISF, TIFF, PNG and JPEG with only their advertised precisions. Integer conversions do not implicitly normalize, clip, develop RAW or use thumbnail JPEGs. Fractional/out-of-range/nonfinite values require an explicit conversion decision; normalization requires an explicit finite range and display rendering requires a frozen recipe. Multi-HDU/video conversion requires the selected HDU/frame. Multi-image XISF, complex TIFF layouts and sensor RAW numerical conversion require upstream explicit selection/development; original copying preserves those complete containers. Export settings affect copies, never the Data science output. Use `describe(exports.submit)` for exact fields and valid format/precision combinations rather than copying a second schema table here.

```powershell
apf import-photo 'C:/Photos/one.fits'
apf import-photos 'C:/Photos/one.fits' 'C:/Photos/two.fits' --data '@upload.json'
apf imports local --data '@night.json'
apf tasks list --status all --limit 20
apf tasks get TASK_ID --items-limit 50 --items-offset 0
apf tasks cancel TASK_ID
apf tasks resume INTERRUPTED_TASK_ID
apf tasks retry FAILED_TASK_ID --data '@retry.json'
```

`upload.json` contains optional metadata, for example:

```json
{"dataset_name":"M31 L night","capture_preset_id":"PRESET_UUID"}
```

`night.json` selects one or more configured-root files/folders:

```json
{"sources":[{"root_id":"science","path":"2026-10-25/M31"}],"storage_mode":"reference","dataset_name":"M31 night"}
```

`retry.json` selects original task-item IDs: `{"item_ids":["FAILED_ITEM_UUID"]}`. Resume applies to service-interrupted tasks; selected retry applies to eligible failed or cancelled tasks/items. Task `report.registration.completed` is distinct from `content_status`, `metadata_status`, `preview_status` and asset-version `availability`. Registration alone does not mean managed originals or previews are ready. A `SOURCE_CHANGED` item error / `availability:changed` means the source changed between registration and reading/copying: confirm the intended current source and create a new import rather than blindly retrying or altering timestamps.

The old single-photo client no longer hardcodes Light/subframe. Omitted classification keys use file facts/preset defaults. Supplied keys override the batch, including explicit null; supply both keys to classify the whole batch manually:

```json
{"classification":{"frame_class":"subframe","frame_type":"light"},"parameters":{"gain":0,"exposure_seconds":120},"dataset_name":"Manually classified night"}
```

Unknown stays unknown; filename hints in inspection are proposals and only become manual classification when the user confirms the corresponding values. Parameter priority is manual non-null, observed file, frozen preset, unknown. The service freezes preset/setup facts when accepting the task and retries retain that snapshot. The client does not resolve mutable live presets. Multiple uploads create a logical dataset according to the existing backend rule, even when `create_dataset` is omitted.

## Revision edits, groups and project references

```powershell
apf assets get ASSET_UUID
apf assets parameters ASSET_UUID --base-revision 3 --gain 0 --clear exposure_seconds
apf assets patch ASSET_UUID --data '@asset-patch.json'
apf datasets create --data '@group.json'
apf datasets version DATASET_UUID VERSION_UUID
apf datasets publish DATASET_UUID --data '@publish.json'
apf datasets member-parameters DATASET_UUID --data '@members.json'
apf projects create --data '{"name":"M31 processing","target_name":"M31"}'
apf projects add-asset PROJECT_UUID --data '@asset-reference.json'
apf projects add-dataset PROJECT_UUID --data '@dataset-reference.json'
apf projects remove-asset PROJECT_UUID REFERENCE_UUID --data '{"base_revision":4}'
```

Representative bodies (replace UUID placeholders with actual returned IDs):

```json
{
  "asset-patch.json": {"base_revision":3,"notes":null,"classification":{"frame_type":"light"}},
  "group.json": {"name":"M31 L","asset_version_ids":["ASSET_VERSION_UUID"]},
  "asset-reference.json": {"base_revision":1,"asset_version_id":"ASSET_VERSION_UUID"},
  "dataset-reference.json": {"base_revision":2,"dataset_id":"DATASET_UUID","dataset_version_id":"DATASET_VERSION_UUID"},
  "members.json": {"base_revision":2,"base_version_id":"DATASET_VERSION_UUID","members":[{"asset_id":"ASSET_UUID","revision":3}],"parameters":{"gain":0}}
}
```

Read the current project revision between dependent reference writes. References pin versions; membership and project reference operations do not physically copy originals. Removing project references preserves the library object. Group publication takes the complete membership list; retained members keep their existing relative order and new members append. Batch member editing requires `base_version_id` and revisions for ALL current canonical group assets.

## Equipment, setups and owned presets

```powershell
apf equipment create --data '{"kind":"camera","name":"Main camera","specs":{"sensor_mode":"mono"}}'
apf equipment list --kind telescope
apf setups create --data '@setup.json'
apf presets create SETUP_UUID --data '@preset.json'
apf presets list --equipment-setup-id SETUP_UUID
apf presets patch PRESET_UUID --data '{"base_revision":1,"parameters":{"gain":0,"offset":null}}'
apf equipment archive EQUIPMENT_UUID --kind camera --base-revision 2
apf setups archive SETUP_UUID --base-revision 2
apf presets archive PRESET_UUID --base-revision 2
apf projects archive PROJECT_UUID --base-revision 5
```

```json
{
  "setup.json": {"name":"Travel rig","components":[{"source":"registered","equipment_id":"EQUIPMENT_UUID"},{"source":"inline","equipment":{"kind":"accessory","name":"Adapter"}}]},
  "preset.json": {"name":"L 120s","classification":{"frame_class":"subframe","frame_type":"light"},"parameters":{"gain":0,"exposure_seconds":120}}
}
```

Equipment kinds are camera, telescope, filter, mount, accessory and the preserved optical_system. Inline components are snapshots and do not auto-register equipment. Setup edits do not modify registered equipment. Configuration deletion means archive; no physical table deletion command is offered.

## Fixed calibration bindings

```powershell
apf calibration targets --frame-type dark --limit 50 --offset 0
apf datasets publish DATASET_UUID --data '@publish.json'
```

```json
{"base_revision":2,"asset_version_ids":["MEMBER_VERSION_UUID"],"calibration_defaults":{"dark":{"kind":"asset_version","id":"MASTER_DARK_VERSION_UUID"}},"member_calibration_overrides":{"MEMBER_VERSION_UUID":{"dark":null}}}
```

Targets are fixed asset_version or dataset_version IDs. Supplying defaults replaces the map, `{}` clears it, omission retains it. Each supplied member map replaces that member's map; omitted members retain theirs. Missing slots inherit and null explicitly disables use. `{}` restores member inheritance. The service validates target kind/use. It records calibration relationships without calibration computation. Historical bindings still protect targets after current bindings change.

## Display preview and guarded cleanup

```powershell
apf previews schedule ASSET_UUID VERSION_UUID
apf previews status ASSET_UUID VERSION_UUID
apf previews export ASSET_UUID VERSION_UUID preview.jpg
apf library remove --data '@remove.json'
apf trash list --limit 50
apf trash restore --data '@selection.json'
apf trash delete-preview --data '@selection.json'
apf trash delete --data '@confirmed-delete.json'
```

Preview state is `not_ready|generating|available|failed|unsupported`. Poll while generating. On `not_ready`, inspect original availability and the import-task outcome; wait only for a live running import/retry. Otherwise report the concrete unavailable/failed/interrupted cause or perform an already-authorized resume/retry. Cached failed/unsupported outcomes are terminal; inspect the error and explicitly schedule to retry a failed preview. Read/export the cached display JPEG after availability. No implicit scheduling is hidden in the image read.

Removal items require `entry_type`, `id`, `revision`, `current_version_id`. Trash selection items require `entry_type`, `id`, `removed_at`, `revision`, `current_version_id`, optional `source_dataset_id`. Use only these request fields from the current trash DTO. A permanent deletion body is that exact current selection plus `preview_fingerprint` from its fresh deletion preview. Review references, tasks and managed-file scope, and act only inside the user's explicitly authorized permanent cleanup task.

Backend fingerprints, reference checks, active-task protection, partial cleanup and external-source rules remain authoritative. Calibration consumers/targets selected together can leave a retained target as an independent trash record. Re-read trash and preview before retrying; do not clear maps or remove managed files directly. Unknown or stale state fails clearly.

## Project Skill and verification

[The project Skill](../../.agents/skills/astrophotoflow-library/SKILL.md) is versioned here and included in the source distribution with this reference. It needs no global installation.

Run `uv run --locked --no-sync pytest tests/integration -q` for the named client, CLI and real SDK stdio workflows. Tests use temporary services and synthetic originals. Current results and coverage limits are maintained in the [verification matrix](test-matrix.md).
