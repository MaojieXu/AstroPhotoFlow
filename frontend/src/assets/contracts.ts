import { z } from 'zod'

const id = z.string().uuid()
const timestamp = z.string().datetime({ offset: true })
const nullableText = z.string().nullable()

export const capabilitiesSchema = z.object({
  stage: z.literal('ingestion'),
  shared_library_read: z.boolean(), project_assets_read: z.boolean(),
  project_management: z.boolean(), equipment_management: z.boolean(),
  capture_profile_management: z.boolean(), asset_import: z.boolean(),
  asset_reference_write: z.boolean(), asset_preview: z.boolean(), asset_metadata_edit: z.boolean(),
  dataset_management: z.boolean(), asset_task_management: z.boolean(),
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
  parameter_mode: z.enum(['iso','gain']).nullable(), iso: z.number().int().nullable(),
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
  role: z.enum(['raw', 'calibration', 'intermediate', 'final']),
  calibration_level: z.enum(['individual', 'master']).nullable(), current_version_id: id.nullable(),
  classification: z.object({
    frame_class: z.enum(['subframe', 'masterframe', 'video']).nullable(),
    frame_type: z.enum(['light', 'bias', 'dark', 'flat', 'dark_flat']).nullable()
  }).strict().nullable(),
  parameters: z.record(z.string(), z.unknown()), value_sources: z.record(z.string(), z.string()),
  notes: nullableText, status: z.enum(['active', 'archived']), revision: z.number().int().positive(),
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


export const importRootSchema = z.object({ id: z.string(), label: z.string(), available: z.boolean() }).strict()
export const importRootListSchema = z.array(importRootSchema)
export const importEntrySchema = z.object({
  name: z.string(), path: z.string(), kind: z.enum(['file', 'directory']),
  format: z.string().nullable(), supported: z.boolean(), size: z.number().int().nonnegative().nullable()
}).strict()
export const importAcceptedSchema = z.object({ task_id: id, status: z.literal('queued') }).strict()
export const uploadCreatedSchema = z.object({ task_id: id, status: z.literal('queued') }).strict()
export const taskActionSchema = z.object({
  task_id: id,
  status: z.enum(['queued', 'running', 'cancelling', 'completed', 'completed_with_errors', 'failed', 'cancelled', 'interrupted'])
}).strict()

export const datasetSchema = z.object({
  id, name: z.string(), notes: nullableText, status: z.enum(['active', 'archived']),
  revision: z.number().int().positive(), current_version_id: id.nullable(),
  member_count: z.number().int().nonnegative(), created_at: timestamp, updated_at: timestamp
}).strict()
export const datasetMemberSchema = z.object({
  id, dataset_version_id: id, asset_version_id: id, position: z.number().int().nonnegative(),
  relative_path: nullableText, asset: assetSchema, version: assetVersionSchema
}).strict()
export const datasetVersionSchema = z.object({
  id, dataset_id: id, version_number: z.number().int().positive(), created_at: timestamp,
  members: z.array(datasetMemberSchema)
}).strict()
export const libraryItemSchema = z.discriminatedUnion('entry_type', [
  z.object({ entry_type: z.literal('asset'), asset: assetSchema, import_issue: nullableText }).strict(),
  z.object({ entry_type: z.literal('dataset'), dataset: datasetSchema, version: datasetVersionSchema.nullable(), import_issue: nullableText }).strict()
])
export const libraryFilterOptionsSchema = z.object({
  frame_classes: z.array(z.string()), frame_types: z.array(z.string()), roles: z.array(z.string()),
  parameter_modes: z.array(z.string()), bin_values: z.array(z.string()),
  equipment: z.object({
    camera_id: z.array(z.object({id, name:z.string()})),
    optical_system_id: z.array(z.object({id, name:z.string()})),
    filter_id: z.array(z.object({id, name:z.string()}))
  }),
  numeric_ranges: z.record(z.string(), z.object({min:z.number(),max:z.number()}))
}).strict()
export const libraryEntriesRemoveSchema = z.object({
  removed_count: z.number().int().nonnegative()
}).strict()
export const libraryEntriesRemoveRequestSchema = z.object({
  items: z.array(z.object({
    entry_type: z.enum(['asset','dataset']), id, revision: z.number().int().positive(), current_version_id: id.nullable()
  }).strict()).min(1)
}).strict()
export const datasetMemberParametersUpdateSchema = z.object({
  dataset_id: id, revision: z.number().int().positive(), version_id: id, assets: z.array(assetSchema)
}).strict()
export const datasetReferenceSchema = z.object({
  id, project_id: id, dataset_id: id, dataset_version_id: id,
  base_revision: z.number().int().positive(), added_at: timestamp,
  dataset: datasetSchema, version: datasetVersionSchema
}).strict()
export const taskItemSchema = z.object({
  id, task_id: id, root_item_id: id, retry_of_item_id: id.nullable(),
  root_id: z.string(), source_path: z.string(), position: z.number().int().nonnegative(),
  status: z.string(), content_status: z.string(), metadata_status: z.string(), preview_status: z.string(),
  asset_id: id.nullable(), asset_version_id: id.nullable(), error: z.record(z.string(), z.unknown()).nullable(),
  created_at: timestamp, updated_at: timestamp
}).strict()
export const taskSchema = z.object({
  id, status: z.enum(['queued', 'running', 'cancelling', 'completed', 'completed_with_errors', 'failed', 'cancelled', 'interrupted']),
  sources: z.array(z.record(z.string(), z.unknown())), storage_mode: z.enum(['reference', 'managed']),
  classification: z.record(z.string(), z.unknown()), parameters: z.record(z.string(), z.unknown()),
  notes: nullableText, dataset_name: nullableText, target_dataset_id: id.nullable(),
  dataset_base_revision: z.number().int().positive().nullable(), dataset_id: id.nullable(),
  enumeration_completed: z.boolean(), retry_of_task_id: id.nullable(),
  report: z.record(z.string(), z.unknown()), error: z.record(z.string(), z.unknown()).nullable(),
  created_at: timestamp, updated_at: timestamp, items: z.array(taskItemSchema),
  items_total: z.number().int().nonnegative(), items_completed: z.number().int().nonnegative(),
  items_limit: z.number().int().positive(),
  items_offset: z.number().int().nonnegative()
}).strict()
export const fitsHduSchema = z.object({
  id, asset_version_id: id, hdu_index: z.number().int().nonnegative(), name: nullableText,
  hdu_type: z.string(), shape: z.array(z.number().int().nonnegative()).nullable(),
  bitpix: z.number().int().nullable(), pixel_type: nullableText, bscale: z.number().nullable(),
  bzero: z.number().nullable(), bunit: nullableText, parser_version: z.string(),
  supported_kind: z.enum(['mono', 'bayer', 'rgb']).nullable(), is_selected: z.boolean(),
  parse_error: nullableText
}).strict()

export const assetParametersSchema = z.object({
  camera_id: id.nullable(), optical_system_id: id.nullable(), filter_id: id.nullable(),
  parameter_mode: z.enum(['iso', 'gain', 'standard']), iso: z.number().int().positive().nullable(),
  gain: z.number().nullable(), offset: z.number().nullable(), exposure_seconds: z.number().nullable(),
  integration_seconds: z.number().nullable(), sensor_temperature_c: z.number().nullable(),
  binning_x: z.number().int().nullable(), binning_y: z.number().int().nullable(),
  cfa_pattern: z.enum(['MONO', 'RGGB', 'BGGR', 'GRBG', 'GBRG', 'XTRANS', 'QUAD_BAYER']).nullable()
}).strict()
