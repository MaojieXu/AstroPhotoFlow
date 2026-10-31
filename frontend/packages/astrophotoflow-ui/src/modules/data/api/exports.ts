import { z } from 'zod'
import { createApiClient } from '../../../core/client'
import type { FetchApi } from '../../../core/client'
import { mediaSelectionSchema } from './media'

export const dataResultSchema = z.object({
  run_id: z.uuid(), execution_id: z.uuid(), node_id: z.string(), workflow_id: z.uuid().nullable(),
  state: z.enum(['preparing', 'completed', 'failed']), error: z.string().nullable(), reference: z.unknown(),
  input_bindings: z.record(z.string(), z.array(z.union([z.string(), z.number()]))).default({}),
  members: z.array(z.object({ name: z.string(), view_base: z.string(), selection: mediaSelectionSchema.partial(),
    format: z.string(), metadata: z.record(z.string(), z.unknown()).nullable(), byte_size: z.number().int().nonnegative() }).strict())
}).strict()
export type DataResult = z.infer<typeof dataResultSchema>

export const exportReceiptSchema = z.object({
  request_id: z.uuid(), state: z.enum(['queued', 'running', 'cancelling', 'completed', 'completed_with_errors', 'cancelled', 'failed', 'interrupted']),
  source: z.object({ run_id: z.uuid(), execution_id: z.uuid() }).strict(), target: z.enum(['library', 'local']),
  member_indexes: z.array(z.number().int().nonnegative()),
  destination: z.string().nullable(), settings: z.record(z.string(), z.unknown()),
  results: z.array(z.object({ member_index: z.number().int(), state: z.string(), path: z.string().optional(),
    registration_task_id: z.uuid().optional(), registration: z.record(z.string(), z.unknown()).optional(),
    error: z.object({ code: z.string(), message: z.string() }).optional() }).passthrough()),
  error: z.string().nullable()
}).strict()
export type ExportReceipt = z.infer<typeof exportReceiptSchema>

export function createDataExportClient(fetchApi: FetchApi) {
  const api = createApiClient(fetchApi)
  const root = '/astrophotoflow/api/v1'
  return {
    result: (run: string, execution: string) => api.get(`${root}/data-nodes/${run}/${execution}`, dataResultSchema),
    submit: (body: unknown) => api.send(`${root}/exports`, exportReceiptSchema, 'POST', body),
    status: (id: string) => api.get(`${root}/exports/${id}`, exportReceiptSchema),
    cancel: (id: string) => api.send(`${root}/exports/${id}/cancel`, exportReceiptSchema, 'POST', {}),
    choose: (body: { mode: 'file' | 'folder'; suggested_name: string }) => api.send(`${root}/exports/select-local`, z.object({ path: z.string().nullable() }).strict(), 'POST', body)
  }
}
