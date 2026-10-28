# ADR-WORKBENCH-NODES-0057: Use Shared Editable Node Definitions

Date: 2026-10-27

## Status

Accepted

This is an accepted design, not an implementation.

## Context

Users want to make a node with an external Agent, save it, try it and reuse it
across projects. A shared editable definition supports that workflow while
keeping actual test results associated with the content that was tested.

## Decision

- Keep editable custom node definitions in one workspace library. Store their
  identity, name and description, ports, parameters and execution content.
  Saving and using a node do not require a successful test or publication gate.
- Read the most recent test and its run link from module ⑤. When a node changes,
  identify an older test as testing the previous content. Do not introduce a
  separate test evidence or activation history object; show actual load errors
  and software readiness from the engine and module ③.
- Before updating a custom node, list affected workflows and ask the user to
  confirm. Module ⑤ updates instances and saves the current workflow. Reset
  instance parameters to the new defaults without validating old parameter values.
- Custom input names must be unique among inputs, and output names among outputs.
  Match ports by direction, name and type: unchanged ports retain connections,
  including after reordering; renamed, removed or retyped ports disconnect.
  This does not impose naming rules on arbitrary third-party nodes.
- Keep already executing content and historical run facts unchanged. Do not
  require older custom implementations to remain installed for old workflows.
  Module ⑤ records what actually ran, without guaranteeing later reproduction.
- Python and composite nodes remain S6 goals. Editing composite internals in a
  workflow creates a local copy and does not change the library or other graphs.
  Export and recipient installation remain goals without a package format.

## Alternatives Considered

A shared editable definition serves the selected cross-project reuse and update
flow without requiring test gates or historical implementation management.

Disconnecting every connection is simpler but loses unchanged wiring. Matching
by native slot position permits duplicate output names but disconnects reordered
ports or confuses same-named outputs. Clear unique names support the selected
behavior without a new persistent port identity system.

A mandatory test gate blocks saving incomplete work. Optional real tests with
an actual run link provide feedback without creating another release process.

## Consequences

The native frontend permits duplicate output names and stores outputs by position.
The host bridge must verify remapping when ports reorder; native definition
refresh alone does not satisfy this update design. Runtime loading and protection
of executing content still require prototypes. This decision does not choose a
database schema, protocol, code execution environment or hot-loading mechanism.

Software package nodes retain the separate update policy of
ADR-WORKBENCH-SOFTWARE-0056. Module ④ owns definitions; ⑤ owns graph instances,
confirmed changes, real execution and controlled interaction. No code,
interface, migration, environment, MCP registration or Skill is changed here.
