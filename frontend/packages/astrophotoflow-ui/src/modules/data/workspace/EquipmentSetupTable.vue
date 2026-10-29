<script setup lang="ts">
import { computed, inject } from 'vue'
import type { EquipmentSetup } from '../api/contracts'
import type { WorkspaceContext } from './Workspace.vue'
import LibraryButton from './LibraryButton.vue'
import LibraryCheckbox from './LibraryCheckbox.vue'

const {
  rows, selected, loading, relatedEquipment, relatedEquipmentReady, relatedEquipmentLoading, relatedEquipmentError,
  loadRelatedEquipment, setupSort, toggleSetupSort, managementFilterBlocked,
  managementSelectMode, managementSelection, managementPageAllSelected,
  managementPagePartiallySelected, toggleManagementSelection, toggleManagementPage, selectRow
} = inject<WorkspaceContext>('workspace')!
const equipmentColumns = [
  { key: 'camera', label: '相机' },
  { key: 'telescope', label: '望远镜' },
  { key: 'mount', label: '赤道仪' },
  { key: 'filter', label: '滤镜' },
  { key: 'accessory', label: '光学附件' }
] as const
const columns = [{ key: 'name', label: '名称' }, ...equipmentColumns] as const
type EquipmentColumn = typeof equipmentColumns[number]['key']
const equipmentById = computed(() => new Map(relatedEquipment.value.map(item => [item.id, item])))
const tableRows = computed(() => (rows.value as EquipmentSetup[]).map(setup => {
  const names: Record<EquipmentColumn, string[]> = { camera: [], telescope: [], mount: [], filter: [], accessory: [] }
  for (const component of setup.components) {
    const equipment = component.source === 'inline' ? component.equipment : equipmentById.value.get(component.equipment_id)
    if (!equipment) continue
    const kind = equipment.kind === 'optical_system' ? 'telescope' : equipment.kind
    names[kind].push(equipment.name + (equipment.kind === 'optical_system' ? '（既有成像系统）' : ''))
  }
  return { setup, names }
}))
const unresolvedEquipment = computed(() => (!relatedEquipmentReady.value || relatedEquipmentLoading.value) && tableRows.value.some(row =>
  row.setup.components.some(component => component.source === 'registered')))
</script>

<template>
  <p v-if="unresolvedEquipment&&relatedEquipmentError" class="apf-error" role="alert">
    设备资料读取失败：{{relatedEquipmentError}}
    <LibraryButton type="button" @click="loadRelatedEquipment(true)">重试</LibraryButton>
  </p>
  <div class="apf-table-scroll apf-setup-table-scroll">
    <table class="apf-assets-table apf-setup-table" aria-label="设备组合列表">
      <thead>
        <tr>
          <th v-if="managementSelectMode" class="apf-setup-select-cell"><LibraryCheckbox label="全选当前页" :model-value="managementPageAllSelected" :indeterminate="managementPagePartiallySelected" :disabled="!tableRows.length||managementFilterBlocked||loading" @update:model-value="toggleManagementPage" /></th>
          <th v-for="column in columns" :key="column.key" :class="{'apf-setup-name-cell':column.key==='name'}" :aria-sort="setupSort.by===column.key?(setupSort.order==='asc'?'ascending':'descending'):undefined">
            <LibraryButton type="button" variant="textonly" class="apf-sort-button" :disabled="managementFilterBlocked||loading" @click="toggleSetupSort(column.key)">{{column.label}}<span v-if="setupSort.by===column.key" aria-hidden="true">{{setupSort.order==='asc'?' ▲':' ▼'}}</span></LibraryButton>
          </th>
        </tr>
      </thead>
      <tbody v-if="!loading">
        <tr v-for="row in tableRows" :key="row.setup.id" :aria-selected="managementSelectMode?managementSelection.has('equipment-setups:'+row.setup.id):selected?.id===row.setup.id" @click="!managementSelectMode&&selectRow(row.setup)">
          <td v-if="managementSelectMode" class="apf-setup-select-cell"><LibraryCheckbox :label="'选择 '+row.setup.name" :model-value="managementSelection.has('equipment-setups:'+row.setup.id)" :disabled="managementFilterBlocked" @click.stop @update:model-value="toggleManagementSelection(row.setup)" /></td>
          <td><LibraryButton type="button" variant="textonly" class="apf-setup-name" :aria-label="'查看组合 '+row.setup.name" :tooltip="row.setup.name" :disabled="managementSelectMode" @click.stop="selectRow(row.setup)">{{row.setup.name}}</LibraryButton></td>
          <td v-for="column in equipmentColumns" :key="column.key">
            <span v-if="unresolvedEquipment">{{relatedEquipmentError?'未读取':'读取中…'}}</span>
            <span v-else-if="row.names[column.key].length" class="apf-setup-equipment-cell" :title="row.names[column.key].join('\n')">
              <span>{{row.names[column.key][0]}}{{row.names[column.key].length>1?' 等 '+row.names[column.key].length+' 件':''}}</span>
            </span>
            <span v-else>—</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
