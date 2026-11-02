import { computed, ref, toValue } from 'vue'
import { uiT } from '../../../core/i18n'
import { filterChoiceLabel } from './filterLabels'
import type { TelescopeSpecs } from '../../../generated/api/types.gen'
import type { MaybeRefOrGetter } from 'vue'
import type { Equipment, EquipmentSetup } from '../api/contracts'
import type {
  EquipmentDraft,
  SetupComponentDraft as SetupComponent
} from './drafts'

/** Local setup/device drafts; creating a registered device is a separate write. */
export function useSetupEditor(
  equipment: MaybeRefOrGetter<readonly Equipment[]>
) {
  const relatedEquipment = computed(() => toValue(equipment))
  const editingSetup = ref<EquipmentSetup | null>()
  const setupDraft = ref({
    name: '',
    notes: '',
    status: 'active' as 'active' | 'archived',
    components: [] as SetupComponent[]
  })
  const original = ref('')
  const deviceEditor = ref<
    | { source: 'new'; equipment: EquipmentDraft }
    | { source: 'inline'; index: number; equipment: EquipmentDraft }
  >()
  const equipmentOriginal = ref('')

  const dirty = computed(
    () =>
      (editingSetup.value !== undefined &&
        JSON.stringify(setupDraft.value) !== original.value) ||
      (deviceEditor.value !== undefined &&
        JSON.stringify(deviceEditor.value.equipment) !==
          equipmentOriginal.value)
  )
  function beginSetup(row: EquipmentSetup | null) {
    editingSetup.value = row
    setupDraft.value = {
      name: row?.name ?? '',
      notes: row?.notes ?? '',
      status: row?.status ?? 'active',
      components: (row?.components ?? []).map(({ effective_focal_length_mm: _effective, ...component }) => JSON.parse(JSON.stringify(component)))
    }
    original.value = JSON.stringify(setupDraft.value)
  }
  function reset() {
    editingSetup.value = undefined
    deviceEditor.value = undefined
  }
  function registeredIds(kind: string) {
    return setupDraft.value.components.flatMap((component) =>
      component.source === 'registered' && componentKind(component) === kind
        ? [component.equipment_id]
        : []
    )
  }
  function setRegistered(kind: string, ids: string[]) {
    if (kind !== 'filter') {
      if (ids.length > 1) return
      setSingle(kind, ids[0] ?? '')
      return
    }
    const retained = setupDraft.value.components.filter(
      (component) =>
        component.source !== 'registered' ||
        componentKind(component) !== kind ||
        ids.includes(component.equipment_id)
    )
    const present = new Set(
      retained.flatMap((component) =>
        component.source === 'registered' ? [component.equipment_id] : []
      )
    )
    setupDraft.value.components = [
      ...retained,
      ...ids
        .filter((id) => !present.has(id))
        .map((equipment_id) => ({
          source: 'registered' as const,
          equipment_id
        }))
    ]
  }
  function singleValue(kind: string) {
    const candidates = setupDraft.value.components.flatMap((component, index) => componentKind(component) === kind
      ? [component.source === 'registered' ? component.equipment_id : `inline:${index}`] : [])
    return candidates.length === 1 ? candidates[0] : ''
  }
  function singleOptions(kind: string) {
    return [{ value: '', name: uiT('apfUi.do_not_use') },
      ...setupDraft.value.components.flatMap((component, index) => component.source === 'inline' && componentKind(component) === kind
        ? [{ value: `inline:${index}`, name: component.equipment.name }] : []), ...equipmentOptions(kind)]
  }
  function setSingle(kind: string, value: string | number | null | undefined) {
    const selected = value == null ? '' : String(value)
    const existing = setupDraft.value.components.find((component, index) => componentKind(component) === kind &&
      (component.source === 'registered' ? component.equipment_id === selected : `inline:${index}` === selected))
    const replacement: SetupComponent | undefined = existing ?? (selected && !selected.startsWith('inline:')
      ? { source: 'registered', equipment_id: selected, optical_accessory_id: null } : undefined)
    const first = setupDraft.value.components.findIndex(component => componentKind(component) === kind)
    const retained = setupDraft.value.components.filter(component => componentKind(component) !== kind)
    if (replacement) retained.splice(first < 0 ? retained.length : Math.min(first, retained.length), 0, replacement)
    setupDraft.value.components = retained
  }
  function addRegistered(kind: EquipmentDraft['kind'], equipmentId: string) {
    if (kind === 'filter') setupDraft.value.components.push({source: 'registered', equipment_id: equipmentId})
    else setSingle(kind, equipmentId)
  }
  function count(kind: string) {
    return setupDraft.value.components.filter(component => componentKind(component) === kind).length
  }
  const invalidCounts = computed(() => count('camera') > 1 || count('telescope') > 1)
  function applyInline(index: number, equipment: EquipmentDraft) {
    if (equipment.kind !== 'filter' && setupDraft.value.components.some((component, position) => position !== index && componentKind(component) === equipment.kind)) return false
    const current = setupDraft.value.components[index]
    setupDraft.value.components[index] = {...current, source: 'inline', equipment: JSON.parse(JSON.stringify(equipment)),
      optical_accessory_id: equipment.kind === 'telescope' && componentKind(current) === 'telescope' ? current.optical_accessory_id : null}
    return true
  }
  function equipmentOptions(kind: string) {
    return relatedEquipment.value
      .filter((item) => item.kind === kind && item.status === 'active')
      .map((item) => ({ value: item.id as string, name: item.kind === 'filter' ? filterChoiceLabel(item) : item.name }))
  }
  function componentKind(component: SetupComponent) {
    return component.source === 'inline'
      ? component.equipment.kind
      : relatedEquipment.value.find((row) => row.id === component.equipment_id)
          ?.kind
  }
  function componentEquipment(component: SetupComponent) {
    return component.source === 'inline' ? component.equipment : relatedEquipment.value.find(row => row.id === component.equipment_id)
  }
  function accessoryOptions(component: SetupComponent) {
    const equipment = componentEquipment(component)
    const accessories = equipment?.kind === 'telescope' ? equipment.specs.optical_accessories : undefined
    return [{ value: '', name: uiT('apfUi.native_focal_no_accessory') },
      ...(Array.isArray(accessories) ? accessories as NonNullable<TelescopeSpecs['optical_accessories']> : []).map(item => ({ value: item.id!, name: `${item.name} ×${item.factor}` }))]
  }
  function setAccessory(index: number, value: string | number | null | undefined) {
    setupDraft.value.components[index] = { ...setupDraft.value.components[index], optical_accessory_id: value ? String(value) : null }
  }
  function beginEquipment(kind: EquipmentDraft['kind']) {
    deviceEditor.value = {
      source: 'new',
      equipment: {
        kind,
        name: '',
        model: null,
        notes: null,
        specs: {}
      }
    }
    equipmentOriginal.value = JSON.stringify(deviceEditor.value.equipment)
  }
  function editInline(index: number) {
    const component = setupDraft.value.components[index]
    if (component.source !== 'inline') return
    deviceEditor.value = {
      source: 'inline',
      index,
      equipment: JSON.parse(JSON.stringify(component.equipment))
    }
    equipmentOriginal.value = JSON.stringify(deviceEditor.value.equipment)
  }

  return {
    editingSetup,
    setupDraft,
    deviceEditor,
    equipmentOriginal,
    dirty,
    beginSetup,
    reset,
    registeredIds,
    setRegistered,
    equipmentOptions,
    singleValue, singleOptions, setSingle, addRegistered, count, invalidCounts, applyInline,
    componentKind,
    componentEquipment,
    accessoryOptions,
    setAccessory,
    beginEquipment,
    editInline
  }
}
