import { z } from 'zod'

const id = z.string().uuid()
const timestamp = z.string().datetime({ offset: true })
const nullableText = z.string().nullable()

export const capabilitiesSchema = z.object({
  stage: z.literal('foundation'),
  shared_library_read: z.boolean(), project_assets_read: z.boolean(),
  project_management: z.boolean(), equipment_management: z.boolean(),
  capture_profile_management: z.boolean(), asset_import: z.boolean(),
  asset_reference_write: z.boolean(), asset_preview: z.boolean(),
  calibration_matching: z.boolean(), asset_publish: z.boolean()
}).strict()

export const pageSchema = <T extends z.ZodType>(item: T) => z.object({
  items: z.array(item), total: z.number().int().nonnegative(),
  limit: z.number().int().positive(), offset: z.number().int().nonnegative()
}).strict()

export const projectSchema = z.object({
  id, name: z.string(), target_name: nullableText, notes: nullableText,
  capture_profile_ids: z.array(id), status: z.enum(['active', 'archived']),
  revision: z.number().int().positive(), created_at: timestamp, updated_at: timestamp
}).strict()

export const equipmentSchema = z.object({
  id, kind: z.enum(['camera', 'optical_system', 'filter']), name: z.string(),
  model: nullableText, serial_number: nullableText, notes: nullableText,
  specs: z.record(z.string(), z.unknown()), status: z.enum(['active', 'archived']),
  revision: z.number().int().positive(), created_at: timestamp, updated_at: timestamp
}).strict()

export const captureProfileSchema = z.object({
  id, name: z.string(), camera_id: id, optical_system_id: id.nullable(), filter_id: id.nullable(),
  frame_type: z.enum(['light', 'bias', 'dark', 'flat', 'dark_flat']),
  exposure_seconds: z.number().nullable(), gain: z.number().nullable(), offset: z.number().nullable(),
  sensor_temperature_c: z.number().nullable(), binning_x: z.number().int().nullable(),
  binning_y: z.number().int().nullable(), notes: nullableText, status: z.enum(['active', 'archived']),
  revision: z.number().int().positive(), created_at: timestamp, updated_at: timestamp
}).strict()

export const assetVersionSchema = z.object({
  id, asset_id: id, version_number: z.number().int().positive(),
  storage_mode: z.enum(['reference', 'managed']), storage_location: z.string(),
  byte_size: z.number().int().nonnegative().nullable(), content_hash: nullableText,
  availability: z.enum(['unknown', 'available', 'changed', 'missing']),
  camera_id: id.nullable(), optical_system_id: id.nullable(), filter_id: id.nullable(),
  capture_profile_id: id.nullable(), frame_type: z.enum(['light', 'bias', 'dark', 'flat', 'dark_flat']).nullable(),
  calibration_level: z.enum(['individual', 'master']).nullable(),
  capture_snapshot: z.record(z.string(), z.unknown()).nullable(),
  scientific_metadata: z.record(z.string(), z.unknown()).nullable(), created_at: timestamp
}).strict()

export const assetSchema = z.object({
  id, name: z.string(), scope: z.enum(['shared', 'project']), owner_project_id: id.nullable(),
  role: z.enum(['raw', 'calibration', 'intermediate', 'final']), current_version_id: id.nullable(),
  created_at: timestamp, current_version: assetVersionSchema.nullable()
}).strict()

export const projectAssetReferenceSchema = z.object({
  id, project_id: id, asset_version_id: id, added_at: timestamp,
  asset: assetSchema, version: assetVersionSchema
}).strict()

export const errorSchema = z.object({
  error: z.object({
    code: z.string(), message: z.string(),
    fields: z.array(z.object({ path: z.string(), message: z.string() }).strict())
  }).strict(),
  request_id: id
}).strict()

export type Capabilities = z.infer<typeof capabilitiesSchema>
export type Project = z.infer<typeof projectSchema>
export type Equipment = z.infer<typeof equipmentSchema>
export type CaptureProfile = z.infer<typeof captureProfileSchema>
export type Asset = z.infer<typeof assetSchema>
export type ProjectAssetReference = z.infer<typeof projectAssetReferenceSchema>
