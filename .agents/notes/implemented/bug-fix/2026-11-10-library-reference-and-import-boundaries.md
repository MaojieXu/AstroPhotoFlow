# Agent Note: Enforce current library ownership and import boundaries

Status: Implemented

## Problem

Materials could acquire multiple dataset owners. Cleanup detached unrelated references and omitted software and export readers. Trash objects could gain new relationships, classification edits could invalidate existing calibration, and deleting equipment changed material metadata without advancing its revision. Project imports lacked association and publication repair paths.

## Decision

Each independent import stores its own managed original. Dataset membership has a global asset uniqueness constraint and shared validation. External references block permanent cleanup. Cleanup uses existing task admission and concrete software and export observations. Metadata writes validate affected calibration structure transactionally. Equipment deletion preserves import snapshots and advances each affected material once, with a persisted update time.

Imports explicitly select independent materials, a new dataset or append. Their task reports retain project identity, revision and association outcome. Successful originals can be organized or associated through existing operation receipts. Uncertain direct import acceptance is queried by request ID. Capture differences are warnings, with an inclusive one-degree group temperature range. Dataset details and JSON expose differences, unknown counts and referencing projects.

## Alternatives considered

Shared originals and implicit dataset creation from file count were rejected following the user's ownership and interaction decisions. Automatic removal of external references would widen the selected deletion scope. Adding a history model or a separate recovery ledger would duplicate current records.

## Consequences

The fresh database baseline includes exclusive member ownership and material update time. Existing development databases require baseline initialization without migration. Runtime behavior awaits the separately deferred automatic tests and end-to-end acceptance. Static checks and frontend build are recorded in the task delivery receipt.
