# Library

English | [中文](library.md)

Asset, dataset, project reference, equipment, calibration, checked result and trash behaviour belongs to the data module; module responsibilities and data ownership are in [architecture](../architecture.en.md), and product rules are in [data product requirements](../product/data.en.md).

## Assets and datasets

- An asset has a stable asset_id and one registered original, with revision for metadata edits; parameters distinguish omitted, explicit null and zero, and a stale revision is rejected instead of overwritten. Changed original content blocks scientific reads until the registered content is restored or the changed file is imported again.
- A dataset stores its current ordered members under dataset_id. Editing adds or removes explicit members, preserves the remaining order and calibration bindings, and keeps originals when members are removed.
- Projects reference asset and dataset identities. Dataset edits apply to all references, and each call fixes its actual inputs when it starts.
- Registration, original availability, metadata and preview are expressed separately, and a preview never becomes scientific input.

## Disk layout and manifests

- `data/library/` has a fixed matrix of purpose, Subframe/MasterFrame and the three calibration statuses. Unknown purposes use Unclassified, and other forms use its Other branch. Rules live in `src/astrophotoflow/modules/data/library/layout.py`.
- Each dataset uses a `<数据集名称>__<设备与拍摄参数>__<短ID>` directory containing imported files and the fixed `dataset.json` directly. An asset belongs to at most one dataset. The manifest records its ID and library-relative original path. Directory labels use the first current member, while JSON exposes all capture differences and unknown counts. Standalone subframes and Masters have independent directories. Master condition directories omit filter fields for Dark/Bias/DarkFlat.
- Names retain original filenames and meaningful decimals for measured temperature and exposure, with UNK for unknowns. Short IDs grow from eight characters until unique. Windows invalid characters, reserved names, path lengths and link boundaries are checked centrally.
- SQLite stores current facts. After database commit, JSON is published atomically with ordered members, state evidence, pending Masters and executed-processing summaries. Publication failures retain committed facts and expose pending or failed state. Rebuilding publishes current database facts at revision.
- Metadata edits save to the database first. Explicit organization preflights all moves, hashes, conflicts and active tasks, executes using the reviewed token and saves per-file receipts. A new file entry is established and its actual position committed before the old entry is cleaned up. Interrupted work checks original identity, and uncertain outcomes are queried by request ID.

## Equipment and setups

- Devices are cameras, telescopes, filters and mounts; optical accessories are maintained inside a telescope rather than as a device category.
- A setup holds at most one camera, telescope and mount plus several filters; inline members are not registered automatically, and a setup is only a selection shortcut, not an import prerequisite.
- Import acceptance freezes equipment details into an import snapshot; editing or deleting equipment does not rewrite snapshots, and permanent deletion only clears the foreign key.
- Exposure, gain, offset and measured temperature belong to the image, come from headers or explicit user confirmation, and are not overwritten by an equipment association.

## Calibration

- A dataset stores one current calibration binding per purpose. Scientific input resolution applies the same configuration to every subframe in the group.
- A binding targets a Master asset that matches the slot. A raw dataset can be recorded as a Master source. Users explicitly select the target, and saving a binding records only the relationship. Standalone calibration and user-declared Master sources store current state. Calls already started retain the relationships and metadata they actually used.
- A master light is a light frame; the calibration library and the light view are independent, and frames of unknown use remain reachable from all assets.
- Light accepts dark, flat and bias, flat accepts bias and dark flat, and dark and dark-flat accept bias.
- Calibration changes update the current dataset and increase revision. Appending checks the current bindings and returns capture differences as warnings. Started calls retain their original input snapshots.
- The dataset exposure summary adds up only subframe `exposure_seconds`, without integration time or masters, and separates known from unknown counts.

## Results and exports

- Checked results live in `src/astrophotoflow/modules/data/results/`; a Data node reads a fixed `APF_SCIENCE` reference or a native IMAGE input, a connected input wins, and conflict fails explicitly.
- `APF_FILE_REFERENCE` hands over bad-pixel tables, ICC profiles, comparison-star CSV, WCS and scripts without pretending they are scientific images.
- An export copies the full container by default; an explicit format or precision affects the copy only, with no implicit normalisation, clipping or RAW development, and a preview JPEG is not scientific input.

## Trash and original protection

- Removal, restore and permanent cleanup are separate operations; cleanup first previews reference impact and returns a fingerprint, and only a confirmed selection with the same fingerprint is executed.
- A changed revision or impact returns a conflict and is never retried automatically or widened; the filesystem and database are not one transaction, so partial failures keep the failed entries.
- References from projects, datasets, calibration or provenance outside the selected scope block cleanup and appear in the preview. Cleanup shares task admission with software calls, exports and organization and checks actual inputs and supporting calibration.
- Objects in trash cannot gain new project, member, calibration or declared provenance relations. Metadata edits validate affected calibration structure transactionally and report consumers and slots on failure. Equipment deletion preserves import snapshots and advances each affected asset revision and update time once.

## External contracts

- HTTP routes are in `src/astrophotoflow/interfaces/http/data/` (assets, datasets, projects, equipment, calibration, results, exports and trash).
- Contract models are in `src/astrophotoflow/contracts/`; fields follow the [OpenAPI snapshot](../api/openapi.json), and query entry points are in [references](../references.en.md).
- The public entry point is `src/astrophotoflow/modules/data/public.py`; other modules never read this module's private ORM.

## Tests

`tests/modules/data/`. See [testing](../testing.en.md) for the real-material suite and commands.
