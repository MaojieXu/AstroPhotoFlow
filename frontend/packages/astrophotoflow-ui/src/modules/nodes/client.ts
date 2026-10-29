import { z } from 'zod'
import type { FetchApi } from '../../core/client'
import { ApiClientError } from '../../core/client'

export const nodeParameterSchema = z.object({
  name: z.string(), kind: z.enum(['int', 'float', 'string', 'boolean', 'choice']),
  default: z.json(), minimum: z.number().nullable(), maximum: z.number().nullable(),
  step: z.number().nullable(), choices: z.array(z.json()).nullable(),
  nullable: z.boolean(), advanced: z.boolean()
})
export const savedNodeSchema = z.object({
  native_type: z.string(), content_token: z.string(),
  definition: z.object({
    definition_id: z.uuid(), name: z.string(), description: z.string(), source: z.enum(['package', 'custom']),
    inputs: z.array(z.object({ name: z.string(), type: z.string() })),
    outputs: z.array(z.object({ name: z.string(), type: z.string() })),
    parameters: z.array(nodeParameterSchema),
    execution: z.object({ package_id: z.string(), operation_id: z.string() }).passthrough()
  })
})
export const nodeCapabilitySchema = z.object({
  node: savedNodeSchema, available: z.boolean(), reason: z.string().nullable(),
  preview: z.object({ kind: z.literal('science-image'), input: z.string(), max_edge: z.literal(1024) }).nullable(),
  help: z.string(), examples: z.array(z.record(z.string(), z.json())),
  operation: z.object({ package_id: z.string(), operation_id: z.string(), parameters: z.array(nodeParameterSchema) }).passthrough()
})
export type NodeCapability = z.infer<typeof nodeCapabilitySchema>
export type SavedNode = z.infer<typeof savedNodeSchema>
export type NodeParameter = z.infer<typeof nodeParameterSchema>

export function createNodeClient(fetchApi: FetchApi) {
  async function read(path: string) {
    const response = await fetchApi('/astrophotoflow/api/v1/nodes' + path)
    if (!response.ok) {
      const body = await response.json() as { error: { message: string; code: string } }
      throw new ApiClientError(body.error.message, 'service', response.status, body.error.code)
    }
    return response.json()
  }
  return {
    async list(): Promise<NodeCapability[]> { return z.array(nodeCapabilitySchema).parse(await read('')) },
    async get(id: string): Promise<NodeCapability> { return nodeCapabilitySchema.parse(await read('/' + encodeURIComponent(id))) }
  }
}
