# Frontend

English | [中文](frontend.md)

The native ComfyUI web page hosts the interface, and platform UI is split into a private UI package and a native bridge. Module boundaries are in [architecture](../architecture.en.md), and interface operations are in the [usage guide](../user/workbench.en.md).

## Private UI package

- `frontend/packages/astrophotoflow-ui` exports the asset workspace, workbench configuration, software panel and node/preview clients through `src/index.ts`; it is compiled by the native web page and is neither run nor published on its own.
- `src/core` provides shared HTTP and error handling, query caching and workbench configuration, while business code lives in `src/modules/data`, `nodes` and `software`.
- The package never imports native stores, canvas singletons or `frontend/src`; native components are injected by the host, and the authoritative export list is the code.

## Native bridge

- `frontend/src/platform/astrophotoflow` installs the query plugin, injects the translation function and wires business controls into the sidebar and canvas; it keeps the persistent canvas, sidebar order and unsaved-edit protection.
- A fixed data reference uses one native undo transaction; a run receipt is checked against the actual Data and source wires; exports write copies only.
- Native stores, canvas and conversion coordination live in this directory, and the UI package never depends on it in reverse.

The local web app uses AstroPhotoFlow branding for the menu, startup and installation, with links to project documentation and feedback. Menus, shortcuts and settings hide upstream account, generation template and model management entry points. The node catalog shows nodes registered by the runtime.

## Queries and polling

- One application-level Vue Query client is shared, with workspace identity in query keys; retries are off by default, the internet may be disconnected, and focus refetching is disabled.
- Visible tasks discover cross-entry tasks every 10 seconds; active tasks are read every 1.5 seconds, directory frequency resumes when they finish, and task queries are invalidated per workspace.
- Import task service data belongs to the query cache, and test mounts use the same plugin.

## Failure modes

- A manual content change invalidates older requests; switching graphics pauses later writes and commits, and late results never steal the view.
- Viewing and zooming do not change the content marker, and display state is not serialised.
- The UI never touches the database directly or duplicates domain rules, and unknown results are queried through the owning module.

## External contracts

- Public entry points are the package exports and the native bridge; backend contracts follow the actual routes and Pydantic models, with fields in the [OpenAPI snapshot](../api/openapi.json).
- The generated frontend SDK is in `frontend/packages/astrophotoflow-ui/src/generated/api` and is never edited by hand.
- Tests use `pnpm test` and `pnpm typecheck`.

## Boundaries

- Workflow editing, queues, execution history and canvas capability belong to ComfyUI; domain rules belong to their modules.
