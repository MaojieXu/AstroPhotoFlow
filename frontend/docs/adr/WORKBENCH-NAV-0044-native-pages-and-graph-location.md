# ADR-WORKBENCH-NAV-0044: Native Pages and Graph Location

Date: 2026-10-25

## Status

Accepted

## Context

AstroPhotoFlow is a local astronomy product built from the pinned ComfyUI
engine and frontend. Its existing library and settings must become native
pages while retaining the editor and the established domain API.

The first delivery is a browser application. Rewriting the working FastAPI
domain service would expand this migration into a change of validation,
authentication and client contracts. Recreating the graph on every page
transition would discard drafts and viewport state.

ComfyUI's subgraph navigation also writes a route hash. Browser acceptance
reproduced that write appending a graph identifier to a library page URL,
conflicting with the product's hash-based page navigation.

## Decision

- Keep one graph workspace mounted. Register Library immediately after Node
  Library and before Workflows as native Vue sidebar tabs, reusing the existing
  splitter, width controls and close behavior. Library is initially selected.
  Equipment management opens within the Library panel beside its import action.
- Keep FastAPI as an internal domain service behind the engine's same-origin
  gateway. One launcher owns both processes.
- Preserve form drafts by checking the active panel before switching or closing
  it. The graph remains visible and retains its contents and viewport.
- Use one workspace route and keep the graph locator in the `graph` route
  query. Sidebar changes do not perform page navigation.

## Consequences

The product owns the frontend and engine source changes and their version
pairing. Domain clients and stored scientific assets retain their existing
contracts. This delivery provides the editor and queue foundation; managed
astronomy workflows, adapters, Agent control and provenance remain separate
future work. Desktop packaging is outside this delivery.
