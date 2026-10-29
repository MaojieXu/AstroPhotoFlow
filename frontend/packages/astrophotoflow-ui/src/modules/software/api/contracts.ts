import { z } from 'zod'

const errorDetailSchema = z
  .object({
    code: z.string(),
    message: z.string(),
    fields: z.array(
      z.object({ path: z.string(), message: z.string() }).strict()
    )
  })
  .strict()

export const softwarePackageSchema = z
  .object({
    package_id: z.string(),
    name: z.string(),
    available_versions: z.array(z.string()),
    installed_version: z.string().nullable(),
    install_path: z.string().nullable(),
    package_token: z.string(),
    availability: z.enum(['not_installed', 'ready', 'not_ready', 'unknown']),
    reason: z.string().nullable(),
    operation: z.enum(['install', 'prepare', 'update', 'uninstall']).nullable(),
    operation_state: z.enum([
      'idle',
      'running',
      'completed',
      'failed',
      'unknown'
    ]),
    phase: z.string().nullable(),
    progress: z.number().min(0).max(1).nullable(),
    last_error: errorDetailSchema.nullable(),
    node_definition_ids: z.array(z.uuid()),
    bundle_version: z.string().nullable().optional(),
    bundle_commit: z.string().nullable().optional(),
    restart_required: z.boolean().optional(),
    migration_required: z.boolean().optional()
  })
  .strict()

const softwarePlanNodeChangeSchema = z
  .object({
    definition_id: z.uuid(),
    name: z.string(),
    action: z.enum(['create', 'update', 'remove', 'retain']),
    before_content_token: z.string().nullable(),
    after_content_token: z.string().nullable()
  })
  .strict()

const workflowImpactSchema = z
  .object({
    project_id: z.uuid(),
    workflow_id: z.uuid(),
    path: z.string(),
    content_token: z.string(),
    node_execution_ids: z.array(z.string()),
    parameter_defaults: z.record(z.string(), z.record(z.string(), z.json())),
    retained_link_ids: z.array(z.number().int()),
    disconnected_link_ids: z.array(z.number().int()),
    missing_definition_ids: z.array(z.uuid()),
    unsaved_pages: z.array(z.uuid())
  })
  .strict()

export const pendingSoftwareActionSchema = z
  .object({
    operation_id: z.uuid(),
    state: z.enum([
      'awaiting_confirmation',
      'running',
      'completed',
      'failed',
      'expired',
      'unknown'
    ]),
    plan: z
      .object({
        action: z.enum(['install', 'update', 'uninstall']),
        package_id: z.string(),
        current_version: z.string().nullable(),
        target_version: z.string().nullable(),
        source: z.string().nullable(),
        install_path: z.string().nullable(),
        package_token: z.string(),
        impact_token: z.string().nullable(),
        restart_required: z.boolean().nullable(),
        restart_reason: z.string().nullable(),
        node_changes: z.array(softwarePlanNodeChangeSchema),
        workflow_impacts: z.array(workflowImpactSchema)
      })
      .strict(),
    confirmation_url: z.string(),
    error: errorDetailSchema.nullable()
  })
  .strict()

const definitionWriteResultSchema = z
  .object({
    definition_id: z.uuid(),
    action: z.enum(['create', 'update', 'remove']),
    applied: z.boolean(),
    content: z.unknown().nullable(),
    error: errorDetailSchema.nullable()
  })
  .strict()

const nativeNodeLoadSchema = z
  .object({
    definition_id: z.uuid(),
    content_token: z.string().nullable(),
    state: z.enum(['loaded', 'not_loaded', 'failed', 'unknown']),
    reason: z.string().nullable()
  })
  .strict()

const workflowChangeResultSchema = z
  .object({
    workflow_id: z.uuid(),
    applied: z.boolean().nullable(),
    save: z.unknown().nullable(),
    error: errorDetailSchema.nullable()
  })
  .strict()

const packageMutationResultSchema = z
  .object({
    package: softwarePackageSchema,
    definition_results: z.array(definitionWriteResultSchema),
    loads: z.array(nativeNodeLoadSchema),
    workflow_results: z.array(workflowChangeResultSchema),
    error: errorDetailSchema.nullable()
  })
  .strict()

export const softwarePackageDetailsSchema = z
  .object({
    package: softwarePackageSchema,
    current_action: pendingSoftwareActionSchema.nullable(),
    result: packageMutationResultSchema.nullable()
  })
  .strict()

export const softwarePreparationSchema = z
  .object({
    package: softwarePackageSchema,
    user_action: z.string().nullable(),
    ui_kind: z.enum(['software', 'platform']).nullable(),
    ui_target: z.string().nullable()
  })
  .strict()

const sirilCommandAssessmentSchema = z
  .object({
    parameter_details: z.string(),
    structured_parameter_defaults_ranges: z.string(),
    single_image_sequence_context: z.string(),
    input_output_semantics: z.string(),
    headless_status: z.string(),
    dependencies: z.string(),
    security_risk: z.string(),
    semantic_review_status: z.string(),
    node_definition_status: z.string(),
    node_definition_reason: z.string(),
    node_generation_status: z.string(),
    node_generation_reason: z.string(),
    registry_load_status: z.string(),
    registry_load_reason: z.string(),
    runtime_test_status: z.string(),
    runtime_test_reason: z.string()
  })
  .strict()

export const sirilCommandSchema = z
  .object({
    command: z.string(),
    scriptable: z.boolean(),
    syntax: z.string(),
    description: z.string(),
    url: z.url(),
    assessment: sirilCommandAssessmentSchema
  })
  .strict()

export const softwareInstallRequestSchema = z
  .object({
    version: z.string(),
    package_token: z.string()
  })
  .strict()

export type SoftwarePackage = z.infer<typeof softwarePackageSchema>
export type PendingSoftwareAction = z.infer<typeof pendingSoftwareActionSchema>
export type SoftwarePackageDetails = z.infer<
  typeof softwarePackageDetailsSchema
>
export type SoftwarePreparation = z.infer<typeof softwarePreparationSchema>
export type SirilCommand = z.infer<typeof sirilCommandSchema>
export type SoftwareInstallRequest = z.infer<
  typeof softwareInstallRequestSchema
>

export type SoftwareConfirmationResult =
  | { ok: true; pending: PendingSoftwareAction }
  | { ok: false; code: string; message: string | null }
