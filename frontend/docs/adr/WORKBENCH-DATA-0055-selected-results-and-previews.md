# ADR-WORKBENCH-DATA-0055: Save Selected Results and Workflow Previews

Date: 2026-10-27

## Status

Accepted as product direction; implementation remains pending.

## Context

ADR-WORKBENCH-DATA-0047 classified intermediate frames as project-only and proposed project result registration and explicit sharing. The user instead selects the specific images worth keeping, regardless of processing stage. Existing imported assets, their references and scientific input protections remain unchanged.

## Decision

- Save a complete result to the workspace library only when the user selects it; allow a name or use a default name. Do not require a separate project result group or detailed provenance display.
- Retain multiple compressed canvas previews with the workflow; delete previews dedicated to a deleted workflow. Full intermediate files are not intended for long-term retention.
- Execution still uses actual scientific inputs and records the parameters and facts needed by the run. Preview images do not replace scientific files.
- Reuse existing asset and collection behavior; result saving and workflow previews are future capabilities, not current implementation.

## Consequences

This supersedes the intermediate-frame sharing restriction in ADR-WORKBENCH-DATA-0047 without changing that historical record. Storage format, preview count and cleanup policy are not fixed here. Scientific files chosen by the user and existing import, calibration and cleanup protections remain separate from canvas previews.
