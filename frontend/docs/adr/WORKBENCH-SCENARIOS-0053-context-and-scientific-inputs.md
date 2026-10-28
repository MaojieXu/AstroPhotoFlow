# ADR-WORKBENCH-SCENARIOS-0053: Context and Scientific Inputs in User Journeys

Date: 2026-10-26

## Status

Accepted

This records clarified product requirements, not implemented capabilities.
The existing 58 data MCP tools, library Skill, runtime and business data remain
unchanged. The [current requirements](../../../docs/requirements/README.md#scenario-import)
own the complete journeys; module outlines own their responsibilities.

## Context

The user described button and Agent imports, selecting or dragging data onto
the canvas, deep-sky and planetary workflows, and making nodes with an Agent.
Reviews from novice experience, astronomy, Agent collaboration and developer
ecosystem perspectives identified missing task outcomes and handoffs.

Reading a workflow, receiving a change notification, starting a model turn and
confirming the displayed canvas are different events. The user chose quiet
resumption on the next interaction. They also confirmed original video as the
planetary starting point and Python function nodes as an S6 goal.

## Decision

- Keep the existing ten journey entries. Detail imports, data-to-canvas,
  processing and node creation in the current requirements, retaining result
  comparison, adoption, recovery, memory and cross-session continuation.
- Preserve manual single/batch import and Agent-assisted grouping/import.
  Report actual successes, skipped items, failures and ambiguities. Logical
  organization does not implicitly move or rename original files.
- A manual drag or graph edit does not trigger a new Agent response or wake an
  idle client. On the next user interaction, the supported and verified
  client/Skill continuation flow reads the explicit target's latest confirmed
  content and known synchronization/control state. The user need not restate
  the graph or copy JSON.
- Keep client guidance, public state reads, commit-time checks and native canvas
  readback separate. A Skill cannot force every external model to read state.
  Offline drafts are not confirmed saved content; a successful save is not
  proof that a particular browser displayed it. Late responses retain their
  original project, workflow, tab and subgraph target.
- Reading context does not restore write control. Manual-edit takeover and
  explicit handback remain in force; accepted runs continue under module ⑤.
- Describe deep-sky raw data, original planetary video and an existing stacked
  image as distinct processing starts. Module ② owns fixed scientific input,
  ③ reports the actual tool's supported conditions and observations, ④ declares
  node semantics, and ⑤ owns the graph, interaction and actual execution scope.
  Users select complete results for ② to save.
- Treat video registration, first-frame preview and scientific video processing
  as separate capabilities. Do not substitute a first frame for requested video
  processing. The software, formats, algorithms, frame representation and
  delivery task will be selected during actual integration.
- Make Python function authoring an explicit S6 goal alongside composite nodes.
  Keep the first operation-node loop in S3. Generated code, saved node content, actual tests, engine loading and canvas
  display remain separate.
  Execution packaging and dependency management are later design work.

## Alternatives Considered

Proactive responses on every manual canvas change could provide more immediate
assistance, but require a verified external-client wakeup and model-turn path.
The user chose quiet resumption instead. This does not remove current-content/control
checks from mutations or introduce an internal Agent.

Requiring users to describe each drag or paste graph JSON would make context
handoff explicit but repeat information the platform should expose. Reading
confirmed state on supported client continuation is the chosen requirement;
its actual client behavior still needs evidence.

Limiting planetary work to a stacked still image would simplify the initial
input path, but would omit the user's original-video goal. The full journey
is retained without declaring formats supported or expanding the first loop.

Moving Python authorship into the first loop would expose custom creation
earlier, but would advance code, environment and execution integration work.
The user chose to retain S6. Requiring an existing external operation is not a
substitute for the later user-authored Python journey.

## Consequences

Shared data and interface design must cover fixed video references, actual
tool scope, target-specific confirmed-state reads and tested node content.
They do not acquire predetermined wire fields, frame entities, an editor,
execution sandbox, new service or package format from this ADR.

Future tests must distinguish quiet waiting, next-interaction reads, offline
drafts, takeover/handback, stale targets, first-frame previews, actual video
execution, registration recovery and S6 Python content/retest evidence.
Documentation checks do not prove these features or client support exist.

The current module outlines define the responsibility boundaries and
implementation order for these journeys. No business regression, build, installation or live service operation
is part of this documentation update.
