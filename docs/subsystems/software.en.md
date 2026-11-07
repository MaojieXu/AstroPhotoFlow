# External software

English | [中文](software.md)

Fixed software packages, installation and readiness, actual invocations and stop observation belong to the software module; the source and adapters of independent Bundles are maintained in a private repository. Module responsibilities are in [architecture](../architecture.en.md), and product rules are in [software product requirements](../product/software.en.md).

## Responsibilities

- Maintain the packages, operations and display material in the release catalogue snapshot, and discover versions from the official Git repository.
- Execute user-confirmed install, switch and uninstall plans, recording program versions, invocations and observations.
- Provide capability and dependency information for the node catalogue and automatic results.

## Bundle contracts

- Only Bundle SDK v2 is supported; inputs, outputs, commands and assessment material are declared in the Bundle, and the platform generates no empty nodes.
- The host owns fixed-asset inputs, the actual process, cancellation and output range checks; analysis schemas and scientific outputs go through data's public capability checks.
- Process exit does not mean a node result is ready; after the main process exits the platform observes the known process tree for at most 5 seconds, and keeps unknown without rerunning when it is still active or cannot be verified.
- Display previews are declared by an operation's `preview.input` and `preview.output`; a sampling parameter change invalidates the cache, new caches are marked `bundle-sample`, and old caches are not migrated.
- `automatic_result_preview` defaults to false; when enabled the operation can become an automatic-result target and dependency, and the whole dependency chain must allow automatic execution.

## Versions and installation

- A selection token binds the official source, tag, commit and manifest; the install plan and the actual checkout both verify the fixed target, while language and the latest marker do not participate in the token.
- A failed version query is reported separately and keeps the last successful list; historical experiment tags and unpublished tags never enter the official install list.
- Installation state is replaced atomically; a failure to write the final state must be reported as an unsaved installation result that needs review.
- Bundle Python is loaded under a separate package namespace, a content fingerprint change invalidates the owned module tree, and modules are compiled from source.

## Inputs and outputs

- Inputs: package and operation identifiers, parameters, fixed asset or dataset versions, and a development binding directory.
- Outputs: invocation records, process observations, output members and actual files; accepted cancellation, observed stop and unknown results are distinct states.
- The platform reads declarations from development or installed Bundles and from the release catalogue snapshot, and platform unit tests use synthetic Bundles.

## Failure modes

- A missing program or environment reports the readiness reason instead of assuming availability.
- When a process stop cannot be observed, unknown is kept and a query is required; nothing is replayed automatically.
- A visible preview sample does not mean a complete result is available, and formal runs keep using full scientific inputs.

## External contracts

- HTTP routes are in `src/astrophotoflow/interfaces/http/software.py`, `software_calls.py` and `software_previews.py`.
- Contracts are in `src/astrophotoflow/contracts/software.py` and `bundles.py`; fields follow the [OpenAPI snapshot](../api/openapi.json).
- The public entry point is `src/astrophotoflow/modules/software/public.py`; cross-module assembly is in `src/astrophotoflow/interfaces/application/`.

## Tests and boundaries

- Tests are in `tests/modules/software/`.
- Node definitions belong to nodes; graphs, queues and execution history belong to ComfyUI; checked results belong to data.
