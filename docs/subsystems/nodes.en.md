# Nodes

English | [中文](nodes.md)

Editable node definitions, update diffs and the derived node catalogue in a workspace belong to the nodes module; module responsibilities are in [architecture](../architecture.en.md), and node execution belongs to software and the native side.

## Responsibilities

- Save user definitions and Bundle-synced copies into the workspace node directory, distinguishing them by a source field.
- Assemble the node catalogue from public software metadata, providing names, categories, ports, parameters and content tokens.
- Compute definition update diffs and write only after impact is confirmed.

## Update rules

- On update, instance parameters all take the new version's defaults.
- Ports with the same direction, name and type keep their wires, including reordering; changed ports are disconnected.
- Input and output names are unique on their own side; the rules are not extended to arbitrary third-party nodes.
- In-flight content and history are left unchanged; saving is not gated on passing tests.

## Catalogue and display

- Names and categories come from node declarations and Bundle bilingual display material; switching language changes display labels only.
- Legacy declarations without a category fall under the software root; a category changes neither node type, ports nor execution binding.
- Custom node titles already on the canvas are preserved.

## Inputs and outputs

- Inputs: definition writes, Bundle synchronisation and update confirmation.
- Outputs: node definitions, diffs, write results and the node capability catalogue.
- Validation failures are returned clearly; a missing referenced definition or parameter is never guessed.

## External contracts

- HTTP queries are in `src/astrophotoflow/interfaces/http/nodes.py`; contracts are in `src/astrophotoflow/contracts/nodes.py`.
- Native Bundle loading is in `src/astrophotoflow/interfaces/native/bundles/`, and this module builds no executor.
- Fields follow the [OpenAPI snapshot](../api/openapi.json).

## Tests and boundaries

- Tests are in `tests/modules/nodes/`.
- Node execution and process observation belong to software; canvas writes and undo belong to the native bridge.
