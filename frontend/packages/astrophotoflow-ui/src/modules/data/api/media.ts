import { z } from 'zod'

import { createApiClient } from '../../../core/client'
import type { FetchApi } from '../../../core/client'

export const mediaSelectionSchema = z.object({
  consumer_id: z.string().nullable().optional(), generation: z.number().int().nonnegative().default(0),
  hdu_index: z.number().int().nonnegative().nullable().optional(),
  array_key: z.string().nullable().optional(),
  x_axis: z.number().int().nonnegative().nullable().optional(),
  y_axis: z.number().int().nonnegative().nullable().optional(),
  channel_axis: z.number().int().nonnegative().nullable().optional(),
  slices: z.record(z.string(), z.number().int().nonnegative()).default({}),
  frame_index: z.number().int().nonnegative().nullable().optional(),
  media_time: z.number().nonnegative().nullable().optional(),
  playback_key: z.string().nullable().optional(),
  proxy: z.boolean().default(false)
}).strict()

export const mediaStateSchema = z.object({
  key: z.string(), status: z.enum(['generating', 'available', 'failed', 'unsupported']),
  phase: z.enum(['queued', 'preparing']).nullable().optional(),
  kind: z.enum(['image', 'video']), width: z.number().int().nonnegative(), height: z.number().int().nonnegative(),
  max_level: z.number().int().nonnegative(), tile_size: z.literal(512), selection: mediaSelectionSchema,
  arrays: z.array(z.object({ key: z.string(), shape: z.array(z.number().int().nonnegative()), dtype: z.string(), numeric: z.boolean() }).strict()),
  needs_selection: z.boolean(), overview_url: z.string().nullable(), tile_url: z.string().nullable(),
  video_url: z.string().nullable(), mime_type: z.string().nullable(), proxy: z.boolean(),
  frame_index: z.number().int().nonnegative().nullable(), media_time: z.number().nullable(),
  frame_count: z.number().int().nonnegative().nullable(), duration: z.number().nullable(), note: z.string().nullable(),
  error: z.object({ code: z.string(), message: z.string() }).strict().nullable()
}).strict()

export type MediaState = z.infer<typeof mediaStateSchema>
export type MediaSelection = z.infer<typeof mediaSelectionSchema>
export type MediaMember = { title: string; basePath: string; selection?: Partial<MediaSelection> }
export type MediaViewerRequest = { index: number; total: number; member: (index: number, signal: AbortSignal) => Promise<MediaMember> }

export function createMediaClient(fetchApi: FetchApi) {
  const client = createApiClient(fetchApi)
  return {
    prepare: (base: string, selection: Partial<MediaSelection>) => client.send(base + '/viewer', mediaStateSchema, 'POST', selection),
    status: (base: string, key: string) => client.get(base + '/viewer/' + key + '/status', mediaStateSchema)
  }
}
