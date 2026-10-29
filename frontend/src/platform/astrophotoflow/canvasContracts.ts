import { canvasDataRequestSchema, canvasDataSchema } from '@astrophotoflow/ui'
import { z } from 'zod'

export const canvasPageSchema = z.object({
  workflow_id: z.uuid(), graph_id: z.uuid(), title: z.string(),
  content_token: z.string(), control_token: z.string().nullable()
}).strict()

export const canvasAddRequestSchema = z.object({
  operation_id: z.uuid(), page_id: z.uuid(), workflow_id: z.uuid(), graph_id: z.uuid(),
  content_token: z.string(), control_token: z.string(), source: canvasDataRequestSchema
}).strict()

export const canvasAddResultSchema = z.object({
  operation_id: z.uuid(), page_id: z.uuid(), workflow_id: z.uuid(), graph_id: z.uuid(),
  applied: z.boolean().nullable(), node_id: z.union([z.string(), z.number()]).nullable(),
  error: z.object({ code: z.string(), message: z.string(), fields: z.array(z.record(z.string(), z.string())) }).nullable()
}).strict()

export const canvasCommandSchema = z.object({ request: canvasAddRequestSchema, data: canvasDataSchema }).strict()
export type CanvasPage = z.infer<typeof canvasPageSchema>
export type CanvasCommand = z.infer<typeof canvasCommandSchema>
export type CanvasAddResult = z.infer<typeof canvasAddResultSchema>
export type CanvasEvent = { action: 'state'; state: CanvasPage | null } | { action: 'result'; result: CanvasAddResult }
