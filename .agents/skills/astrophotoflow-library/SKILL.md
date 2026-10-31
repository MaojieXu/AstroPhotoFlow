---
name: astrophotoflow-library
description: Manage the local AstroPhotoFlow astronomy library through its HTTP-backed MCP tools or apf CLI, including night imports, fixed-version groups, project references, equipment setups, calibration bindings, previews and trash.
---

# AstroPhotoFlow library

Use the connected AstroPhotoFlow MCP server, or the installed `apf` CLI with `ASTROPHOTOFLOW_CONFIG` pointing to the intended workspace's `config.toml`. Both call the same local service. Keep the user's workspace and configuration; this Skill does not register MCP servers or change the active workspace. Use the API rather than SQL or direct managed-file changes.

Read [the operation reference](../../../docs/development/library-agent-tools.md) when choosing commands, request schemas or a complete multi-step operation. The available MCP input schemas are authoritative for arguments. Complex CLI bodies accept `--data '<JSON>'` or `--data '@request.json'` from a UTF-8 file. IDs in examples are placeholders for IDs returned by the service.

## Confirmed night import

MCP exposes only `data_management(operation, arguments)` and `node_canvas_management(operation, arguments)`. Call known operations directly. For unfamiliar parameters, `describe` accepts `{"operations":["projects.add_dataset"]}`; for unknown capabilities, `discover` accepts query/group/limit/offset, returning at most ten candidates and full schema for an exact match. Existing clients must reconnect; old flat tool names are removed. CLI commands are unchanged.

1. Call data `imports.inspect` with `{"body":{"paths":["C:/Photos/night"],"recursive":true}}`. This scans sources without registering assets or copying files. Retain scan_id and group IDs. Only ten groups are returned initially; page more via `imports.entries` with kind=groups. Read kind=files/excluded/issues only as needed, not every filename/header into model context.
2. Propose groups by target, frame type/class, filter, exposure and equipment clues. Header facts take priority; directory/name hints remain proposals. Show source/date range, group counts, unknowns, conflicts and exclusions. When the folder spans nights, clarify which files count as last night. Obtain user confirmation of groups, manual metadata and optional project before any ingestion.
3. Call `imports.submit` once with body containing scan_id, a new request_id and groups such as `[{"name":"M31 L","group_id":"RETURNED_GROUP_ID"}]`. Explicit ordered member_ids replace group_id for splitting/reordering/exclusions. Each member appears once. Group options accept classification, parameters, notes and capture_preset_id. Only confirmed manual values belong here; name hints never silently become metadata. Use only preset ID to preserve its default priority. Optional project_id requires current project_revision; create a project only if included in confirmation.
4. Retain request_id before submitting. Unknown acceptance: query `import_tasks.status`, or resend the identical ID/body; never blindly create another ID. Changed body conflicts. Source changes require a new inspection and confirmation. Manifests and accepted task mappings survive restart.
5. Call `import_tasks.wait` with `{"body":{"request_id":"REQUEST_ID","wait_seconds":20}}`. Observe all groups and project links together. Follow next_poll_seconds instead of rapid polling. Registration, originals, metadata and previews are independent. Report partial failures honestly; successful member details are read only on demand.

This flow makes managed copies and preserves originals. `imports.local` retains current-level direct folder imports and configured-root reference imports; `imports.upload_one/upload` still reads client-machine files. For interrupted tasks use `import_tasks.resume`; for selected eligible failed stages use `import_tasks.retry` after fixing the cause. SOURCE_CHANGED requires source review and a new confirmed import. For project linking failure, read/reconcile the project and call `projects.retry_import_links` with request_id and body.base_revision; never re-import for an association failure.

## Organize and edit

Read current records before edits. Pass their current `base_revision`; on a conflict re-read, reconcile the user's intended change, and submit the new revision. Do not blindly retry stale writes. Omitted PATCH fields stay unchanged, explicit `null` clears supported fields, and `0` stays zero.

- Use `assets.update(asset_id, body)` for name, notes, classification and parameters, or `assets.update_parameters(asset_id, base_revision, parameters)` for the existing parameter tool. CLI example: `apf assets parameters ASSET --base-revision 3 --gain 0 --clear exposure_seconds`.
- Use `datasets.create(body={"name":"M31 L","asset_version_ids":[...]})` for a logical ordered group. Read `datasets.get_version` to inspect fixed membership. `datasets.publish_version(dataset_id, body)` takes the complete membership list and current dataset revision; retained members keep their existing relative order and new members append. `datasets.update_members` additionally requires `base_version_id` and revisions for ALL current canonical group assets.
- Use `projects.create`, `projects.add_asset(project_id, body)` and `projects.add_dataset(project_id, body)` to pin fixed versions across nights/filters. Reference add/remove operations use the project's current revision; re-read it between dependent operations. Removing a reference preserves its library original/group.
- Register equipment using `equipment.create_item(body)` with `kind` camera, telescope, optical_system, filter, mount, or accessory. `equipment.create_setup(body)` accepts registered equipment references and inline equipment snapshots. Inline equipment is not registered automatically; editing a setup does not edit registered equipment.
- Create owned presets with `equipment.create_preset(setup_id, body)`; query with `equipment.list_presets(equipment_setup_id=...)`. Delete requests for configuration records mean archival: use the applicable update tool with `status:"archived"` and `base_revision`. CLI has explicit `projects/equipment/setups/presets archive` commands.

Reversible edits already requested by the user do not require an extra approval step.

## Bind calibration versions

Find candidates with paged `calibration.targets(limit, offset, frame_type, q)` / `apf calibration targets`. A target is a fixed `{"kind":"asset_version"|"dataset_version","id":"..."}`; standalone asset targets are Master calibration material.

Use `datasets.publish_version` for group defaults and member overrides, along with the current dataset revision and complete ordered member list:

```json
{"base_revision":2,"asset_version_ids":["MEMBER_VERSION"],"calibration_defaults":{"dark":{"kind":"asset_version","id":"MASTER_VERSION"}},"member_calibration_overrides":{"MEMBER_VERSION":{"dark":null}}}
```

Providing `calibration_defaults` replaces that map; `{}` clears it. A submitted member's map replaces its old map; an omitted member retains its map. Absent slots inherit; explicit `null` disables that slot for that member. `{}` restores all inheritance for a submitted member. Bindings belong to that dataset version and do not alter other groups. This records relationships; it does not perform calibration or stacking.

## Read a display preview

Call `previews.schedule(asset_id, version_id)`, then `previews.status`; poll while generating. On `not_ready`, inspect original availability and the import-task outcome. Wait only while a live running import/retry can resolve it; otherwise report the concrete unavailable, failed or interrupted cause, or perform an already-authorized resume/retry. Registration alone does not make a preview available. Cached failed/unsupported states are terminal outcomes; failed status carries an error and scheduling explicitly retries it. `previews.read` returns a native MCP image only when explicitly needed. CLI: `apf previews schedule ASSET VERSION`, `apf previews status ASSET VERSION`, then `apf previews export ASSET VERSION preview.jpg`. Display JPEGs are cached at a longest edge of at most 1080 pixels without enlarging small images. Export creates a new file exclusively; if the output already exists, choose a new output path. Existing originals and previews remain untouched.

## Trash and permanent cleanup

`trash.remove(body)` moves current asset/dataset selections to reversible trash. It takes `items` with `entry_type`, `id`, `revision`, and `current_version_id`. Read `trash.list` for current trash identity and partial/failed outcomes. `trash.restore(body)` restores selected records.

Permanent cleanup is allowed only within the user's explicit destructive task. First call `trash.preview_delete(body)` with the current selection fields: `entry_type`, `id`, `removed_at`, `revision`, `current_version_id`, and optional `source_dataset_id`. Inspect its references, tasks, files and bytes. Then call `trash.delete(body)` with that exact selection and the returned `preview_fingerprint`. Do not invent, reuse stale fingerprints, clear binding maps, or delete files directly.

Historical calibration/project/group references protect originals. Unbinding the current version does not remove historical bindings. Cleanup may leave partial/failed records or retain a target while selected consumer containers are cleaned. Re-read trash and generate a fresh preview before any retry; respect external sources and the backend's protection errors. Stop when the requested selections are removed, or report the concrete remaining blocker.

## Online canvas

Use node_canvas `nodes.search` for short candidates and `nodes.get/get_many` for explicit full definitions. Read `canvas.pages/get` for the requested actual graph. After an explicit user edit instruction use `canvas.edit/add_data` with exact target IDs and current content_token. Stop on target/content changes; do not follow another graph or overwrite manual changes. Unknown outcome: query `receipts.get` with the same operation ID, never replay. Editing does not execute the graph. `runs.list_calls/get_call/analysis` observes existing calls only. Projects do not yet manage native workflow-file lifecycle.

## Data node results and explicit export

Data accepts either science or images, not both. Use the actual native queue; no export operation runs the graph. Connected inputs disable local reference editing. The science output remains a fixed scientific reference. Native floating IMAGE batches are materialized as complete FITS files in the run directory (float16 promoted to float32; float32/64 retained), without automatic library registration. File nodes retain their previous contract.

Use data_management operation exports.inspect with run_id and execution_id from the actual Data result. After the user selects members and destination, exports.submit accepts body with request_id, source:{run_id,execution_id}, ordered member_indexes, target:library|local, optional name and settings. A local target requires an absolute destination: file for one member, directory for multiple members. Never guess or overwrite an existing destination. Default settings copy the original complete container; explicit format/precision choices are defined by describe(exports.submit), not a second handwritten schema table.

Supported converted formats are FITS, XISF, TIFF, PNG and JPEG, with valid per-channel precisions only. Preserve numeric values by default. Do not silently clip, normalize, develop RAW, drop channels or turn preview JPEGs into scientific input. Fractional/out-of-range/nonfinite integer conversions require an explicit choice; normalization requires a finite explicit range, and display rendering requires a frozen current display recipe. FITS/video conversion requires explicit HDU/frame selection. Complex containers and RAW numerical development may require explicit upstream selection/development; original copying preserves all their bytes.

Retain request_id before submission. exports.status queries the receipt and per-member outcome; unknown acceptance is recovered only with the same ID and unchanged payload. exports.cancel requests cancellation; completed members remain. Interrupted jobs are not automatically replayed. A library-registration failure exposes registration_task_id: inspect that existing import task before retrying any stage. Never re-run upstream processing for a save/export failure. Saved library copies retain source and conversion provenance; export settings never modify the Data science output or original files.
