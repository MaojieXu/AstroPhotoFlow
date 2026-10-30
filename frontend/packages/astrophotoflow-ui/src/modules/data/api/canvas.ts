import { z } from 'zod'

import { createApiClient } from '../../../core/client'
import type { FetchApi } from '../../../core/client'
import { displayPreviewSchema } from './contracts'

export const canvasDataRequestSchema = z.object({
  entry_type: z.enum(['asset', 'dataset']),
  id: z.uuid(),
  version_id: z.uuid(),
  member_indexes: z.array(z.number().int().nonnegative()).nullable().optional()
}).strict()

const selection = z.object({
  kind: z.enum(['whole_file', 'fits_hdu']),
  hdu_index: z.number().int().nonnegative().nullable().optional()
}).strict()

export const scienceReferenceSchema = z.discriminatedUnion('kind', [
  z.object({
    kind: z.literal('asset_version'),
    asset_version_id: z.uuid(),
    selection
  }).strict(),
  z.object({
    kind: z.literal('dataset_version'),
    dataset_version_id: z.uuid(),
    members: z.array(z.object({
      member_index: z.number().int().nonnegative(),
      asset_version_id: z.uuid(),
      selection
    }).strict()).min(1)
  }).strict()
])

export const canvasDataSchema = z.object({
  native_type: z.enum(['APF_DATA_REFERENCE', 'APF_FILE_REFERENCE']),
  title: z.string(),
  reference: scienceReferenceSchema
}).strict()

export const canvasInspectSchema = z.object({
  title: z.string(), total: z.number().int().positive(), member_index: z.number().int().nonnegative(),
  asset_id: z.uuid(), asset_version_id: z.uuid(), name: z.string(),
  availability: z.enum(['unknown', 'available', 'changed', 'missing']),
  parameters: z.record(z.string(), z.unknown()), equipment: z.record(z.string(), z.string().nullable()),
  format: z.string().nullable(), width: z.number().int().nullable(), height: z.number().int().nullable(),
  bitpix: z.number().int().nullable(), pixel_type: z.string().nullable(),
  preview_status: z.enum(['available', 'pending', 'failed', 'unsupported', 'not_ready']),
  preview_url: z.string().nullable(), preview_error: z.string().nullable(),
  byte_size: z.number().int().nonnegative().nullable().optional(), content_hash: z.string().nullable().optional()
}).strict()

export type CanvasDataRequest = z.infer<typeof canvasDataRequestSchema>
export type CanvasData = z.infer<typeof canvasDataSchema>
export type CanvasInspect = z.infer<typeof canvasInspectSchema>
export type ScienceReference = z.infer<typeof scienceReferenceSchema>

export function createCanvasDataClient(fetchApi: FetchApi) {
  const client = createApiClient(fetchApi)
  return {
    inspect: (reference: ScienceReference, memberIndex: number) => client.send(
      '/astrophotoflow/api/v1/library/canvas-data/inspect', canvasInspectSchema, 'POST', { reference, member_index: memberIndex }
    ),
    getBlob: client.getBlob,
    display: (base: string) => client.send(base + '/display', displayPreviewSchema, 'POST', {}),
    displayStatus: (base: string) => client.get(base + '/display/status', displayPreviewSchema),
    prepare: (body: CanvasDataRequest) => client.send(
      '/astrophotoflow/api/v1/library/canvas-data', canvasDataSchema, 'POST', body
    )
  }
}
