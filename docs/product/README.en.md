# Product requirements

English | [中文](README.md)

AstroPhotoFlow is a locally running astronomy image workbench: it turns captured FITS files into traceable assets, connects software operations into a processing graph on a canvas, then runs the processing for real so users can view, compare and save results. Users can operate it directly, or let an external general-purpose Agent work through the platform MCP on the same data and a canvas the user explicitly authorizes.

## Target loop

The first delivery proves one complete path:

1. Select one fixed FITS file or one ordered collection.
2. Add the asset to the native ComfyUI canvas.
3. Process it with Siril 1.4.4 Auto Stretch.
4. View the real output file.
5. Have the user select a complete result and save it to the asset library.

Both entries, manual operation and real Agent calls, must work; a UI demo alone is not enough.

## Product rules that must hold

- Asset identity is stable, and assets and collections have fixed versions; members and order are fixed at acceptance, and later appends do not change the order of existing members.
- Editing and running reuse the native ComfyUI canvas, workflows, queue, history and undo; no separate workflow library, run library or second editor is built.
- Processing results come from actual software execution; previews, thumbnails and automatic results are never treated as science originals or official results.
- Installing, switching versions, permanent deletion, overwriting, sending data out and payment are confirmed per concrete plan, or explicitly pre-authorized by the user.
- One workspace runs only two resident processes, the local web app and the domain service; data and science originals stay local by default.

## Scope boundaries

- No built-in chat, inference, model sessions or generative model credential management; an external Agent is a general-purpose tool that works through the interfaces the platform provides.
- No promise of multi-user operation, multiple Agents concurrently editing the same graph without order, cloud clusters, arbitrary third-party nodes or arbitrary software being understood automatically.
- Windows first; Linux/WSL is verified separately later. Formal release and version numbering are approved separately.

## Page index

| Page | Content |
| --- | --- |
| [Assets, equipment and calibration](data.en.md) | Asset identity and fixed versions, import, equipment setups, calibration and asset library display |
| [Workflows and processing](workflow.en.md) | Canvas editing, Agent editing, runs, previews, saving results and comparison |
| [Software and nodes](software.en.md) | Software packages, installs and versions, hot reload, node definitions and capability discovery |
| [Workbench rules](workbench.en.md) | Workbench shape, lifecycle, safety confirmations, data protection and delivery |
| [User guide](../user/workbench.en.md) | Step-by-step instructions for users |
| [Architecture](../architecture.en.md) | Modules, data ownership and cross-module assembly |
