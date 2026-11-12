# ADR-WORKBENCH-WORKFLOWS-0058: Reuse Native Workflows for Execution and Agent Interaction

Date: 2026-10-27

## Status

Accepted

This is an accepted documentation design, not an implementation. Software
package and custom node update policies are defined in ADRs 0056 and 0057.

## Context

Users edit one visible graph, run astronomy tools, inspect images and continue
with an external Agent. ComfyUI provides JSON storage, drafts, undo, conversion,
queueing, events and cancellation. The platform needs project association,
execution records, previews and explicit online control.

## Decision

- Place workflow, execution and Agent interaction in module ⑤ under workflows.
  Keep MCP protocol adaptation in interfaces and native stores/canvas coordination
  in the host bridge. Keep data, software and node ownership in ②③④.
- Use the native workspace workflow JSON file as the only editable current
  graph. Add project association and minimal current control metadata, not a
  second editable graph. Keep native local drafts and session undo. Use Save As
  for important independent schemes; persist the actual graphs and parameters
  used by each run, without permanent per-edit revisions.
- Keep necessary execution, cancellation and selected-result-save facts in one
  run record, including its native prompt association and actual calls. Do not
  introduce separate plan, projection, handoff or acknowledgement histories.
  Native history is in memory and cannot replace required run persistence.
- First-version Agent edits and new submissions require the explicit active
  online canvas. Switching tabs pauses later edits/submissions to the old graph;
  accepted executions continue. Closing the page permits status/list queries but
  no new Agent editing or execution. Manual edits still take control until the
  user explicitly hands it back; reading or reconnecting does not regain it.
- Every image-producing node actually executed in the requested scope produces
  a lightweight completed preview. Reuse native UI outputs and executed events;
  do not make all nodes output endpoints or enlarge execution scope. Persist
  multiple completed previews with workflow/run/node/output association, route
  background results to their original graph, and do not capture every progress
  frame. Preview generation and persistent routing remain unimplemented.
- Keep scientific output separate. Only user-selected full results enter the
  asset library. Do not retain full intermediate files long term or imply that
  a saved preview guarantees its full result is still available.
- Keep skill-first known capability access, on-demand hybrid Top10 retrieval,
  explicit keyword degradation and the planned complete compact-MCP migration.
  Catalogs are derived; do not create a new author, copyright, role or approval
  platform. Existing software license preparation is unaffected.

## Alternatives Considered

A second graph store or durable conversion service would duplicate native
mechanisms. The chosen workflow uses the current graph and run records.

Headless editing and background writes to inactive canvases need additional
conversion and synchronization support. The user chose active-page interaction.
Manual preview nodes would reuse more native behavior but were rejected in favor
of automatic previews on each executed image step.

## Consequences

The bridge must validate active target, current content and current control at
mutation/submission time. Native userdata writes alone do not implement this.
Native UI events can display preview descriptors, but scientific preview creation,
multi-run persistence and cross-tab routing still need implementation. An accepted
interrupt does not prove an external application stopped; unknown submissions
are queried rather than replayed. Existing reproducible/reference input modes,
fixed groups, corrected metadata and executing/historical content protection stay.

This decision does not choose database tables, public API fields, code execution
environments, package formats or hot-loading mechanisms. No code, environment,
business data, current MCP registration or Skill changes are part of this task.
