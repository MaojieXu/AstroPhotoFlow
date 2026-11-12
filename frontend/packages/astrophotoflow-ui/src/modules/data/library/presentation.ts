import { uiT } from '../../../core/i18n'
const labels: Record<string, string> = {
  get UnCalibrated() { return uiT('apfUi.uncalibrated') },
  get Calibrated() { return uiT('apfUi.calibrated') },
  get Unknown() { return uiT('apfUi.unknown') },
  get subframe() { return uiT('apfUi.subframe') }, get masterframe() { return uiT('apfUi.master_frame') }, get video() { return uiT('apfUi.video') },
  get light() { return uiT('apfUi.light') }, get bias() { return uiT('apfUi.bias') }, get dark() { return uiT('apfUi.dark') }, get flat() { return uiT('apfUi.flat') }, get dark_flat() { return uiT('apfUi.dark_flat') },
  get intermediate() { return uiT('apfUi.intermediate_result') }, get final() { return uiT('apfUi.final_result') }, get unknown() { return uiT('apfUi.unknown') }, get changed() { return uiT('apfUi.content_changed') }, get raw() { return uiT('apfUi.raw_asset') }, get calibration() { return uiT('apfUi.calibration_asset') }, get result() { return uiT('apfUi.result_asset') },
  get standard() { return uiT('apfUi.general') }, iso: 'ISO', gain: 'Gain／Offset',
  get managed() { return uiT('apfUi.managed_copy') }, get reference() { return uiT('apfUi.reference_only') }, get active() { return uiT('apfUi.active') }, get archived() { return uiT('apfUi.archived') },
  get available() { return uiT('apfUi.original_readable') }, get missing() { return uiT('apfUi.original_inaccessible') }, get unavailable() { return uiT('apfUi.unavailable') },
  get mono() { return uiT('apfUi.monochrome') }, get color() { return uiT('apfUi.color') }, get mixed() { return uiT('apfUi.mixed') }, get partial() { return uiT('apfUi.partially_missing') },
  get file() { return uiT('apfUi.file') }, get manual() { return uiT('apfUi.manual') }, get equipment() { return uiT('apfUi.equipment') }
}

export function displayLabel(value: unknown) {
  return value == null || value === '' ? uiT('apfUi.not_specified') : labels[String(value)] ?? String(value)
}

export function parameterSummary(value: { parameter_mode?: unknown; iso?: unknown; gain?: unknown; offset?: unknown }) {
  const number = (input: unknown) => input == null || input === '' ? uiT('apfUi.not_specified') : displayLabel(input)
  if (value.parameter_mode === 'mixed') return uiT('apfUi.mixed')
  if (value.parameter_mode === 'iso') return 'ISO · ' + number(value.iso)
  if (value.parameter_mode === 'gain') return 'Gain · ' + number(value.gain) + ' / Offset · ' + number(value.offset)
  const recorded = (['iso', 'gain', 'offset'] as const)
    .filter(key => value[key] != null && value[key] !== '')
    .map(key => `${key === 'iso' ? 'ISO' : key === 'gain' ? 'Gain' : 'Offset'} ${number(value[key])}`)
  return recorded.length ? uiT('apfUi.mode_not_specified') + recorded.join(' / ') : uiT('apfUi.not_specified')
}
