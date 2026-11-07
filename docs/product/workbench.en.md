# Workbench rules

English | [中文](workbench.md)

The workbench is the local application users see after opening the web page. This page states the workbench's shape, lifecycle, safety and delivery rules; step-by-step operations are in the [user guide](../user/workbench.en.md), and runtime topology and process contracts are in [architecture](../architecture.en.md) and the [workbench subsystem](../subsystems/workbench.en.md).

## Workbench shape

- The workbench is a local web app opened in a browser; one workspace runs two resident processes, the native web app and the domain service.
- The canvas is permanent, and the sidebar contains, in order, node library, asset library, projects, workflows and software packages.
- The sidebar can be collapsed and resized; the asset library offers import and equipment management entries.
- Opening the workbench shows the canvas first and enables Nodes 2.0 node styling locally.
- Unrelated native features, internal migration entries, model and cloud settings are hidden, and upstream notifications are off.
- Saved graphs autosave after a delay by default; if the user explicitly turns that off, the setting is kept.

## Workspace and lifecycle

- The default workspace is chosen in user configuration; the platform offers no identity registry or migration service.
- The latest configuration, actual runtime information and recent start/stop results are kept; control commands do not change the default workspace.
- Performance settings take effect on the next explicit restart, with no queued automatic restart.
- A restart is refused while the service is busy or cannot be confirmed idle.
- A healthy service belonging to the same workspace is reused; when a port is occupied, a free port is chosen automatically.
- After both services are ready, actual ports and allowed origins are written back and the web address is returned; saving configuration and control do not drift the running target.
- When the control target is unknown, check first; before an upgrade, back up the database and protect originals and tokens.

## Safety and confirmation

- Ordinary operations run continuously; install, permanent deletion, overwriting, sending data out and payment are confirmed per concrete plan or explicitly pre-authorized by the user.
- Actual submission verifies authentication, target and scope; text, Skills and self-reported identity never widen permissions.
- A virtual environment is not a malicious-code sandbox.

## Data protection

- Programs and workspace data are separate; upgrade and uninstall never delete user data automatically.
- Only data and previews necessary for the task are sent; science originals are not sent out by default.
- Logs, graphs, exports and diagnostics are redacted.

## Performance

- Large files are handled on demand and asynchronously; full science files are never read into the browser or a model context.
- Long tasks stay interactive; unknown progress shows stage, duration and logs.
- Performance conclusions record machine, version, data scale and measured values; numeric thresholds are never invented.

## Delivery

- The delivery form is a local web app, Windows first; development versions are X.Y.Z-dev.N, and formal releases are approved separately.
- Support scope is recorded for the actual combination of nodes, formats, software and platform; unverified platforms are never written as passing.
- Traceability is not bit-level reproducibility; a locked combination can be rebuilt, with out-of-repo wheel installs and sdist rebuilds without Node.

## Further reading

- [Architecture](../architecture.en.md)
- [Workbench subsystem](../subsystems/workbench.en.md)
- [Release](../release.en.md)
- [User guide](../user/workbench.en.md)
