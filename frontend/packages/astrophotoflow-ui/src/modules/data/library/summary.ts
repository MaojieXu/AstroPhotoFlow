import type { LibraryItemPage, LibraryMetadataSummary, LibraryParameterSummary } from '../../../generated/api/types.gen'
import { uiT } from '../../../core/i18n'
import { displayLabel } from './presentation'

export type LibrarySummary = LibraryItemPage['items'][number]
export type MetadataRow = { summary: LibraryMetadataSummary }
export type MetadataField = keyof LibraryParameterSummary | 'frame_class' | 'frame_type' | 'camera_id' | 'optical_system_id' | 'filter_id' | 'storage_mode' | 'availability'
type ScalarSummary = Pick<LibraryParameterSummary['gain'], 'state'> & { value: string | number | null }

export function hasSummary(value: unknown): value is MetadataRow & Pick<LibrarySummary, 'id' | 'input_ready'> & Partial<Pick<LibrarySummary, 'import_issue'>> {
  return typeof value === 'object' && value !== null && 'summary' in value && value.summary !== null && 'id' in value && typeof value.id === 'string' && 'input_ready' in value && typeof value.input_ready === 'boolean'
}

export function fieldSummary(row: MetadataRow, field: MetadataField): ScalarSummary {
  switch (field) {
    case 'frame_class': case 'frame_type': return row.summary.classification[field]
    case 'storage_mode': case 'availability': return row.summary[field]
    case 'camera_id': case 'optical_system_id': case 'filter_id': {
      const slot = field === 'camera_id' ? 'camera' : field === 'filter_id' ? 'filter' : 'optical_system'
      const value = row.summary[slot]
      return { state: value.state, value: value.value?.id ?? null }
    }
    default: return row.summary.parameters[field]
  }
}

export function summaryRaw(row: MetadataRow, field: MetadataField): string | number {
  const value = fieldSummary(row, field)
  return value.state === 'mixed' ? 'mixed' : value.state === 'consistent' ? value.value ?? '' : ''
}

export function summaryText(row: MetadataRow, field: MetadataField, format: (value: unknown) => string = String): string {
  const value = fieldSummary(row, field)
  return value.state === 'mixed' ? uiT('apfUi.mixed') : value.state === 'consistent' && value.value !== null ? format(value.value) : '—'
}

function parameterValue<T extends { state: string; value: string | number | null }>(field: T): T['value'] | 'mixed' {
  return field.state === 'mixed' ? 'mixed' : field.value
}
export function summaryParameters(row: MetadataRow) {
  const parameters = row.summary.parameters
  const equipmentId = (key: 'camera' | 'optical_system' | 'filter') => {
    const field = row.summary[key]
    return field.state === 'mixed' ? 'mixed' : field.value?.id ?? null
  }
  return {
    parameter_mode: parameterValue(parameters.parameter_mode), iso: parameterValue(parameters.iso),
    gain: parameterValue(parameters.gain), offset: parameterValue(parameters.offset),
    exposure_seconds: parameterValue(parameters.exposure_seconds), integration_seconds: parameterValue(parameters.integration_seconds),
    sensor_temperature_c: parameterValue(parameters.sensor_temperature_c), binning_x: parameterValue(parameters.binning_x),
    binning_y: parameterValue(parameters.binning_y), cfa_pattern: parameterValue(parameters.cfa_pattern),
    camera_id: equipmentId('camera'), optical_system_id: equipmentId('optical_system'), filter_id: equipmentId('filter')
  }
}
export type ParameterDisplayValues = ReturnType<typeof summaryParameters>

export function summaryClassification(row: MetadataRow) {
  return { frame_class: summaryRaw(row, 'frame_class'), frame_type: summaryRaw(row, 'frame_type') }
}

export function summaryClassificationText(row: MetadataRow): string {
  const classification = row.summary.classification
  const parts = (['frame_class', 'frame_type'] as const).filter(field => classification[field].state !== 'unknown')
  return parts.length ? parts.map(field => summaryText(row, field, displayLabel)).join(' / ') : '—'
}

export function summaryEquipment(row: MetadataRow, key: 'camera_id' | 'optical_system_id' | 'filter_id'): string | undefined {
  const slot = key === 'camera_id' ? 'camera' : key === 'filter_id' ? 'filter' : 'optical_system'
  const value = row.summary[slot]
  return value.state === 'mixed' ? uiT('apfUi.mixed') : value.value?.name
}

export function isLibrarySummary(value: unknown): value is LibrarySummary {
  return hasSummary(value) && 'entry_type' in value && (value.entry_type === 'asset' || value.entry_type === 'dataset') && 'thumbnail' in value
}
