<script setup lang="ts">
import { uiT } from '../../../core/i18n'
import { filterLabel } from './filterLabels'

import { computed } from 'vue'
import type { Equipment, EquipmentSetup } from '../api/contracts'
import type { ListSetupsApiV1EquipmentSetupsGetData } from '../../../generated/api/types.gen'
import LibraryButton from '../components/LibraryButton.vue'
import LibraryCheckbox from '../components/LibraryCheckbox.vue'

type SetupQuery = NonNullable<ListSetupsApiV1EquipmentSetupsGetData['query']>
const props = defineProps<{
  setups: readonly EquipmentSetup[]
  selectedId?: string
  loading: boolean
  equipment: readonly Equipment[]
  equipmentReady: boolean
  equipmentLoading: boolean
  equipmentError: string
  sort: { by: NonNullable<SetupQuery['sort_by']>; order: 'asc' | 'desc' }
  blocked: boolean
  selectMode: boolean
  selectedIds: ReadonlySet<string>
  allSelected: boolean
  partiallySelected: boolean
}>()
const emit = defineEmits<{
  sort: [field: 'name' | EquipmentColumn]
  select: [setupId: string]
  edit: [setupId: string]
  'toggle-row': [setupId: string]
  'toggle-page': [selected: boolean]
  'retry-equipment': []
}>()
const equipmentColumns = [
  { key: 'camera', get label() { return uiT('apfUi.camera_dacf07') } },
  { key: 'telescope', get label() { return uiT('apfUi.telescope') } },
  { key: 'mount', get label() { return uiT('apfUi.mount') } },
  { key: 'filter', get label() { return uiT('apfUi.filter') } }
] as const
const columns = [{ key: 'name', get label() { return uiT('apfUi.name') } }, ...equipmentColumns] as const
type EquipmentColumn = typeof equipmentColumns[number]['key']
const equipmentById = computed(() => new Map(props.equipment.map(item => [item.id, item])))
const tableRows = computed(() => props.setups.map(setup => {
  const names: Record<EquipmentColumn, string[]> = { camera: [], telescope: [], mount: [], filter: [] }
  const filterTags: { id: string; label: string; name: string }[] = []
  for (const component of setup.components) {
    const equipment = component.source === 'inline' ? component.equipment : equipmentById.value.get(component.equipment_id)
    if (!equipment) continue
    if (equipment.kind === 'filter') {
      const label = filterLabel(equipment)
      names.filter.push(label)
      filterTags.push({ id: component.id, label, name: equipment.name })
      continue
    }
    const accessory = equipment.kind === 'telescope' ? equipment.specs?.optical_accessories?.find(item => item.id === component.optical_accessory_id) : undefined
    names[equipment.kind].push([equipment.name, accessory ? `${accessory.name} ×${accessory.factor}` : '', component.effective_focal_length_mm == null ? '' : `${component.effective_focal_length_mm} mm`].filter(Boolean).join(' · '))
  }
  return { setup, names, filterTags }
}))
const unresolvedEquipment = computed(() => (!props.equipmentReady || props.equipmentLoading) && tableRows.value.some(row =>
  row.setup.components.some(component => component.source === 'registered')))
</script>

<template>
  <p v-if="unresolvedEquipment&&equipmentError" class="apf-error" role="alert">{{ $t('apfUi.could_not_read_equipment_metadata_value', { p0: (equipmentError) }) }}<LibraryButton type="button" @click="emit('retry-equipment')">{{ $t('apfUi.retry') }}</LibraryButton>
  </p>
  <div class="apf-table-scroll apf-setup-table-scroll">
    <table class="apf-assets-table apf-setup-table" :aria-label="$t('apfUi.equipment_setup_list')">
      <thead>
        <tr>
          <th v-if="selectMode" class="apf-setup-select-cell"><LibraryCheckbox :label="$t('apfUi.select_current_page')" :model-value="allSelected" :indeterminate="partiallySelected" :disabled="!tableRows.length||blocked||loading" @update:model-value="emit('toggle-page', $event)" /></th>
          <th v-for="column in columns" :key="column.key" :class="{'apf-setup-name-cell':column.key==='name'}" :aria-sort="sort.by===column.key?(sort.order==='asc'?'ascending':'descending'):undefined">
            <LibraryButton type="button" variant="textonly" class="apf-sort-button" :disabled="blocked||loading" @click="emit('sort', column.key)">{{column.label}}<span v-if="sort.by===column.key" aria-hidden="true">{{sort.order==='asc'?' ▲':' ▼'}}</span></LibraryButton>
          </th>
          <th v-if="!selectMode" scope="col" class="apf-setup-action-cell" :aria-label="$t('apfUi.setup_actions')"></th>
        </tr>
      </thead>
      <tbody v-if="!loading">
        <tr v-for="row in tableRows" :key="row.setup.id" :aria-selected="selectMode?selectedIds.has(row.setup.id):selectedId===row.setup.id" @click="!selectMode&&emit('select', row.setup.id)">
          <td v-if="selectMode" class="apf-setup-select-cell"><LibraryCheckbox :label="$t('apfUi.select_beb481')+row.setup.name" :model-value="selectedIds.has(row.setup.id)" :disabled="blocked" @click.stop @update:model-value="emit('toggle-row', row.setup.id)" /></td>
          <td><LibraryButton type="button" variant="textonly" class="apf-setup-name" :aria-label="$t('apfUi.view_setup')+row.setup.name" :tooltip="row.setup.name" :disabled="selectMode" @click.stop="emit('select', row.setup.id)">{{row.setup.name}}</LibraryButton></td>
          <td v-for="column in equipmentColumns" :key="column.key">
            <span v-if="unresolvedEquipment">{{equipmentError?$t('apfUi.not_read'):$t('apfUi.reading')}}</span>
            <span v-else-if="row.names[column.key].length&&column.key==='filter'" class="apf-setup-filter-list"><span v-for="filter in row.filterTags" :key="filter.id" class="apf-setup-filter-tag" :title="filter.name">{{filter.label}}</span></span>
            <span v-else-if="row.names[column.key].length" class="apf-setup-equipment-cell" :title="row.names[column.key].join('\n')">
              <span>{{row.names[column.key][0]}}{{row.names[column.key].length>1?$t('apfUi.and_others')+row.names[column.key].length+$t('apfUi.items'):''}}</span>
            </span>
            <span v-else>—</span>
          </td>
          <td v-if="!selectMode" class="apf-setup-action-cell">
            <LibraryButton
              v-if="selectedId === row.setup.id"
              class="apf-setup-edit"
              variant="textonly"
              :tooltip="$t('apfUi.edit_equipment_setup')"
              :disabled="blocked"
              @click.stop="emit('edit', row.setup.id)"
            >
              <i class="pi pi-pencil" aria-hidden="true" />
              <span class="sr-only">{{ $t('apfUi.edit_equipment_setup') }}</span>
            </LibraryButton>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
