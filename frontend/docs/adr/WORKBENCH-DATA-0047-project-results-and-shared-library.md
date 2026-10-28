# ADR-WORKBENCH-DATA-0047: Keep Project Outputs Scoped and Share Reusable Results Explicitly

Date: 2026-10-26

## Status

Accepted

This accepts the product and architecture direction. Project result registration,
result collections and explicit sharing remain unimplemented.

## Context

The existing library imports shared assets and projects reference fixed versions.
Asset models already represent project scope, but shared collections accept only
shared assets. These foundations do not implement managed workflow output
registration or project result collections.

Processing can create many calibrated and registered frames. Listing all of them
in the shared library would mix working data with reusable scientific products.
The user chose project-local intermediate frames and optional sharing for stacked
images, master calibration frames and final products.

## Decision

- Keep intermediate calibrated and registered frames within their project.
- Default stacked images, master calibration frames and final products to their
  producing project. Let the user explicitly add them to the workspace-wide
  library for other projects to reference fixed versions.
- Preserve stable identity, versions, producing project and run provenance.
  File extensions do not determine sharing, and sharing does not establish
  scientific suitability for every project.
- Treat retention and sharing as separate choices. Not sharing an intermediate
  result does not authorize automatic cleanup.
- Keep asset authority in the data module and execution facts in run management.
  The private UI consumes public HTTP capabilities; host canvas coordination
  remains in the native bridge.
- Preserve the existing shared import behavior. Define project collection scope,
  sharing and reference protection in subsequent data and interface design.

## Alternatives

Making every output shared would reuse the current import organization, but would
expose large intermediate batches in the global library and conflict with the
chosen project workflow.

Keeping every result permanently project-only would simplify scope, but would
prevent the chosen explicit reuse of master frames and retained products.

Automatically sharing by extension or processing step would hide user intent.
A FITS file can be an intermediate or a retained product, and sharing is not a
cleanup instruction.

## Consequences

No API, schema, storage migration, UI component or runtime behavior is added by
this ADR. The [data module outline](../../../src/astrophotoflow/modules/data/README.md#flows)
owns the detailed responsibilities and acceptance scenarios. Existing project
scope fields are not evidence of a completed result lifecycle.
