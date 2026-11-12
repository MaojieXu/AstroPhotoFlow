# Frontend

English | [中文](frontend.md)

The native ComfyUI web page hosts the interface, and platform UI is split into a private UI package and a native bridge. Module boundaries are in [architecture](../architecture.en.md), and interface operations are in the [usage guide](../user/workbench.en.md).

## Private UI package

- `frontend/packages/astrophotoflow-ui` exports the asset workspace, workbench configuration, software panel and node/preview clients through `src/index.ts`; it is compiled by the native web page and is neither run nor published on its own.
- `src/core` provides shared HTTP and error handling, query caching and workbench configuration, while business code lives in `src/modules/data`, `nodes` and `software`.
- The package never imports native stores, canvas singletons or `frontend/src`; native components are injected by the host, and the authoritative export list is the code.

## Native bridge

- `frontend/src/platform/astrophotoflow` installs the query plugin, injects the translation function and wires business controls into the sidebar and canvas; it keeps the persistent canvas, sidebar order and unsaved-edit protection.
- A data reference uses one native undo transaction; a run receipt is checked against the actual Data and source wires; exports write copies only.
- Native stores, canvas and conversion coordination live in this directory, and the UI package never depends on it in reverse.

The local web app uses AstroPhotoFlow branding for the menu, startup and installation, with links to project documentation and feedback. Menus, shortcuts and settings hide upstream account, generation template and model management entry points. The node catalog shows nodes registered by the runtime.

## Canvas nodes

- Data receives one file path through the system chooser shared with the library and imports it. Manual path entry is collapsed. Cancellation, failure or node replacement preserves the existing binding. Single-image names appear only in the title, collections retain the current member name, and full information is available in details.
- Preview height follows content, and single images hide pagination. Saving to the library and exporting locally continue to use checked complete data. Preview resolution and channel selection affect display only.
- Software result cards use the native channel dropdown and place logs and complete-file downloads in the more menu. Reset restores every parameter from the instance definition, including advanced parameters, in one native undo transaction. Automatic mode submits one combined calculation, while manual mode waits for a run.
- Native widgets resolve their owner again when undo recreates a node with the same ID. Automatic float precision represents declared defaults, and restoring a default preserves its value despite edit-time callback rounding.

## Language resources

- The web app ships only English and Simplified Chinese: `localeDefinitions` in `frontend/src/locales/localeConfig.ts` decides the available languages, and other locale directories are not shipped.
- Native text lives in the `main`, `settings`, `commands` and `nodeDefs` catalogs under `frontend/src/locales/{en,zh}`; business text is merged into the same vue-i18n instance through `uiMessages` from `@astrophotoflow/ui`.
- The language is stored as the `Comfy.Locale` workspace setting and switching applies immediately in the web app; the service renders domain errors in the same language, while Bundle text follows its own language boundaries.
- New or changed text must be submitted in English and Chinese together; `tests/core/test_frontend_locale_coverage.py` checks that both key sets match, and the backend error catalog is checked by `tests/core/test_error_localization_coverage.py`.
- The automated translation entry point is `pnpm locale` (requires `OPENAI_API_KEY`) and the offline check is `pnpm locale:check`; the guards above are the merge standard.

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
