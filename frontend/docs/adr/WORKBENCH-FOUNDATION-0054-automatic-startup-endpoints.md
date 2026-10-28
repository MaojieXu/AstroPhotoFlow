# ADR-WORKBENCH-FOUNDATION-0054: Discover Available Workbench Endpoints at Startup

Date: 2026-10-27

## Status

Accepted

This accepts the product direction. MCP startup, automatic port selection and
discovery of actual endpoints are not yet implemented or verified.

## Context

The workbench uses separate local ports for the native web application and the
domain service. Today the launcher reads both from configuration and reports
an error when a required port is occupied; existing data MCP operations access
the domain service over HTTP and do not start it.

The user wants an external Agent to request startup through AstroPhotoFlow MCP
and receive the actual web address, without manually finding available ports.
The same workspace may already be running, and another program or workspace may
be using one of its configured ports.

## Decision

- Check the target workspace and reuse its existing services only after their
  identity and health are verified. An unrelated or unidentified process is not
  evidence that this workspace is ready.
- When a needed port is occupied by another program or workspace, automatically
  select an available port. The web and domain services use different ports.
  Return the actual web address and make the domain address available to the
  gateway, CLI and MCP so their business requests reach the same workspace.
- Keep requested configuration separate from the actual addresses associated
  with a successful startup. The gateway's allowed local origins must agree
  with the actual web address; selecting a port does not authorize arbitrary
  origins. Saving settings does not itself restart a running workbench. Display
  the actual address and the reason when it differs.
- Expose startup through a future local MCP lifecycle capability that can use
  the workbench controller while the domain service is offline. Business requests
  still use the shared HTTP service; this is not an arbitrary shell capability
  or a new resident control service.
- Verify actual binding, process identity and service health before reporting
  readiness. A scan of an unused port is not a reservation or a success receipt.

## Alternatives

Failing on every occupied configured port keeps address selection simple, but
requires the user or Agent to resolve routine collisions manually. Always opening
a second workbench when the target is already healthy risks duplicate processes
and inconsistent workspace state.

## Consequences

Candidate-port order, coordination under concurrent binding, whether to persist a
newly selected port as configuration, the local control protocol and the exact
layout and concurrency mechanism for control records remain for data and interface
design. The user selected file-based public control records; existing business
data continues to use SQLite. Existing configuration, MCP registration and
runtime behavior are unchanged by this ADR.

The [foundation design](../../../src/astrophotoflow/core/README.md#behavior)
and [data draft](../../../docs/architecture/data-models/01-foundation.md#processes)
track the behavior and its future acceptance conditions.
