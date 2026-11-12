# Local workbench branding handoff

English | [中文](2026-11-08-local-workbench-brand.md)

## Ownership and expiry

The maintainer who resumes local workbench verification owns this handoff. Created November 8, 2026, and expires November 22, 2026. The [frontend](../subsystems/frontend.en.md) and [release](../release.en.md) docs own the durable facts, and the [branding and entry points note](../../.agents/notes/implemented/simplification/2026-11-08-local-workbench-brand-and-entrypoints.md) owns the decision.

## Current state

The branding and local entry point cleanup (`fab5e835`) and the single-row library and equipment toolbars (`8fcbf51f`) were pushed to `origin/dev`. Other uncommitted changes remain in the local working tree.

## Verification and next action

The commit candidate passed 651 frontend tests, three production browser regressions, type checking and the docs gate. The wheel installed outside the candidate source directory, and the sdist rebuilt without Node. Verification records are in `.artifacts/reports/dev-push-fca4301f/`, with the packaging results in `features-packaging.json`.

The full Siril regression failed. Node registration, real processing and definition updates passed before Windows returned `EPERM` while renaming the test checkout in the isolated workspace. See `.artifacts/reports/apf-brand-bundle/results.json` and the `rename(checkout, retired)` step in `tests/browser/bundle-hot-reload.spec.ts`.

When a complete regression receipt is needed, rerun the test in a fresh isolated workspace with the same Siril source checkout. If it fails again, identify the handle holding the directory before treating the failure as transient. Record durable findings in the test receipt and remove this handoff and its pair registration when resolved.
