import { z } from 'zod'

export const errorSchema = z
  .object({
    error: z
      .object({
        code: z.string(),
        message: z.string(),
        fields: z.array(
          z.object({ path: z.string(), message: z.string() }).strict()
        )
      })
      .strict(),
    request_id: z.string().uuid()
  })
  .strict()

export const configValuesSchema = z
  .object({
    host: z.string(),
    service_port: z.number().int(),
    data_dir: z.string(),
    allowed_origins: z.array(z.string()),
    import_roots: z.array(
      z.object({ id: z.string(), path: z.string() }).strict()
    ),
    file_workers: z.number().int().positive(),
    preview_workers: z.number().int().positive()
  })
  .strict()

export const configStateSchema = z
  .object({
    config_path: z.string(),
    default_workspace: z.string().nullable(),
    saved: configValuesSchema,
    config_token: z.string(),
    effective: configValuesSchema.nullable(),
    restart_required: z.boolean()
  })
  .strict()

export const configSaveSchema = z
  .object({
    config_token: z.string(),
    values: configValuesSchema,
    default_workspace: z.string().min(1).optional()
  })
  .strict()

export type ConfigValues = z.infer<typeof configValuesSchema>
export type ConfigState = z.infer<typeof configStateSchema>
export type ConfigSave = z.infer<typeof configSaveSchema>
