# ADR-WORKBENCH-FOUNDATION-0064: Web Restart and Native Controls

Date: 2026-10-28

## Status

Accepted

## Context

During M1 acceptance the user requested a restart button, clickable web address
and controls matching the native node sidebar. An unsaved concurrency edit can
otherwise appear to have been applied by a restart of the saved settings.

## Decision

Keep the native sidebar and use the native Input and Button semantic styles,
consistent control heights, block labels and aligned input/removal rows. Keep
configuration paths inside the advanced section. Link the actual web address.
Disable restart until local edits are saved and show the reason.

A typed public restart request dispatches an external controller which calls the
existing restart and drain behavior. The browser creates the operation ID before
posting; a lost reply triggers only status queries. Keep one current web request
receipt so failures before the lifecycle control record exists remain observable.
This is not a history ledger or a new resident service. Authentication and native
proxy origin checks apply to both routes.

After a configured web-port change, show a new configured entry and explicitly
state that cross-port automatic reconnection is unavailable. An automatically
selected different port requires `apf status` to obtain the actual address.
Never report a timeout or cancellation request as a completed restart.

This extends the CLI-only restart scope of
[ADR-WORKBENCH-FOUNDATION-0062](WORKBENCH-FOUNDATION-0062-configuration-and-lifecycle.md)
and preserves the placement of
[ADR-WORKBENCH-FOUNDATION-0063](WORKBENCH-FOUNDATION-0063-native-configuration-sidebar.md).

## Consequences

Saving and restarting remain distinct actions. Busy rejection, real draining and
startup diagnostics retain one implementation. The frontend keeps no credentials
and does not launch local processes directly. Human M1 acceptance remains pending.
