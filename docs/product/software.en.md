# Software and nodes

English | [中文](software.md)

The platform binds astronomy processing software to canvas nodes, so users can call fixed software versions on the graph. Software installation, readiness and call facts are maintained by the software capability, and node definitions by the node capability; concrete contracts are in the [software subsystem](../subsystems/software.en.md) and [node subsystem](../subsystems/nodes.en.md).

## Software packages and versions

- The platform maintains fixed software and its companion nodes; ordinary software comes from Git and is pinned to a tag or commit.
- The Siril program, operations, node bindings and adapter live in an independent private Bundle; the platform maintains the SDK and release snapshot.
- Software versions and Bundle versions are displayed separately and never substitute for each other.
- The target is complete encapsulation of Siril 1.4.4 scriptable capabilities; session and file control map to actual capabilities, and duplicate aliases may share an implementation.
- Non-script or GUI capabilities keep a description and limits and never declare fake execution nodes.

## Install and update

- Install, version switching and uninstall follow the concrete plan confirmed in the web app; sensitive logins and licenses are entered directly by the user.
- Maintenance is not refused because runs or previews exist, and no in-flight old implementation version is kept.
- Readiness requires both the actual program and its nodes to load; a successful checkout is not usability.
- Dedicated software copies are separate from assets; uninstall keeps assets, node definitions and workflows; the first migration keeps the original standalone program.
- Update first lists impact and parameter changes; missing nodes keep a hint in the graph; old software is not promised long-term coexistence or reproduction of old runs.
- The Bundle version dropdown checks official Git tags and can refresh; when not installed, prefer the latest stable release, fall back to a compatible development release when no compatible stable exists, and keep the current version for an existing install.
- Grayed items explain incompatibility with the system, SDK, declaration format or required files; after selection, review current and target versions, program version, tag, commit and node changes before confirming install or switch.
- A confirmed plan always points to the commit selected then; when a check fails, installed information and the last successful list are kept.

## Hot reload

- Frontend Vue, TypeScript and CSS update automatically through the development service.
- Changes to an installed Bundle's SDK Python adapters and node definitions, as well as install, update and uninstall, load, update or remove capabilities without a service restart.
- Platform backend business Python is not reloaded automatically.
- Hot reload must be verified for real and cannot be inferred from a page refresh.

## Node definitions

- Node definitions live in workspace JSON and can be saved before testing; the latest test result is read from the same run facts.
- After an update is confirmed, instance parameters use the new version defaults; ports with the same direction, name and type keep their links, including after reordering.
- Renaming, changing the type of or deleting a node breaks its links; input names and output names are each unique.
- The platform first wraps existing software operations; Python and composite nodes are deferred.
- One workspace node library serves all projects; editing a composite's internals affects only the current workflow and does not write back to the public definition.

## Call ownership

- Concrete software calls belong to the software capability, result file facts to data, and cross-module assembly to interfaces.
- The platform does not establish a Workflow or Run lifecycle.
- Cancel acceptance, actual stop, save, apply, execution and asset registration are expressed separately.

## Capability discovery

- Skills and known workflows are reached directly; when discovery is needed, a typed hybrid search covers tools, nodes and software operations, returning at most 10 candidates per time, with full definitions read on demand.
- The local fixed embedding serves retrieval only; on failure it degrades to keywords and states the reason.
- Chats, memory and science bytes are not indexed by default; ranking is never authorization.
- MCP offers a few entries per data, node and canvas domain, with concrete operations discovered on demand or called directly.
- Whole-night imports first show an organization list, and after user confirmation submit in batches and aggregate observed results.
- No empty capabilities are registered; model and index implementations are chosen for the actual task.

## Further reading

- [Software subsystem](../subsystems/software.en.md)
- [Node subsystem](../subsystems/nodes.en.md)
- [Native ComfyUI](../subsystems/comfyui.en.md)
- [Interfaces and generated artifacts](../references.en.md)
