# Canvas agent

English | [中文](canvas-agent.md)

External agents observe and edit the current native canvas through the platform's access layer; graph files, queues, history and the cancel entry belong to ComfyUI. Access responsibilities and dependency boundaries are in [architecture](../architecture.en.md).

## Responsibilities

- List online canvas pages with their workflow, subgraph and `content_token`.
- On explicit user request, add a fixed asset or dataset set to the exact page, or perform one node addition, parameter change, connection or node deletion.
- Hand edits over to native undo, drafts and saving, and never execute the whole graph.

## Inputs and outputs

- Inputs: page, workflow and subgraph identifiers, the current `content_token`, and the edit content the user specified.
- Outputs: an operation receipt and the current page state; an unknown result is queried by the original `operation_id` and never resent.
- Deleting a node removes the node and its wires through native undo while keeping the source asset.

## Constraints and failure modes

- Verify the exact target before editing; stop when the page is offline, the graph is switched or the content changed.
- When the canvas result cannot be confirmed, return an unknown connection and require a query with the same `operation_id` instead of replaying automatically.
- Edits change no assets, datasets or project references on the platform side, and adding to the canvas copies no scientific original.
- A late receipt is never written into another graph, and work never continues on a canvas the user did not specify.

## Data references

- A fixed asset or dataset enters the canvas as a fixed-version reference, and display state is not serialised as scientific data.
- Canvas widgets display data through the native widget lifecycle, and the host keeps the existing canvas and theme.
- Data references and content markers follow the current page receipt.

## External contracts

- HTTP routes are in `src/astrophotoflow/interfaces/http/canvas.py` and `interfaces/http/data/canvas.py`.
- Contracts are in `src/astrophotoflow/contracts/canvas.py`, `inputs.py` and `native.py`; page messages are included in the [OpenAPI snapshot](../api/openapi.json) under `x-apf-native-messages`.
- Native receipts and clients are in `src/astrophotoflow/interfaces/native/`; query entry points are in [references](../references.en.md).

## Tests and boundaries

- Tests are in `tests/interfaces/`.
- Workflow editing, queues and execution history belong to ComfyUI; software invocations belong to software; checked results belong to data.
