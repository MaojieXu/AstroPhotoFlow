import { z } from 'zod'
import { bundleDevelopmentSourceSchema } from '../../core/bundleDevelopmentSource'

import { createApiClient } from '../../core/client'
import type { FetchApi } from '../../core/client'

export const analysisResultSchema = z
  .object({
    kind: z.enum(['metrics', 'table', 'series', 'text', 'json']),
    title: z.string(),
    source: z.string(),
    unit: z.string().nullable(),
    columns: z.array(z.string()),
    rows: z.array(z.array(z.json())),
    values: z.record(z.string(), z.json()),
    text: z.string().nullable(),
    sample: z.string().nullable(),
    member_index: z.number().int().nonnegative().nullable()
  })
  .strict()

export const runCallResultSchema = z
  .object({
    prompt_id: z.uuid(),
    call_id: z.uuid(),
    node_id: z.string(),
    workflow_id: z.uuid().nullable().optional(),
    calculation_signature: z.string().nullable().optional(),
    package_id: z.string().nullable().optional(),
    software_version: z.string().nullable().optional(),
    bundle_version: z.string().nullable().optional(),
    bundle_commit: z.string().nullable().optional(),
    development_source: bundleDevelopmentSourceSchema.nullable().optional(),
    operation_id: z.string().nullable().optional(),
    definition_token: z.string().nullable().optional(),
    state: z.enum([
      'starting',
      'running',
      'completed',
      'failed',
      'cancelled',
      'unknown'
    ]),
    ports: z.array(
      z
        .object({
          name: z.string(),
          type: z.string(),
          members: z.number().int().nonnegative(),
          formats: z.array(z.string()).default([]),
          names: z.array(z.string()).default([])
        })
        .strict()
    ),
    preview_error: z.string().nullable().optional(),
    observation: z.unknown().nullable().optional(),
    error: z
      .object({
        code: z.string(),
        message: z.string(),
        fields: z.array(z.object({ path: z.string(), message: z.string() }))
      })
      .nullable()
      .optional()
  })
  .strict()

export type AnalysisResult = z.infer<typeof analysisResultSchema>
export type RunCallResult = z.infer<typeof runCallResultSchema>

export function runResultBase(
  result: Pick<RunCallResult, 'prompt_id' | 'call_id'>
) {
  return `/astrophotoflow/api/v1/runs/${encodeURIComponent(result.prompt_id)}/calls/${encodeURIComponent(result.call_id)}`
}

export function runOutputBase(
  result: Pick<RunCallResult, 'prompt_id' | 'call_id'>,
  outputIndex: number,
  memberIndex: number
) {
  return `${runResultBase(result)}/outputs/${outputIndex}/members/${memberIndex}`
}

export function createRunResultClient(fetchApi: FetchApi) {
  const client = createApiClient(fetchApi)
  return {
    get: (result: Pick<RunCallResult, 'prompt_id' | 'call_id'>) =>
      client.get(runResultBase(result), runCallResultSchema),
    analysis: (
      result: Pick<RunCallResult, 'prompt_id' | 'call_id'>,
      outputIndex: number,
      memberIndex: number
    ) =>
      client.get(
        runOutputBase(result, outputIndex, memberIndex) + '/analysis',
        z.array(analysisResultSchema)
      )
  }
}
