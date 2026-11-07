# User guide

English | [中文](workbench.md)

This page gives everyday operating steps; product rules for the workbench are in [workbench rules](../product/workbench.en.md), and interface lookups are in [references](../references.en.md).

## Install and open

Use the development wheel you actually obtained in place of the example path:

```powershell
py -3.12 -m venv .apf-env
.\.apf-env\Scripts\python.exe -m pip install <开发wheel路径>
.\.apf-env\Scripts\apf.exe init --workspace D:\AstroPhotoFlow\workspace --service-port 18190 --comfyui-port 18188
.\.apf-env\Scripts\apf.exe start --workspace D:\AstroPhotoFlow\workspace
```

Open the actual web address `start` returns; when a port is occupied one is chosen automatically, so do not guess a fixed address. The first initialization prepares fixed CPU runtime dependencies, and later runs of the same version reuse the completed environment. You can also run `apf runtime prepare` first to prepare software, then `apf workspace create --workspace <path>` to create only empty configuration and directories; opening the web app still needs `init` or explicitly supplied existing web resources. Installing the platform wheel does not require Node; the standalone Siril Bundle needs Git access. Manual processing needs no generative model.

## Interface

- The canvas is permanent; the sidebar provides node library, asset library, projects, workflows and software packages in order.
- The sidebar can be collapsed and resized; the asset library toolbar offers import and equipment management, and the settings button in the sidebar opens settings.

## Importing assets

- In the asset library choose import, then pick local files or one folder; a folder contributes only files supported at the current level, with no authorization root to configure first.
- Registration and originals becoming ready are shown separately from background previews; partial failures keep their reason and can be inspected and retried individually.
- Import notifications cover only the current submission or session; there is no history page or notification center.

## Asset library and fixed collections

- The asset library offers a compact list and a detail mode; click an asset name and then choose a canvas drop point, or drag the whole row onto the canvas.
- Click a thumbnail to view an asset; a fixed collection can switch members while keeping the image, name and parameters.
- The calibration column shows the final Master name, with version, source and diagnostics available on demand.

## Canvas editing

- Adding nodes, parameters, links, layout, autosave and undo follow native canvas operations.
- Save important schemes with native Save As; browser drafts and undo use native mechanisms.
- External workflow JSON opens through native mechanisms; missing nodes keep a hint and are not installed automatically.

## Runs and results

- Runs, queue, progress and cancel use native entries; while running, each completed image node produces an automatic preview.
- After selecting a complete result, save it to the asset library or export it locally; format and precision keep the original by default.
- Previews and thumbnails are not science originals; continuing processing starts from real complete files.
- When comparing results, check whether registration, size, ROI and stretch match; a missing metric is not 0.

## Letting an external Agent operate

- In the conversation, tell the Agent which canvas and target to change, and the Agent then edits that active canvas directly.
- Ordinary tasks need no node-by-node confirmation; manual edits invalidate old requests, and the Agent should stop and explain.
- After the web page closes, no canvas writes are accepted; on reconnect or a client change, read the actual state first.

## Software packages

- The software package page shows each Bundle's actual readiness and reason; actual node capability follows the installed Bundle and its readiness state, and command documentation is not an executable node.
- Install, version switching and uninstall are confirmed in a native dialog after reviewing the exact plan.
- The version dropdown checks official Git tags and can refresh; grayed items explain incompatibility, and the review before confirmation covers version, tag, commit and node changes.

## Settings

- Settings are not applied by saving; only an explicit restart adopts saved values, and unsaved content cannot be used for a restart.
- A restart is refused while the service is busy or cannot be confirmed idle.
- Under "Settings → General → Language", choose English or Simplified Chinese; the web app updates immediately, and MCP refreshes tool descriptions after reconnecting.
- After changing ports, the current page cannot reconnect across ports automatically; open the new address shown in the UI or returned by `apf status`.

## Stop, diagnostics and data protection

```powershell
.\.apf-env\Scripts\apf.exe stop --workspace D:\AstroPhotoFlow\workspace
```

- Stopping waits for tasks to drain; on timeout or unknown identity it keeps a record and does not mean stopped, so check status and logs first.
- Logs are in the workspace `logs` directory; never output service.token.
- Business data lives in the specified workspace, web resources in `web`, native workflows in `comfyui-user`, and assets and previews in `data`; the program runtime is separate.
- The default workspace is chosen by the user TOML `[workspace] default`; the platform offers no workspace migration service.
- Existing databases are not upgraded automatically; protect data under an explicit plan before upgrading, and never copy only the running SQLite main file.
- Closing the browser does not stop accepted tasks; after a disconnect, query existing requests first and do not submit again automatically.

## Further reading

- [Workbench rules](../product/workbench.en.md)
- [Assets, equipment and calibration](../product/data.en.md)
- [Workflows and processing](../product/workflow.en.md)
- [References](../references.en.md)
- [Development](../development.en.md)
