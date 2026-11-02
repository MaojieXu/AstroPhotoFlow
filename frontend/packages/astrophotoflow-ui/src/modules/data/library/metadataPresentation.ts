import type {
  AssetParametersPatch,
  AssetClassification
} from '../../../generated/api/types.gen'
import { uiT } from '../../../core/i18n'
import { ApiClientError } from '../api/client'
import type { WorkspaceRecord } from '../workspace/recordTypes'
import { assetRecord, isDatasetRecord } from '../workspace/recordTypes'
import { binValue, binEditValue } from '../assets/binning'
import { displayLabel, parameterSummary } from './presentation'
import {
  hasSummary,
  summaryRaw,
  summaryText,
  summaryParameters,
  summaryClassification,
  summaryClassificationText,
  type MetadataField
} from './summary'
import type { ParameterDisplayValues } from '../library/summary'

const rowAsset = assetRecord

export const rowParameters = (
  row: WorkspaceRecord
): AssetParametersPatch | ParameterDisplayValues =>
  hasSummary(row) ? summaryParameters(row) : (rowAsset(row)?.parameters ?? {})
export const rowClassification = (
  row: WorkspaceRecord
): AssetClassification | ReturnType<typeof summaryClassification> =>
  hasSummary(row)
    ? summaryClassification(row)
    : (rowAsset(row)?.classification ?? {})
export function datasetBinValue(row: WorkspaceRecord) {
  if (!hasSummary(row))
    throw new ApiClientError('Dataset metadata summary is missing', 'contract')
  const { binning_x: x, binning_y: y } = summaryParameters(row)
  return x === 'mixed' || y === 'mixed'
    ? 'mixed'
    : binEditValue({ binning_x: x, binning_y: y })
}
export function datasetBinDisplay(row: WorkspaceRecord) {
  const value = datasetBinValue(row)
  return value === 'mixed'
    ? uiT('apfUi.mixed')
    : (binValue(rowParameters(row)) ?? '—')
}
export function datasetBinChoices(row: WorkspaceRecord) {
  const current = datasetBinValue(row)
  return [
    {
      value: '',
      get label() {
        return uiT('apfUi.not_specified')
      }
    },
    ...(current === 'mixed'
      ? [
          {
            value: 'mixed',
            get label() {
              return uiT('apfUi.mixed')
            },
            disabled: true
          }
        ]
      : []),
    ...Array.from({ length: 16 }, (_, i) => ({
      value: 'Bin' + (i + 1),
      label: 'Bin' + (i + 1)
    })),
    ...(current.startsWith('legacy:')
      ? [
          {
            value: current,
            label:
              current.replace(/^legacy:/, 'Bin').replace('x', '×') +
              uiT('apfUi.current_value')
          }
        ]
      : [])
  ]
}
export function datasetFieldValue(row: WorkspaceRecord, field: MetadataField) {
  if (!hasSummary(row))
    throw new ApiClientError('Dataset metadata summary is missing', 'contract')
  return summaryRaw(row, field)
}
export function datasetParameterRaw(
  row: WorkspaceRecord,
  key: 'iso' | 'gain' | 'offset'
) {
  return datasetFieldValue(row, key)
}
export function parameterModeValue(
  row: WorkspaceRecord
): ParameterModeFieldValue {
  if (isDatasetRecord(row)) {
    const mode = datasetParameterMode(row)
    return {
      parameter_mode: mode || 'standard',
      iso: datasetParameterRaw(row, 'iso'),
      gain: datasetParameterRaw(row, 'gain'),
      offset: datasetParameterRaw(row, 'offset')
    }
  }

  const parameters = rowParameters(row)
  return {
    parameter_mode: parameters.parameter_mode,
    iso: parameters.iso,
    gain: parameters.gain,
    offset: parameters.offset
  }
}
export type ParameterModeFieldValue = {
  parameter_mode: string | null | undefined
  iso: number | string | null | undefined
  gain: number | string | null | undefined
  offset: number | string | null | undefined
}
export function parameterModeDisplay(row: WorkspaceRecord) {
  return parameterSummary(parameterModeValue(row))
}

export function displayTemperature(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return String(value)
  const match = String(value).match(
    /^([+-]?)(\d+)(?:\.(\d*))?(?:e([+-]?\d+))?$/i
  )
  if (!match) return n.toFixed(2)
  const digits = (match[2] + (match[3] ?? '')).replace(/^0+(?=\d)/, '')
  const decimalPlaces = (match[3] ?? '').length - Number(match[4] ?? 0)
  const retained = digits.length - decimalPlaces + 2
  const cents =
    retained <= 0
      ? 0n
      : retained >= digits.length
        ? BigInt(digits) * 10n ** BigInt(retained - digits.length)
        : BigInt(digits.slice(0, retained))
  const sign = match[1] === '-' && cents > 0n ? '-' : ''
  return (
    sign +
    (cents / 100n).toString() +
    '.' +
    (cents % 100n).toString().padStart(2, '0')
  )
}
export function datasetTemperature(row: WorkspaceRecord) {
  return datasetFieldDisplay(
    row,
    'sensor_temperature_c',
    (value) => displayTemperature(value) + ' °C'
  )
}
export function captureValue(value: unknown) {
  return value === null || value === undefined || value === ''
    ? '—'
    : String(value)
}
export function datasetParameterMode(row: WorkspaceRecord) {
  const value = datasetFieldValue(row, 'parameter_mode')
  return value === 'standard' ? '' : String(value)
}
export function frameClassLabel(value: unknown) {
  return displayLabel(value)
}
export function frameTypeLabel(value: unknown) {
  return displayLabel(value)
}
export function datasetFieldDisplay(
  row: WorkspaceRecord,
  field: MetadataField,
  format: (value: unknown) => string = captureValue
) {
  if (!hasSummary(row))
    throw new ApiClientError('Dataset metadata summary is missing', 'contract')
  return summaryText(row, field, format)
}
export function datasetClassification(row: WorkspaceRecord) {
  return hasSummary(row) ? summaryClassificationText(row) : '—'
}
