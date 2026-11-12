# ADR-WORKBENCH-FOUNDATION-0062: Configuration and Lifecycle

Date: 2026-10-27

## Status

Accepted

This records the previously agreed M1 design. It does not record user
acceptance of a candidate implementation or permission to merge it.

## Context

The user needs to verify configuration from the native workbench. Configuration
storage alone cannot demonstrate startup adoption, real addresses, or busy
restart rejection. The existing data UI also owns the HTTP client needed by
this second consumer.

## Decision

- Keep the native canvas mounted and open a configuration dialog in its host.
  The private UI receives the typed client and the host's translator; it does
  not import native stores or introduce another Vue application.
- Move the existing HTTP implementation and error schema to the planned core
  files, as agreed in
  [ADR-WORKBENCH-PLAN-0061](WORKBENCH-PLAN-0061-executable-batches-and-shared-client.md).
  Data imports directly re-export the same error class and implementation.
- Show saved settings separately from startup-adopted settings. Saving neither
  restarts services nor changes the current connection. A conflict preserves
  input; loading the latest values is an explicit action.
- Use the existing local controller, two services and file records. Serialize
  control for one workspace and configuration writes; inspect process identity
  and health before reporting readiness. Explicit stop can reconcile an
  interrupted operation before its unresolved record is replaced.
- Serialize maintenance checks with import and preview admission. Existing
  task records supply busy facts; unavailable native queue observations reject
  restart. Future software and managed workflow occupancy remain in their
  corresponding batches.
- Persist the current maintenance operation ID in the existing running record.
  Close admission before native queue observation. The existing native adapter
  serializes prompt admission and queue observation so an already accepted
  validation cannot be missed. A lost reply releases the same operation only;
  a late release cannot reopen another operation or a shutting-down service.

## Consequences

M1 can be tested from the native page together with explicit CLI restart.
There is no configuration history, online restart endpoint, new service,
resource registry or generic settings framework. A stopped client uses saved
settings; an active managed service uses its startup-adopted address.

Real acceptance uses isolated workspaces during the agreed maintenance window.
Automated evidence does not replace the user's M1 acceptance or current-commit
merge approval. The normal dev source, configuration, data and fixed runtime
must remain recoverable.
