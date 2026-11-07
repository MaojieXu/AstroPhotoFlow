# Release

English | [中文](release.md)

Releases are development versions only, `X.Y.Z-dev.N`, with the sole version source in `project.version` of `pyproject.toml`. Build artifacts are a wheel and an sdist that carry the web output and the pinned engine; tags are created manually.

## Version numbers

- The version is read only from `project.version` in `pyproject.toml`; packaging and metadata both use that field.
- Only `X.Y.Z-dev.N` development versions are released, with `N` increasing; no separate version numbers are introduced in docs or scripts.
- `main` only receives release pull requests from `dev`; merging into the main branch and tagging require separate user authorization.

## Build

From the repository root in a prepared environment, run:

```powershell
uv run --locked --no-sync python scripts/build_release.py
```

- The script requires Node and pnpm on PATH; it installs frontend dependencies from the lock file, builds the frontend, and then calls `python -m build`.
- The wheel carries the web output and the pinned engine archive, so users need no Node after installation.
- Artifacts go to `.artifacts/dist` and Python intermediates to `.artifacts/build/python`; the script confirms that both the wheel and the tar.gz exist and fails when either is missing.

## Distribution verification

After building, run:

```powershell
uv run --locked --no-sync python scripts/verify_distribution.py
```

- It verifies required wheel resources: the web page, pinned engine archive and hash, route inventory, bundle catalog, database migrations, and product modules.
- It installs the wheel in a temporary environment outside the repository and smoke-tests the CLI, imports, and database migration.
- It unpacks the sdist, rebuilds the wheel in a Node-free environment, and verifies it again.
- The report defaults to `.artifacts/reports/packaging.json`; `--dist`, `--report`, `--rebuilt-wheel-dir`, `--temp-dir`, and `--sdist-build-python` change paths and the rebuild interpreter.

## Release flow

- Open a release pull request from `dev` to `main`, using the same CI gate and one independent reviewer.
- After merging, a human creates the tag on the release commit; pushing the main branch, tagging, and public release require explicit user authorization.
