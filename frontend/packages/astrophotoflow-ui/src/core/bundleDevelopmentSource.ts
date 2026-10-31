import { z } from 'zod'

export const bundleDevelopmentSourceSchema = z.object({
  root: z.string(),
  head: z.string().nullable(),
  dirty: z.boolean(),
  fingerprint: z.string(),
  state: z.enum(['building', 'ready', 'failed']),
  error: z.string().nullable(),
  software_version: z.string().nullable(),
  bundle_version: z.string().nullable()
}).strict()
