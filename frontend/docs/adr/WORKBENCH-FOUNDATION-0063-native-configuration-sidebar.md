# ADR-WORKBENCH-FOUNDATION-0063: Native Configuration Sidebar

Date: 2026-10-28

## Status

Accepted

## Context

The M1 configuration dialog was accessible from a floating toolbar button.
The user requested the same navigation and appearance as the native node,
asset and workflow sidebars.

## Decision

Register configuration after workflows using the native sidebar extension
and SidebarTabTemplate. Remove the floating button and dialog. The shared
sidebar owns resizing, switching and closing; the existing private form owns
configuration loading, saving and conflict display. Use native semantic theme
tokens and a single-column layout suitable for the sidebar width.

This supersedes only the dialog placement in
[ADR-WORKBENCH-FOUNDATION-0062](WORKBENCH-FOUNDATION-0062-configuration-and-lifecycle.md).
Configuration and lifecycle behavior remain the same.

## Consequences

The canvas remains mounted and visible during configuration editing. There is
no second settings framework, modal or connection. Native design components
and repository tokens supply the reference because live Figma access is not
available in this environment. Candidate implementation still requires human
M1 acceptance.
