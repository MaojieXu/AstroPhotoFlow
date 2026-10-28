# ADR-WORKBENCH-FOUNDATION-0046: Reuse Native Progress and Verify Platform Status Bridging

Date: 2026-10-26

## Status

Accepted

This accepts the design direction. Cross-process platform status bridging and
standard node hot publication remain unimplemented and require verification.

## Context

AstroPhotoFlow keeps the native canvas and queue in the browser application.
The pinned frontend already receives execution progress and custom events through
its WebSocket client. Domain state lives in a separate FastAPI service, so those
native facilities do not demonstrate delivery of domain changes or canvas
acknowledgements.

The user chose native reuse before an additional platform notification channel.
The product must preserve module authority, unsaved drafts and explicit receipts
while supporting both browser and external MCP clients.

## Decision

- Reuse native execution progress and display. Actual external software progress
  comes from the software adapter and managed run; report phases when no measured
  percentage is available.
- Verify the minimum controlled bridge from domain changes to the existing native
  connection before selecting another notification channel.
- Keep native event, Store and canvas adaptation in the product host bridge.
  The private UI package consumes public capabilities and does not import native
  application internals.
- Treat messages as change hints. Query authoritative module state after a hint
  or reconnection; version commit, canvas display and run completion remain
  separate receipts.
- Verify workspace and target routing, authorization, reconnection and preservation
  of drafts before claiming platform synchronization. Node definition refresh
  does not prove backend publication or implementation version isolation.

## Alternatives

An independent domain notification connection could avoid forwarding through the
engine but adds a connection, authentication and reconnection lifecycle. Reconsider
it only when the native bridge has an observed limitation.

Polling remains an existing data-module behavior. It does not establish the
target workflow synchronization or justify a new common polling framework.

A durable replayable platform event store was not selected. Domain modules retain
their own versions and execution facts; the common layer must not duplicate them.

## Consequences

No transport, API or code is added by this ADR. The
[foundation design](../../../src/astrophotoflow/core/README.md#behavior) owns the
module outline and acceptance gates. Subsequent data and interface design will
define the actual handoff after the cross-process prototype establishes feasibility.
