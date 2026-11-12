# Contributing

English | [中文](CONTRIBUTING.md)

Create branches from `dev`, verify changes locally, and merge them into `dev`. Repository-wide conventions are in [AGENTS](AGENTS.md), documentation rules in [docs/AGENTS](docs/AGENTS.md), validation in [Testing](docs/testing.en.md), and release steps in [Release](docs/release.en.md).

## Branches and commits

- The integration branch is `dev`; every change starts from the current `dev`.
- Commits, merges, pushes, and pull request creation follow user authorization.
- Keep each commit to a single purpose and exclude unrelated formatting, refactoring, or renames.
- Before committing, read the `AGENTS.md`, code, and tests near the change.
- Name branches after the change topic, not after old module names or historical task names.

## Integration into `dev`

- Before merging, sync with the latest `dev`, run the checks that apply to the change, and record the results.
- Once the checks pass, merge the feature branch into `dev` locally. A pull request and independent approval are optional.
- After merging locally, push `dev` when authorized. See [Testing](docs/testing.en.md) for the check workflow.

## Release pull request review and merge

- Use `.github/pull_request_template.md` for the release pull request and describe the changes and actual validation results.
- A release pull request requires approval from one independent reviewer. The reviewer judges from the requirements and the diff.
- Reviewers raise findings and do not edit the code; after changes, authors ask reviewers to recheck the affected parts.
- Merge only after all required checks pass and approval is recorded.

## Check commands

| Check | Command |
| --- | --- |
| Documentation gate | `pnpm check:docs` |
| Python tests | `uv run --locked --no-sync pytest -q` |
| Frontend unit tests | `pnpm test` |
| Build | `pnpm build` |
| Distribution verification | `python scripts/verify_distribution.py` |

Add browser tests, packaging, and architecture boundary checks according to the change scope; see [Testing](docs/testing.en.md).

## Branch protection

GitHub repository administrators configure these rules in the repository settings.

- `dev` allows authorized regular pushes to receive changes integrated locally.
- `main` is updated through release pull requests and requires at least one approval and the `all checks passed` status check.

## AI usage declaration

- Fill in the release pull request's AI usage section for breakdown, design, testing, implementation, and review.
- Mark the assistance level for each stage: `none`, `assisted`, `generated`.
- Declare only real usage; write `none` for unused stages instead of omitting them.
- Generated content is the submitter's responsibility and is still verified and reviewed under this guide.

## Release

- Releases are development versions only, `X.Y.Z-dev.N`; the version source and build steps are in [Release](docs/release.en.md).
- `main` only receives release pull requests from `dev`; merging into the main branch, tagging, and public release require separate user authorization.
