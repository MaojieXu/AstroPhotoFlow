import { canvasDataRequestSchema, canvasDataSchema, savedNodeSchema } from '@astrophotoflow/ui'
import { z } from 'zod'

export const canvasPageSchema = z.object({
  workflow_id: z.uuid(), graph_id: z.uuid(), title: z.string(),
  content_token: z.string()
}).strict()

export const canvasAddRequestSchema = z.object({
  operation_id: z.uuid(), page_id: z.uuid(), workflow_id: z.uuid(), graph_id: z.uuid(),
  content_token: z.string(), source: canvasDataRequestSchema
}).strict()

export const canvasAddResultSchema = z.object({
  operation_id: z.uuid(), page_id: z.uuid(), workflow_id: z.uuid(), graph_id: z.uuid(),
  applied: z.boolean().nullable(), node_id: z.union([z.string(), z.number()]).nullable(),
  error: z.object({ code: z.string(), message: z.string(), fields: z.array(z.record(z.string(), z.string())) }).nullable()
  ,graph: z.record(z.string(), z.json()).nullable().optional(),
  link_id: z.union([z.string(), z.number()]).nullable().optional(),
  content_token: z.string().nullable().optional()
}).strict()

export const canvasEditSchema = z.discriminatedUnion('action', [
  z.object({ action: z.literal('inspect') }),
  z.object({ action: z.literal('add_node'), definition_id: z.uuid(), parameters: z.record(z.string(), z.json()).default({}) }),
  z.object({ action: z.literal('set_parameter'), node_id: z.union([z.string(), z.number()]), name: z.string(), value: z.json() }),
  z.object({ action: z.literal('delete_node'), node_id: z.union([z.string(), z.number()]) }),
  z.object({ action: z.literal('connect'), source_node_id: z.union([z.string(), z.number()]), source_port: z.string(), target_node_id: z.union([z.string(), z.number()]), target_port: z.string() })
])
export const canvasGraphCommandSchema = z.object({
  request: canvasAddRequestSchema.omit({ source: true }).extend({ edit: canvasEditSchema }),
  definition: savedNodeSchema.nullable()
}).strict()
export const canvasCommandSchema = z.union([z.object({ request: canvasAddRequestSchema, data: canvasDataSchema }).strict(), canvasGraphCommandSchema])
export type CanvasGraphCommand = z.infer<typeof canvasGraphCommandSchema>
export type CanvasPage = z.infer<typeof canvasPageSchema>
export type CanvasCommand = z.infer<typeof canvasCommandSchema>
export type CanvasAddResult = z.infer<typeof canvasAddResultSchema>
export type CanvasEvent = { action: 'state'; state: CanvasPage | null } | { action: 'result'; result: CanvasAddResult }
