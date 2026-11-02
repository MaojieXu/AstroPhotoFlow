<script setup lang="ts">
import type { Equipment } from '../api/contracts'
import { equipmentKindIcons, equipmentSubtitle } from './fields'
import LibraryCheckbox from '../components/LibraryCheckbox.vue'
import LibraryButton from '../components/LibraryButton.vue'
defineProps<{
  equipment: readonly Equipment[]
  selectedId?: string
  selectedIds: ReadonlySet<string>
  selectMode: boolean
  allSelected: boolean
  partiallySelected: boolean
  blocked: boolean
  loading: boolean
  layout: 'grid' | 'list'
}>()
const emit = defineEmits<{
  select: [id: string]
  edit: [id: string]
  'toggle-row': [id: string]
  'toggle-page': [selected: boolean]
}>()
</script>
<template>
  <section :class="['apf-records',layout]">
    <label v-if="selectMode" class="apf-management-select-page"><LibraryCheckbox :label="$t('apfUi.select_current_page')" :model-value="allSelected" :indeterminate="partiallySelected" :disabled="blocked" @update:model-value="emit('toggle-page',$event)" />{{ $t('apfUi.select_current_page') }}</label>
    <div v-for="item in equipment" :key="item.id" class="apf-equipment-record" role="group" :aria-label="$t('apfUi.equipment_0221ba')+item.name">
      <LibraryCheckbox v-if="selectMode" :label="$t('apfUi.select_beb481')+item.name" :model-value="selectedIds.has(item.id)" :disabled="blocked" @update:model-value="emit('toggle-row',item.id)" />
      <button type="button" :class="['apf-record',selectedId===item.id?'selected':'']" :aria-label="$t('apfUi.select_equipment')+item.name" :aria-pressed="selectedId===item.id" :disabled="selectMode||blocked" @click="emit('select',item.id)">
        <i :class="[equipmentKindIcons[item.kind],'size-4 shrink-0 text-muted-foreground']" aria-hidden="true" />
        <span class="apf-equipment-record-text"><strong>{{item.name}}</strong><small>{{equipmentSubtitle(item)}}</small></span>
      </button>
      <span class="apf-equipment-edit-slot"><LibraryButton v-if="selectedId===item.id" type="button" :aria-label="$t('apfUi.edit_equipment_86df54')+item.name" :disabled="blocked||loading" @click="emit('edit',item.id)">{{ $t('apfUi.edit') }}</LibraryButton></span>
    </div>
  </section>
</template>
