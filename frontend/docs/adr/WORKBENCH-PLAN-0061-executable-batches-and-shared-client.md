# ADR-WORKBENCH-PLAN-0061: Executable Batches and Shared HTTP Client

> 2026-10-29：本文的22 Batch及固定前置文档流程已被 [ADR-0001](../../../docs/decisions/0001-minimal-documentation.md)取代，只保留历史参考。共用HTTP客户端的已实现边界仍以当前代码及架构为准。

Date: 2026-10-27

## Status

Accepted

These are the user's five planning decisions. They do not approve an
implementation, a runtime change, or a completed milestone.

## Context

The implementation plan has six milestones and 22 batches. Some execution
batches are large, software installation consumes node definitions before the
node milestone can finish, and new configuration UI must not import the data
module's existing HTTP implementation. A separate workspace does not isolate
the user-level native runtime. Changing library removal before the MCP
migration would leave its old request without the required impact fields.

## Decision

- Keep 22 batches and suggested branches. Describe ordered implementation and
  verification steps inside large cards; integrate the complete card.
- Implement M3 and M4 in their technical dependency order and obtain separate
  user approvals during the same acceptance session.
- In B13, move the existing FetchApi, ApiClientError and createApiClient code
  into the already planned core/client.ts, with errorSchema in
  core/contracts.ts. Preserve direct data-module re-exports and existing
  behavior, adding the required error fields. Business DTOs stay in their
  modules. Do not add a transport framework or another file.
- Use an explicit maintenance window for real native verification. Stop users
  of the shared runtime, test the candidate, and restore the original dev
  version and running state. Keep normal dev data unchanged; an isolated test
  workspace alone is insufficient protection.
- Switch the removal preview, new DELETE body, clients, MCP mapping and Skill
  together in B57. B54 provides the internal impact query and its tests. Do not
  add temporary tools, compatibility branches or automatic confirmation.

## Alternatives Considered

More branches would shorten large assignments while adding integration and
review dependencies. Ordered steps within the existing batches retain the
chosen integration boundaries. Requiring M3 approval before any M4 work would
block M3's own node-definition dependency.

Leaving the shared request code in data would either invert the core boundary
or duplicate request and error handling. Moving that existing code has actual
configuration and business consumers, without a new abstraction.

A separate Windows user or VM would keep dev continuously running but require
another environment. The user chose a maintenance window and restoration.
Publishing new removal requests before the MCP switch would require an interim
protocol or restricted path; the user chose one final switch instead.

## Consequences

The [implementation plan](../../../docs/archive/2026-10-29-planning/development/implementation-plan.md)
owns batches, gates and future verification procedures. The
[interface design](../../../docs/archive/2026-10-29-planning/api/platform-contracts.md) remains the sole
protocol and signature authority. Task cards map it to files and tests.

Batch integration and user milestone acceptance are separate facts. Real
software, native loading, canvas control, execution, cancellation and image
results still require the planned prototypes and user operations.
