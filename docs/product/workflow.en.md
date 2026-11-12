# Workflows and processing

English | [中文](workflow.md)

This page explains how users organize processing on the canvas, run it, and view and save results. The canvas and workflows reuse the native ComfyUI system, and the platform only adds astronomy assets, software calls and result saving; concrete contracts are in [native ComfyUI](../subsystems/comfyui.en.md) and [canvas and Agent](../subsystems/canvas-agent.en.md).

## Native canvas and workflows

- The canvas, workflow files, drafts, autosave, undo, conversion, queue, execution history, progress and cancel are owned by the native ComfyUI system.
- The platform does not build a separate workflow library, project-graph association, complete run library or second graph editor.
- Important schemes are saved with native Save As; the platform does not additionally keep a version per edit, server drafts or a permanent receipt store.
- External workflow JSON opens through native mechanisms; graphs with missing dependencies can stay for repair and are not installed or replaced automatically.
- Project metadata and asset and dataset references belong to data and are not associated with graph files.

## Putting assets on the canvas

- The canvas references assets by asset_id and datasets by dataset_id; dataset members and calibration follow the currently saved content.
- Users click an asset name and then choose a canvas drop point, or drag the whole row in; the node keeps the image, member switching and parameters.
- Switching members changes the display selection only. When a call starts, it fixes the actual members in current order, original hashes, metadata and calibration.
- Viewing an asset does not write the canvas and does not take over the Agent's editing.
- External image references on the canvas keep source and format information, and keep a hint when the source is disconnected.

## Agent editing

- After the user explicitly asks in the conversation, an external Agent directly edits the active canvas the user identified; there is no in-page handover, takeover session or control marker.
- Daily editing is a local operation; whole-graph JSON is used only for import or when the user explicitly asks to replace the entire graph.
- Before writing, the Agent checks the page, workflow, canvas and content marker; ordinary tasks need no node-by-node confirmation.
- After the user manually changes parameters, nodes, links or layout, old requests are rejected because the content marker changed; the Agent stops and explains instead of rereading and overwriting automatically.
- Pan, zoom and viewing do not change the content marker.
- Switching workflows pauses later writes and submissions for the old target and does not follow the new graph automatically; runs already started continue.
- After the web page closes, no canvas writes are accepted; other business continues under its own rules.
- Authorization comes from the user's explicit instruction; the platform does not parse chat or keep authorization sessions, and HTTP authentication remains.
- After reconnecting or changing clients, read the actual state first; stop when the target or content does not match; when a result is unknown, query the original operation receipt first and never resend automatically.

## Runs

- Manual runs and node automatic result previews reuse native conversion, validation, queue, progress and cancel; unnamed drafts are submitted through native mechanisms.
- After content or parameter changes, automatic results are submitted after a 500-millisecond merge window, without additionally saving a self-built project or a separate compute snapshot.
- Result ownership is decided by a content-match signature; each concrete call fixes the actual science inputs and parameters.
- Reproducible by default: use verified registered originals, or finish preparation first; when the user explicitly chooses "reference only", a weaker guarantee applies.
- Preparation failure never downgrades automatically; a specified target includes necessary dependencies and the request is not narrowed silently; science processing is not reused across runs automatically by default.
- Graph and prompt records use native execution history.
- A concrete call records fixed inputs and metadata, parameters, node definition content, software and Bundle versions, prompt and node association, status, errors and logs; later edits do not change existing call facts.
- A cancel request is not the same as an actual stop; on disconnect or unknown results, query first and never replay automatically.

## Previews

- Image nodes actually completed in a run automatically produce lightweight previews associated through the native workflow, prompt and node.
- No per-progress frame is saved, no complete workflow history library is built, and no Preview node is forced.
- A background result belongs to its source run and does not leak to other workflows or steal the view.
- Old previews do not guarantee a complete file or environment can be restored; continuing from fixed results reads real complete files.
- The viewer shows an overview first, then tiles by current member and viewport; video playback and pause, and original-frame zoom, are separate.
- Bundle nodes show all parameters and their own outputs. The thumbnail and viewer use the same checked member, frame, and channel with direct pixel mapping. The thumbnail size setting affects display.
- When comparable histograms exist, the grey trace shows the result before adjustment and the coloured trace shows the current result. Metrics carry source, unit, sample, and unavailability information. Frame tables can select a declared member and frame.

## Saving results and export

- Only a complete result the user selects is registered as an asset, with a chosen or default name; there is no intermediate-versus-final classification restriction.
- Complete intermediate files that are not selected are not kept long-term; native graph operations do not delete saved assets.
- A Data node takes content from the asset library or an external import, an upstream science reference, or a native IMAGE input; saving to the library and exporting locally are both triggered after the user selects complete members.
- Both support format and precision choices and preserve the original by default; they do not auto-stretch, crop, normalize or overwrite originals, nor rerun upstream work.
- Format and precision follow the interface contract and actual combination verification; cropping, resampling and registration update and verify WCS or mark it invalid.
- A preview does not replace the original; RGB display white balance is not photometric calibration.

## Continuing work

- Project metadata and current references belong to data and are not associated with graph files.
- Work can continue from a saved graph, run or result; when the Agent changes, it reads the background summary.
- Unknown results are checked first, and restoring never changes old runs.
- Local memory can be viewed, edited, disabled and deleted; explicit user statements win over Agent analysis; analysis names its source project and does not change run facts; deletion includes historical text; full chats, model state and credentials are not stored.

## Further reading

- [Canvas and Agent](../subsystems/canvas-agent.en.md)
- [Native ComfyUI](../subsystems/comfyui.en.md)
- [Previews](../subsystems/previews.en.md)
- [Workbench subsystem](../subsystems/workbench.en.md)
