import type InlineField from '../components/InlineField.vue'
import type ParameterModeField from '../equipment/ParameterModeField.vue'
import type { CanvasDataRequest } from '../api/canvas'
import type { InlineCalibrationBinding } from './inlineCalibration'
export type InlineBinding = Pick<InstanceType<typeof InlineField>['$props'], 'value' | 'display' | 'title' | 'editValue' | 'kind' | 'choices' | 'choicesMessage' | 'save' | 'onCancelled'>
export type ParameterBinding = Pick<InstanceType<typeof ParameterModeField>['$props'], 'value' | 'display' | 'unsetMode' | 'save' | 'onCancelled'>
export interface LibraryTableRow {
  key: string
  title: string
  subtitle: string
  dataset: boolean
  video: boolean
  selected: boolean
  memberCount: number
  mixedUse: boolean
  source?: CanvasDataRequest
  thumbnail?: string
  thumbnailUrl?: () => string | undefined
  prioritizeThumbnail?: () => void
  readiness: string
  parametersDisplay: string
  parameterSource: string
  issue?: { label: string; availability: string; text: string }
  storage: string
  availability: string
  calibrationStatusLabel?: string
  calibrationStatus?: InlineBinding
  calibrationCounts?: string
  calibrationEvidence?: string
  calibration?: InlineCalibrationBinding[]
  exposureSummary?: string
  fields: {
    name: InlineBinding
    groupClass: InlineBinding
    groupType: InlineBinding
    assetClass: InlineBinding
    assetType: InlineBinding
    camera: InlineBinding
    parameters: ParameterBinding
    exposure: InlineBinding
    temperature: InlineBinding
    binning: InlineBinding
    cfa: InlineBinding
    opticalSystem: InlineBinding
    filter: InlineBinding
    integration: InlineBinding
    status: InlineBinding
    notes: InlineBinding
    opticalSystemReference: InlineBinding
    filterReference: InlineBinding
    statusReference: InlineBinding
    notesReference: InlineBinding
  }
}
