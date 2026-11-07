# Library

English | [中文](library.md)

Asset, dataset, project reference, equipment, calibration, checked result and trash behaviour belongs to the data module; module responsibilities and data ownership are in [architecture](../architecture.en.md), and product rules are in [data product requirements](../product/data.en.md).

## Assets and fixed versions

- An asset has a stable identity, versions and a revision; parameters distinguish omitted, explicit null and zero, and a stale revision is rejected instead of overwritten.
- A dataset version fixes member scope and order; editing only adds or removes explicit members, keeps the remaining order and calibration bindings, and never deletes asset originals.
- Project references fix an asset or dataset version and do not link workflow files; a project that selected an older version keeps it.
- Registration, original availability, metadata and preview are expressed separately, and a preview never becomes scientific input.

## Equipment and setups

- Devices are cameras, telescopes, filters and mounts; optical accessories are maintained inside a telescope rather than as a device category.
- A setup holds at most one camera, telescope and mount plus several filters; inline members are not registered automatically, and a setup is only a selection shortcut, not an import prerequisite.
- Import acceptance freezes equipment details into a version snapshot; editing or deleting equipment does not rewrite snapshots, and permanent deletion only clears the foreign key.
- Exposure, gain, offset and measured temperature belong to the image, come from headers or explicit user confirmation, and are not overwritten by an equipment association.

## Calibration

- Dataset defaults and member overrides are saved with the dataset version; a missing key on a member means inherit, explicit null means do not use, and an object means override.
- Targets are fixed master calibration asset versions or calibration dataset versions for the matching use; the platform does not match automatically, run calibration or produce masters.
- A master light is a light frame; the calibration library and the light view are independent, and frames of unknown use remain reachable from all assets.
- Light accepts dark, flat and bias, flat accepts bias and dark flat, and dark and dark-flat accept bias.
- A relation-only change also publishes a new dataset version; member changes and appends keep old defaults and overrides of unaffected members.
- The dataset exposure summary adds up only subframe `exposure_seconds`, without integration time or masters, and separates known from unknown counts.

## Results and exports

- Checked results live in `src/astrophotoflow/modules/data/results/`; a Data node reads a fixed `APF_SCIENCE` reference or a native IMAGE input, a connected input wins, and conflict fails explicitly.
- `APF_FILE_REFERENCE` hands over bad-pixel tables, ICC profiles, comparison-star CSV, WCS and scripts without pretending they are scientific images.
- An export copies the full container by default; an explicit format or precision affects the copy only, with no implicit normalisation, clipping or RAW development, and a preview JPEG is not scientific input.

## Trash and original protection

- Removal, restore and permanent cleanup are separate operations; cleanup first previews reference impact and returns a fingerprint, and only a confirmed selection with the same fingerprint is executed.
- A changed revision or impact returns a conflict and is never retried automatically or widened; the filesystem and database are not one transaction, so partial failures keep the failed entries.
- Calibration references and in-progress large-image generation take part in the cleanup checks; a target still referenced by a retained dataset version cannot be cleaned up.
- When a consumer and its target are selected together, the target is kept first and becomes an independent retryable record; there is no recursive retry.

## External contracts

- HTTP routes are in `src/astrophotoflow/interfaces/http/data/` (assets, datasets, projects, equipment, calibration, results, exports and trash).
- Contract models are in `src/astrophotoflow/contracts/`; fields follow the [OpenAPI snapshot](../api/openapi.json), and query entry points are in [references](../references.en.md).
- The public entry point is `src/astrophotoflow/modules/data/public.py`; other modules never read this module's private ORM.

## Tests

`tests/modules/data/`.
