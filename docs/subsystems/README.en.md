# Subsystems

English | [中文](README.md)

Each page covers one subsystem's behaviour, inputs and outputs, failure modes and external contracts; module boundaries, data ownership and dependency direction are in [architecture](../architecture.en.md), and product rules are in [product requirements](../product/README.en.md).

## Index

| Subsystem | Responsibility |
| --- | --- |
| [Import pipeline](import-pipeline.en.md) | Stage orchestration and task reporting for registration, content storage, metadata and previews |
| [Library](library.en.md) | Fixed versions of assets and datasets, equipment snapshots, calibration relations, result saving and trash |
| [Previews](previews.en.md) | Thumbnails, display recipes, tiled viewing and derived caches |
| [External software](software.en.md) | Software package catalogue, installation and readiness, actual invocations and stop observation |
| [Nodes](nodes.en.md) | Workspace node definitions, update diffs and the derived node catalogue |
| [Canvas agent](canvas-agent.en.md) | External agents observing and editing the current native canvas |
| [Workbench](workbench.en.md) | Configuration, workspace layout, process control and maintenance |
| [Frontend](frontend.en.md) | Private UI package and native bridge |
| [ComfyUI](comfyui.en.md) | Fixed engine, managed startup and same-origin gateway |

## Conventions

- Each page covers that subsystem's behaviour and contracts only, without repeating architecture or product content.
- Interface fields follow the actual routes and Pydantic models; generated artifacts are listed in [references](../references.en.md).
- User-facing operation instructions are in [usage guide](../user/workbench.en.md).
