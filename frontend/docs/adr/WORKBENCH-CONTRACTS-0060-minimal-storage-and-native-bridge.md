# ADR-WORKBENCH-CONTRACTS-0060: Minimal Storage and Native Bridge

Date: 2026-10-27

## Status

Accepted

Accepted design choices for the fourth documentation stage. No runtime,
storage migration, node loader or canvas protocol is implemented by this ADR.

## Context

The five-module baseline keeps one native workflow JSON as the current graph.
The interface design still needs concrete storage and native integration
boundaries before its public signatures can guide implementation.

## Decision

- Store workflow project associations, runs and preview associations in the
  existing workspace SQLite database. Keep native workflow JSON and image files
  as files. Foundation configuration and lifecycle records remain file based.
- Store workspace node definitions as JSON files. Do not add a node version
  repository, publication gate or separate port and parameter tables.
- Deliver bounded canvas commands through the existing ComfyUI connection.
  The browser host performs native editing and conversion; the domain service
  checks and records the run before submitting it to the native queue. Add only
  the required relay and response handling, without another connection service.
- Keep other custom nodes disabled and whitelist one platform-managed node
  package through the existing native loader. Its installed bootstrap delegates
  to the platform integration code; business state stays in its owning modules.

The user selected these four alternatives together. Message routing identifiers
do not grant control. Loading, refresh, trusted handback and execution still
require prototypes with explicit failure results.

Two subsequent user choices close concrete data and interaction gaps:

- After an external file change is observed and accepted, retain the asset
  identity and add an internal content record. Only explicitly selected
  references move to it; fixed groups and historical runs do not change.
- Software installation and changes requested through MCP require reviewing
  the concrete plan in the platform webpage. Keep only the current pending
  action, without an approval ledger, installation-plan table or update queue.

## Alternatives Considered

Using JSON for all workflow records avoids a migration but requires new file
queries and concurrency handling. The existing database already provides the
necessary short transactions and associations.

Storing node definitions in SQLite would centralize updates, but the user chose
directly readable JSON definitions without a separate publication system.

A separate domain-to-browser connection would simplify relay ownership while
adding another connection lifecycle. Reusing the native connection preserves
the selected integration direction.

Registering platform nodes directly in the fixed engine would avoid a loader
bootstrap but require maintaining that integration when the engine changes.
The native whitelist already supports loading only the managed package.

## Consequences

Define public operations, DTOs, file ownership and tests in the
[platform contract](../../../docs/api/platform-contracts.md). Do not duplicate
the editable current graph, add a scheduler or create placeholder source files.
Database transactions do not make file updates, queue submissions and external
software calls atomic.

Native conversion is preparation, not execution. Its existing queued-widget
callbacks and asynchronous serialization must settle before the one required
successful save and final submission. Verify execution-relevant content rather
than byte equality of localized or display metadata. This satisfies ADR 0059
without a second serializer, mandatory double save or repeated randomization.

The first software version and operation, target conversion, scientific cache,
actual cancellation, preview production and supported client behavior require
their own evidence. This ADR does not claim those prototypes have passed.

Two later user decisions keep the collaboration boundary small:

- Select a project, save through the native workflow mechanism and associate the
  actual saved file before giving an unsaved canvas to the Agent. Keep native
  temporary drafts; do not add a server-side temporary graph/control lifecycle.
- Share the current graph control state across Agent clients. Another client
  may continue an allowed, online bound target; reads and reconnects never
  restore revoked control. Keep explicit page selection, without a client
  identity, account, role or session authorization system. This replaces the
  previous broader claim that every new client must obtain fresh write rights.
