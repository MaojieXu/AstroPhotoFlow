# ADR-WORKBENCH-WORKFLOWS-0059: Native Editing, Save Before Run and Explicit Agent Page

Date: 2026-10-27

## Status

Accepted

Accepted product and interface design; the bridge and submission behavior are
not implemented. This refines ADR 0058 without changing the five-module boundary.

## Context

The platform reuses ComfyUI files, canvas operations, undo, graphToPrompt and
execution. Agent edits need a clear target, and a run must correspond to the
canvas the user has saved. Multiple open pages make implicit targeting ambiguous.

## Decision

- Use local graph operations for routine Agent changes. Keep whole-graph JSON
  for import or explicit replacement, using native loading rather than another
  editor or graph language. Check target, current content and current control at
  the actual mutation boundary; report actual application separately from saving.
- Save the current canvas before every managed run, including native buttons,
  shortcuts, automatic queue paths and MCP submissions. A failed save blocks
  that run. Conversion and input preparation must not submit different content
  from the saved canvas. Persist the actual run graphs and parameters separately
  from the one editable current file, without per-edit revision history.
- Bind the Agent by the user clicking “交给 Agent” in the intended page. This
  explicit handback is also required after manual editing takes control. Reading,
  reconnecting or starting another client context cannot grant control. Switching
  workflows pauses later edits and submissions to the old target; accepted work
  continues and results stay associated with its original workflow.

## Alternatives Considered

Whole JSON replacement for every edit reduces operation entry points but makes
small changes depend on rewriting unrelated content. Use focused native changes.

Running an unsaved canvas avoids waiting for disk but leaves the reopened graph
different from the run. The user chose save success as a prerequisite.

Listing online pages for the Agent to select adds chat steps and ambiguity. The
user chose a button in the intended page; there is no automatic page following.

## Consequences

Prototype native command delivery and responses, trusted UI handback, session
undo, save failure, asynchronous conversion, tab switching and late messages.
Native socket IDs are routing identifiers, not authorization. Reuse native
connections and file operations; do not add a second editor, queue or permanent
command/acknowledgement ledger. Existing 58 MCP tools and Skills remain unchanged
until the separately planned complete migration.

The future shared contracts are documented in
[platform contracts](../../../docs/archive/2026-10-29-planning/api/platform-contracts.md). No API, model,
runtime, dependency or business data change is part of this documentation task.
