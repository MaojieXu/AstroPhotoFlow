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

- Development and installed Bundles and custom nodes provide English and Chinese display material through the same capability catalogue. The web UI follows the system language for names, categories, ports, parameters, descriptions and help.
- Custom display overrides are stored in the definition. Omitted fields inherit, explicit empty descriptions or help clear the text, and null is rejected. Names and labels must be nonempty, and category depth and member keys must match the node definition.
- Custom names, descriptions and categories retain the node text unless overridden. Help inherits from the operation, and ports and parameters inherit Bundle labels through execution bindings. Fixed parameters generate no labels. Conflicting labels in many-to-one bindings use the node field name.
- The catalogue returns effective translations keyed by node fields and retains node-authored material when the operation is missing. Catalogue events refresh translations and remove withdrawn entries. Failed queries preserve the existing catalogue and report an error.
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
