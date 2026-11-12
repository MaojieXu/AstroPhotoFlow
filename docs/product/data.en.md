# Assets, equipment and calibration

English | [中文](data.md)

The asset library holds the science files users import and their traceable metadata. Asset identity, current datasets, equipment snapshots and calibration relations are maintained by the data capability; this page states what users need and which product rules must hold. Concrete behavior and interfaces are in the [library subsystem](../subsystems/library.en.md) and [references](../references.en.md).

## Assets and datasets

- Every file gets a stable asset identity at import; later name, thumbnail or metadata updates do not change it.
- Each asset has one registered original referenced by asset_id. A dataset stores its current ordered members under dataset_id, and appending preserves the order of existing members.
- New runs use corrected metadata and record it; old runs do not change because metadata was updated.
- Import can save a standalone asset, create a subframe dataset, or append to a specified dataset. Datasets contain assets explicitly classified as subframes. Master frames are saved independently.
- Successful members and their relations are published together; failed members keep their identity and are reported separately.
- Users or Agents submit ordered member lists. The platform displays differences in purpose, equipment, readout mode, ISO/Gain/Offset, temperature, exposure, filter, Binning and optical configuration. A group temperature range up to and including 1°C matches. Larger ranges and other capture parameter differences produce warnings and allow saving and processing. Capture time, filename and sequence may differ. Unknown facts remain unknown, and differences in filter labels and observed device names remain visible.
- Every import registers an independent asset and copies its original. An asset ID belongs to at most one dataset. Removing a member retains its original and permits later assignment to another dataset. Asset trash handles original cleanup.

## Import

- Users pick local files or a folder in the web app; a folder contributes only files in formats supported at the current level, with no authorization root to configure first.
- The registration stage reads file headers and structural facts and fixes member order; originals are copied and integrity-checked; registration, original readability, parsing and previews are reported separately, and a partial failure never hides successes.
- The main progress follows original bytes and successful count; registration finishing does not mean the batch is done, and background previews continue once originals are ready.
- The background fills in 100-pixel long-edge thumbnails for images that can be previewed automatically: one collection shares fixed first-frame parameters, standalone images are computed separately; large images are prepared on demand per viewport and cached.
- A preview failure does not block the original from entering the library, and no image quality analysis is performed.
- If the source changes before or after reading, the import reports that the source changed and keeps availability, publishing no partial copy; the user confirms the current source and imports again.
- Classification and capture metadata keep raw observed values, mark unknown as unknown and never guess from file names; a non-empty manual value wins over file observation, which wins over the preset frozen at acceptance, and the number 0 is valid; before importing, an external Agent summarizes grouping, equipment, calibration and open questions for user confirmation, while knowledge or web material may only form pending suggestions and the user may keep unknown.

## Equipment and equipment setups

- Equipment kinds are camera, telescope, filter and mount; the library holds "my equipment" and "equipment setups", with no separate shooting preset.
- A setup is an optional shortcut, not an import prerequisite; import can select devices directly, or select a setup and then state the filters and accessories actually used, without guessing from multiple filters.
- A setup contains at most one camera, one telescope and one mount, and may contain several filters with the full list; members filled in inline are not registered to the equipment library automatically; each use selects one setup or none.
- A telescope keeps an optical accessory list whose entries have only a name and a positive multiplier; effective focal length equals native focal length times the selected accessory multiplier, and historical snapshots do not follow later accessory edits.
- A camera keeps only pixel size and pixel arrangement, which expresses mono or a concrete array; unspecified is not the same as mono.
- A filter records its actual name, a free-text Channel and an optional bandwidth; the web app offers no channel options, unknown channels are not guessed, and wavelength or bandwidth is never invented from labels.
- A mount records only name, model, notes and status, with no hardware control; an image explicitly applies and freezes equipment metadata, and the mount is not a calibration adaptation condition.
- Exposure, Gain, Offset and measured temperature belong to each image; associating equipment does not override capture metadata.
- Editing or deleting equipment and setups does not rewrite historical snapshots; deletion first prechecks actual reference impact and returns a fingerprint, then executes the same selection after confirmation, and a revision or impact change is a conflict, never an automatic retry or wider scope.
- Deleting equipment cleans up the corresponding members in current setups and keeps the identity and order of other members, without switching to another device or filter; deleting a setup does not delete standalone devices, images or science originals.

## Calibration

- Edit calibration in the project dataset details and view current targets in the asset table. Unconfigured and explicitly unused slots are distinct.
- Each dataset stores one current calibration configuration shared by all members, with at most one Master asset per purpose. Keep subframes that require different calibration in separate datasets. A standalone image stores its current calibration settings.
- Every slot is optional: Light may take Dark, Flat or Bias; Flat may take Bias or Dark-flat; Dark and Dark-flat may take Bias; not all slots must be configured.
- A binding target must be an existing masterframe asset for the matching purpose and cannot reference a raw calibration group or subframe; raw groups remain manageable and usable as sources for a Master.
- Saving a calibration relation does not run calibration; binding is not the same as having executed it.
- A collection shows subframe count and accumulated exposure automatically, summed from single-frame exposure over the whole current member range regardless of paging or filters; the number 0 and unknown are kept apart.
- Calibration candidates provide conflict and unknown evidence; the current user-declared Master sources are kept separately from the platform's actual processing facts.

## Calibration status

- Current asset status uses `UnCalibrated`, `Calibrated` and `Unknown`. External imports default to `Unknown`, and an explicit declaration records its evidence. Masters also retain their own status.
- Saving Master bindings preserves asset status. Successful calibration outputs register as new assets with the actual inputs, Masters, parameters and call. Operations explicitly preserving status inherit it, and unspecified processing semantics produce `Unknown`.
- A dataset displays the common member status, or aggregates mixed states as `Unknown` with counts for all three statuses. User declarations and actual processing evidence are retained separately.

## Asset library display

- The library provides global filters, lists, and previews. Projects manage references to subframe datasets and independent master frames. Multiple projects may reference a dataset. Its details show affected projects, and edits apply to their next processing call.
- The calibration column shows the final Master name on one line, with source and diagnostics available on demand.
- Normal browsing batch-reads calibration relations for the current page and does not rerun scientific checks.
- Local writes refresh immediately; external MCP changes sync through the existing lightweight refresh, without a new event system.

## Further reading

- [Library subsystem](../subsystems/library.en.md)
- [Import pipeline](../subsystems/import-pipeline.en.md)
- [Previews](../subsystems/previews.en.md)
- [Interfaces and generated artifacts](../references.en.md)
