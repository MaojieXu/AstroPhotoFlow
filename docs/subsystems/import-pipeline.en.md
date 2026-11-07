# Import pipeline

English | [中文](import-pipeline.md)

Registers local files or uploaded content as assets, stores originals and generates previews. The implementation lives in the data module's import pipeline (`src/astrophotoflow/modules/data/imports/`); module responsibilities and data ownership are in [architecture](../architecture.en.md).

## Responsibilities

- Accept an import, fix the file list and source observations, and create assets, versions and logical datasets.
- Store originals: copy and hash managed sources, or hash and atomically place uploaded files.
- Write header metadata, classification, equipment and calibration snapshots, then generate previews once originals are available.
- Report per-stage progress through the task report, with cancellation, recovery, retry and publication-only retry.

## Inputs

- An absolute file list submitted by the web page; a folder contributes only supported files at its top level, not a recursive tree.
- A relative path list with `root_id`, and staged files from the upload endpoints.
- Optional classification, parameters, target dataset and calibration input; omitted keys fall back to file observations, the preset frozen at acceptance, then unknown.

## Stages and states

Registration reads only FITS/XISF headers and establishes identity; it does not hash, copy or decode images. A pending version has `availability=unknown` and `content_status=pending`, and becomes available only after the original is fully hashed and placed. Registration, content, metadata and preview states are recorded separately, and the task reaches a terminal state only after every stage finishes.

- A managed source is hashed and copied to a staging file in one read, then atomically placed under `objects/<version-id>/`.
- An uploaded file is already staged; the background run only hashes it and moves it atomically into objects.
- An external source keeps the size and mtime observed at registration; a change between reads returns `SOURCE_CHANGED` and publishes the version as changed without partial copies.
- Cancellation removes unpublished partial copies; recovery and retry reuse the original asset and version identities instead of registering again.

## Report and failures

The task report has three parts, `report.registration`, `report.content` and `report.preview`; `bytes_copied` counts copied bytes only and does not mean verified usable bytes, and 100% registration does not mean the batch has finished.

- Metadata failures are counted as `metadata_failed` and do not affect the usability of published originals.
- Import tasks share the service-level file thread pool and priority preview executor, which drain on shutdown; a task reaches a terminal state only after its own content and preview stages end.
- A preview failure does not affect the scientific original; compatible subframes of the same Object share a reference-frame recipe in fixed order, while masterframes are computed independently.

## Classification and snapshots

Classification follows explicit headers only and never the file name. Parameter precedence is an explicit non-empty manual value, a file observation, the preset frozen at acceptance, then unknown; zero is a valid value. The setup, preset and equipment details are frozen at acceptance, retries and recovery reuse that snapshot, and background runs do not rewrite manual data.

## External contracts

- HTTP routes are in `src/astrophotoflow/interfaces/http/data/imports.py`, `inspection.py` and `previews.py`.
- Tasks, reports and error codes are in `src/astrophotoflow/contracts/imports.py`; fields follow the [OpenAPI snapshot](../api/openapi.json).
- The web page, CLI and MCP use the same routes; CLI and MCP conventions are in [references](../references.en.md).

## Tests

`tests/modules/data/test_import_pipeline.py`, `test_ingestion.py` and `test_equipment_snapshots.py`.
