# ADR-PRODUCT-UI-0045: Private Product UI Workspace and Native Bridge

Date: 2026-10-25

## Status

Accepted

## Context

AstroPhotoFlow is a source-based local web product. Its data components were compiled by the native application from a Python source directory, while component tests used a second dependency tree. Future platform capabilities need stable ownership without relocating the upstream application workspace.

## Decision

Keep the complete upstream workspace and add one private source package, `@astrophotoflow/ui`. Its core and module directories mirror product ownership. Only implemented components are exported; documentation placeholders do not register capabilities.

The native application consumes the package entry and owns the integration under `src/platform/astrophotoflow`. The package does not import application stores, graph singletons or internal scripts. Existing props, events and exposed component methods remain the integration contract.

Vue and Pinia resolve from the same locked workspace. Product component tests retain an isolated jsdom setup. Product web output is `.artifacts/build/frontend` relative to the repository; upstream `build/` remains source code.

## Alternatives and Consequences

Placing product components directly in application source would need fewer package files but would mix ownership and test setup. Relocating the whole repository into apps directories would add migration work without defining internal dependencies.

The private package adds a manifest and explicit entry points. In return, module documentation, tests and import checks have a bounded scope. This migration preserves existing component logic and does not implement node hot publishing, external tool execution or Agent workflow coordination.
