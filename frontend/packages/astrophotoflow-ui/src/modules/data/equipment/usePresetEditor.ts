import { computed, ref, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { uiT } from '../../../core/i18n'
import { filterChoiceLabel } from './filterLabels'
import type { CapturePreset, Equipment, EquipmentSetup } from '../api/contracts'

/** Presets only select a filter and capture parameters; hardware belongs to the setup. */
export function usePresetEditor(
  setup: MaybeRefOrGetter<EquipmentSetup | undefined>,
  equipment: MaybeRefOrGetter<readonly Equipment[]>
) {
  const selectedSetup = computed(() => toValue(setup))
  const relatedEquipment = computed(() => toValue(equipment))
  const editingPreset = ref<CapturePreset | null>()
  type Selection = NonNullable<CapturePreset['equipment_selection']>
  type Parameters = NonNullable<CapturePreset['parameters']>
  const presetDraft = ref({ equipment_selection: {} as Selection, parameters: {} as Parameters })
  const presetOriginal = ref('')
  const numericParameters = [
    { key: 'exposure_seconds', get label() { return uiT('apfUi.exposure_seconds') }, min: 0 },
    { key: 'sensor_temperature_c', get label() { return uiT('apfUi.temperature_c') } },
    { key: 'iso', label: 'ISO', integer: true, min: 1 },
    { key: 'gain', get label() { return uiT('apfUi.gain_3b0865') } },
    { key: 'offset', label: 'Offset' }
  ] as const
  const visibleNumericParameters = computed(() => numericParameters.filter(field => field.key === 'iso'
    ? presetDraft.value.parameters.parameter_mode === 'iso'
    : field.key === 'gain' || field.key === 'offset' ? presetDraft.value.parameters.parameter_mode === 'gain' : true))
  const ownedFilters = computed(() => (selectedSetup.value?.components ?? []).flatMap(component => {
      const equipment = component.source === 'inline' ? component.equipment : relatedEquipment.value.find(row => row.id === component.equipment_id)
      return equipment?.kind === 'filter' && component.id ? [{ value: component.id, name: filterChoiceLabel(equipment) }] : []
    }))
  const filterOptions = computed(() => [
    { value: '', name: uiT('apfUi.use_setup_default_filter', { p0: ownedFilters.value[0]?.name ?? uiT('apfUi.no_setup_filter') }) },
    { value: 'none', name: uiT('apfUi.do_not_use') },
    ...ownedFilters.value
  ])
  const filterValue = computed(() => 'filter' in presetDraft.value.equipment_selection
    ? presetDraft.value.equipment_selection.filter ?? 'none' : '')
  function setFilter(value: string | number | null | undefined) {
    if (!value) delete presetDraft.value.equipment_selection.filter
    else presetDraft.value.equipment_selection.filter = value === 'none' ? null : String(value)
  }
  const presetName = computed(() => editingPreset.value?.name ?? uiT('apfUi.preset_name_generated_on_save'))
  const dirty = computed(() => editingPreset.value !== undefined && JSON.stringify(presetDraft.value) !== presetOriginal.value)
  function reset() { editingPreset.value = undefined }
  function beginPreset(row: CapturePreset | null) {
    editingPreset.value = row
    const selection: Selection = {}
    if (row && row.equipment_selection && 'filter' in row.equipment_selection) selection.filter = row.equipment_selection.filter
    const parameters: Parameters = {}
    for (const key of ['parameter_mode','exposure_seconds','sensor_temperature_c','iso','gain','offset'] as const) {
      if (row?.parameters && key in row.parameters) Object.assign(parameters, { [key]: row.parameters[key] })
    }
    presetDraft.value = { equipment_selection: selection, parameters }
    presetOriginal.value = JSON.stringify(presetDraft.value)
  }
  function setParameter(key: 'parameter_mode' | typeof numericParameters[number]['key'], value: string) {
    if (key === 'parameter_mode') presetDraft.value.parameters.parameter_mode = value === '' ? null : value as Parameters['parameter_mode']
    else presetDraft.value.parameters[key] = value === '' ? null : Number(value)
  }
  return { editingPreset, presetDraft, dirty, reset, beginPreset, filterOptions, filterValue, setFilter, presetName, visibleNumericParameters, setParameter }
}
