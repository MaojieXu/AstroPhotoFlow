# Testing and validation

English | [中文](testing.md)

Test layers cover documentation, Python, architecture, frontend, browser, and distribution; local runs and CI use the same command set. Implementation, automated validation, real execution, and user acceptance are reported separately and never substitute for one another.

## Test layers

| Layer | Scope | Entry point |
| --- | --- | --- |
| Documentation | Budgets, pairing, line wrapping, links, and notes/skills checks, plus gate behavior | `pnpm check:docs`; `pytest tests/docs` |
| Python | Unit, module, interface, integration, core, and packaging layout | `uv run --locked --no-sync pytest -q` |
| Architecture | Python import boundaries and frontend dependency direction | `pnpm check:boundaries` |
| Frontend | Unit tests for the UI package and native bridge | `pnpm test` |
| Browser | Playwright end-to-end tests against real services | `pnpm test:browser` |
| Distribution | wheel/sdist resources, out-of-repository install, and a Node-free rebuild | `python scripts/verify_distribution.py` |

## Gates and CI

- The `docs` job runs `pnpm check:docs` and `pytest tests/docs` on ubuntu.
- The `product` job builds the frontend on an ubuntu and windows matrix, discovers browser test cases, runs Python and frontend tests, and builds and verifies the distribution.
- The `checks` job aggregates both, with the status name `all checks passed` referenced by branch protection.

## Writing receipts

- Before merging into `dev`, record the commands run and their results in the handoff summary. For a release pull request, use the Testing section. Explain any relevant checks that were skipped.
- Put full logs under `.artifacts/reports`, for example `python.xml`, `browser/`, and `packaging.json`.
- Report implementation, automated validation, real execution, and user acceptance separately; they never substitute for one another.
- Do not rerun checks that already passed; add affected checks after the change scope changes.

## Browser test boundaries

- Browser tests run only against a locally chosen workspace: `APF_WEB_URL` must be a loopback address and must point to the same workspace as `APF_TEST_WORKSPACE`; the shared `dev` and `default` workspaces are rejected.
- CI only runs `pnpm test:browser --list` to discover cases and does not start services.
- The default config runs the native web page, layout, and workbench settings cases; `pnpm test:browser:modernization` and `pnpm test:browser:native` are separate configs chosen by change scope.
- Reports go to `.artifacts/reports/browser/`; parallel or per-worktree runs set `APF_BROWSER_REPORT` to a dedicated subdirectory under that directory.
- The worker count is 1 and failures are not retried automatically; failures keep traces and screenshots, and native queue or restart scenarios that are not explicitly enabled are reported as skipped, not passed.

## Validation boundaries

- Automated tests prove implementation and contracts; real execution proves service, engine, and native page state; users complete user acceptance on real assets and the workbench.
- Never report previews, synthetic probes, or skipped scenarios as passing.
- Packaging validation must install outside the repository and rebuild the wheel in an environment without Node.
