import { zProjectPage } from '../../../generated/api/zod.gen'
import type { LocalSelectionFile } from '../../../generated/api/types.gen'
import {
  zImportContentProgress,
  zImportPreviewProgress,
  zImportReport,
  zAssetTaskOut
} from '../../../generated/api/zod.gen'
import {
  zAssetContentObservation,
  zAssetOut,
  zAssetParameters,
  zAssetVersionOut,
  zCalibrationTarget,
  zCalibrationTargetOption,
  zDatasetMemberOut,
  zDatasetMemberParametersUpdateOut,
  zDatasetVersionOut,
  zEquipmentPage,
  zEquipmentSetupOut,
  zFitsHduOut,
  zImportAccepted,
  zImportRootEntryOut,
  zImportRootOut,
  zImportTaskStateOut,
  zLibraryEntriesRemove,
  zLibraryEntriesRemoveOut,
  zLibraryFilterOptions,
  zLibraryTrashDeleteOut,
  zLibraryTrashItemOut,
  zLibraryTrashPreviewOut,
  zLibraryTrashSelection,
  zLocalSelectionOut,
  zProjectAssetReferenceOut,
  zTaskItemOut
} from '../../../generated/api/zod.gen'
import {
  zServiceCapabilities,
  zProjectOut,
  zAutoStretch,
  zDisplayPreviewState
} from '../../../generated/api/zod.gen'
import {
  zCapturePresetOut,
  zLibraryItemPage,
  zDatasetOut,
  zDatasetMemberPage,
  zProjectDatasetReferenceOut
} from '../../../generated/api/zod.gen'
import { z } from 'zod'

export const capabilitiesSchema = zServiceCapabilities

export const pageSchema = <T extends z.ZodType>(item: T) =>
  zProjectPage.omit({ items: true }).extend({ items: z.array(item) })

export const projectSchema = zProjectOut

export const equipmentSchema = zEquipmentPage.shape.items.element

export const setupComponentSchema = zEquipmentSetupOut.shape.components.element

export const equipmentSetupSchema = zEquipmentSetupOut

export const capturePresetSchema = zCapturePresetOut
export type EquipmentSetup = z.infer<typeof equipmentSetupSchema>
export type SetupComponent = z.infer<typeof setupComponentSchema>
export type CapturePreset = z.infer<typeof capturePresetSchema>

export const assetVersionSchema = zAssetVersionOut

export const assetSchema = zAssetOut

export const assetContentObservationSchema = zAssetContentObservation

export const projectAssetReferenceSchema = zProjectAssetReferenceOut

export { errorSchema } from '../../../core/contracts'

export type Capabilities = z.infer<typeof capabilitiesSchema>
export type Project = z.infer<typeof projectSchema>
export type Equipment = z.infer<typeof equipmentSchema>
export type Asset = z.infer<typeof assetSchema>
export type ProjectAssetReference = z.infer<typeof projectAssetReferenceSchema>

export const importRootSchema = zImportRootOut

export const importRootListSchema = z.array(importRootSchema)
export const importEntrySchema = zImportRootEntryOut

export type LocalImportFile = LocalSelectionFile & { root_id?: string }
export const localSelectionSchema = zLocalSelectionOut

export const importContentProgressSchema = zImportContentProgress

export const importPreviewProgressSchema = zImportPreviewProgress

export const importReportSchema = zImportReport

export const importAcceptedSchema = zImportAccepted

export const uploadCreatedSchema = zImportAccepted

export const taskActionSchema = zImportTaskStateOut

export const datasetSchema = zDatasetOut
export const calibrationTargetSchema = zCalibrationTarget

export const calibrationBindingsSchema =
  zDatasetVersionOut.shape.calibration_defaults.unwrap()
export const calibrationTargetOptionSchema = zCalibrationTargetOption

export type CalibrationTarget = z.infer<typeof calibrationTargetSchema>
export type CalibrationBindings = z.infer<typeof calibrationBindingsSchema>
export type CalibrationTargetOption = z.infer<
  typeof calibrationTargetOptionSchema
>
export const datasetMemberSchema = zDatasetMemberOut

export const datasetVersionSchema = zDatasetVersionOut

export const libraryItemSchema = zLibraryItemPage.shape.items.element
export const libraryFilterOptionsSchema = zLibraryFilterOptions

export const libraryEntriesRemoveSchema = zLibraryEntriesRemoveOut

export const libraryEntriesRemoveRequestSchema = zLibraryEntriesRemove

export const libraryTrashItemSchema = zLibraryTrashItemOut

export const libraryTrashSelectionSchema = zLibraryTrashSelection

export const libraryTrashDeleteSchema = zLibraryTrashDeleteOut

export const libraryTrashPreviewSchema = zLibraryTrashPreviewOut

export const datasetMemberParametersUpdateSchema =
  zDatasetMemberParametersUpdateOut

export const datasetReferenceSchema = zProjectDatasetReferenceOut
export const taskItemSchema = zTaskItemOut

export const taskSchema = zAssetTaskOut

export const fitsHduSchema = zFitsHduOut

export const assetParametersSchema = zAssetParameters

export const previewStretchSchema = zAutoStretch

export const displayPreviewSchema = zDisplayPreviewState

export const datasetMemberPageSchema = zDatasetMemberPage
