import type { CalibrationPatch, LibraryCalibrationProjection, LibraryCalibrationSlot } from '../../../generated/api/types.gen'
import type { AssetRecord, DatasetRecord } from '../workspace/recordTypes'
import { assetRecord, isDatasetRecord, isMemberRecord, recordEntity } from '../workspace/recordTypes'
import { uiT } from '../../../core/i18n'

export type CalibrationSlot = keyof CalibrationPatch
type CalibrationChoice = NonNullable<CalibrationPatch['bias']>
export const calibrationSlots: CalibrationSlot[] = ['dark', 'flat', 'bias', 'dark_flat']
export interface CalibrationEditContext {
  workspaceId: string
  saved: () => Promise<void>
  runSave: (key: string, operation: () => Promise<void>) => Promise<void>
  cancel: (key: string) => void
}
export interface InlineCalibrationBinding {
  slot: CalibrationSlot
  label: string
  value: LibraryCalibrationSlot
  context?: CalibrationEditContext & { assetId: string; revision: number }
}
export function calibrationChoiceToken(choice: CalibrationChoice | null) {
  return choice?.mode === 'target' ? choice.target.id : choice?.mode ?? 'unconfigured'
}
export function calibrationCellLabel(value: LibraryCalibrationSlot) {
  if (value.status === 'not_applicable') return '—'
  if (value.status === 'disabled') return uiT('apfUi.calibration_disabled')
  if (value.status === 'target') return value.target_detail?.name ?? uiT('apfUi.calibration_target_unavailable')
  return uiT('apfUi.calibration_unconfigured')
}
export function rowCalibration(row: AssetRecord | DatasetRecord, context: CalibrationEditContext): InlineCalibrationBinding[] | undefined {
  const entity = recordEntity(row)
  const projection: LibraryCalibrationProjection | null | undefined = 'calibration_projection' in row
    ? row.calibration_projection : 'calibration_projection' in entity ? entity.calibration_projection : undefined
  if (!projection) return
  const asset = assetRecord(row)
  return calibrationSlots.flatMap(slot => {
    const value = projection.slots[slot]
    if (!value) return []
    return [{ slot, label: uiT(slot === 'dark' ? 'apfUi.dark' : slot === 'flat' ? 'apfUi.flat' : slot === 'bias' ? 'apfUi.bias' : 'apfUi.dark_flat'), value,
      context: !isDatasetRecord(row) && !isMemberRecord(row) && entity.id && value.status !== 'not_applicable'
        ? { ...context,
          assetId: asset?.id ?? entity.id, revision: asset?.revision ?? entity.revision } : undefined }]
  })
}
