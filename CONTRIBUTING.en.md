# Contributing

English | [中文](CONTRIBUTING.md)

This repository creates branches from `dev` and opens pull requests against `dev`. A change must pass the documentation gate, product checks, and approval by one independent reviewer; releases are development versions only, `X.Y.Z-dev.N`, and `dev` → `main` goes through a release pull request. Repository-wide conventions are in [AGENTS](AGENTS.md), documentation rules in [docs/AGENTS](docs/AGENTS.md), validation in [Testing](docs/testing.en.md), and release steps in [Release](docs/release.en.md).

## Branches and commits

- The integration branch is `dev`; every change starts from the current `dev`.
- Never push directly to `dev` or `main`; push and pull-request creation follow user authorization.
- Keep each commit to a single purpose and exclude unrelated formatting, refactoring, or renames.
- Before committing, read the `AGENTS.md`, code, and tests near the change.
- Name branches after the change topic, not after old module names or historical task names.

## Pull requests

- The pull request targets `dev`; describe the change using `.github/pull_request_template.md`.
- Motivation states the problem, issue, or scenario; the change list is grouped by module.
- The validation section lists only commands and results actually executed; explain any check not run.
- Put full logs under `.artifacts/reports` and link their paths instead of pasting them.
- Documentation changes state which layer was updated and whether `.i18n.yaml` was re-recorded.

## Review and merge

- Every pull request requires approval from one independent reviewer; the reviewer does not inherit the author's context and judges from the requirement and the diff alone.
- Reviewers raise findings and do not edit the code; after changes, authors ask reviewers to recheck the affected parts.
- Merge only after all required checks pass and approval is recorded.
- Delete the branch after merging and start the next change from the latest `dev`.

## Required checks

| Check | Command |
| --- | --- |
| Documentation gate | `pnpm check:docs` |
| Python tests | `uv run --locked --no-sync pytest -q` |
| Frontend unit tests | `pnpm test` |
| Build | `pnpm build` |
| Distribution verification | `python scripts/verify_distribution.py` |

Add browser tests, packaging, and architecture boundary checks according to the change scope; see [Testing](docs/testing.en.md).

## Branch protection

GitHub repository administrators configure `dev` and `main` manually in the repository settings:

- Direct pushes are disabled; all changes merge through pull requests.
- At least one approval is required before merging.
- The required status check is `all checks passed` (CI aggregates the docs and product jobs).
- Administrators keep an emergency override; the normal flow performs no exception merges.

## AI usage declaration

- Fill in the AI usage section of the pull request by stage: breakdown, design, testing, implementation, review.
- Mark the assistance level for each stage: `none`, `assisted`, `generated`.
- Declare only real usage; write `none` for unused stages instead of omitting them.
- Generated content is the submitter's responsibility and is still verified and reviewed under this guide.

## Release

- Releases are development versions only, `X.Y.Z-dev.N`; the version source and build steps are in [Release](docs/release.en.md).
- `main` only receives release pull requests from `dev`; merging into the main branch, tagging, and public release require separate user authorization.
