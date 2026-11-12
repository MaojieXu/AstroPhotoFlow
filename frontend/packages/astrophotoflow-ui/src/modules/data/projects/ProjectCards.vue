<script setup lang="ts">
import type { ProjectOut } from '../../../generated/api/types.gen'
import LibraryCheckbox from '../components/LibraryCheckbox.vue'
defineProps<{
  projects: readonly ProjectOut[]
  selectedId?: string
  selectedIds: ReadonlySet<string>
  selectMode: boolean
  allSelected: boolean
  partiallySelected: boolean
  layout: 'grid' | 'list'
}>()
const emit = defineEmits<{ select: [id: string]; 'toggle-row': [id: string]; 'toggle-page': [selected: boolean] }>()
</script>
<template>
  <section :class="['apf-records',layout]">
    <label v-if="selectMode" class="apf-management-select-page"><LibraryCheckbox :label="$t('apfUi.select_current_page')" :model-value="allSelected" :indeterminate="partiallySelected" @update:model-value="emit('toggle-page',$event)" />{{ $t('apfUi.select_current_page') }}</label>
    <template v-for="project in projects" :key="project.id">
      <label v-if="selectMode" class="apf-management-record-select" @click.stop>
        <input type="checkbox" :aria-label="$t('apfUi.select_beb481')+project.name" :checked="selectedIds.has(project.id)" @change="emit('toggle-row',project.id)" />
        <span class="apf-record-icon">▣</span><span><strong>{{project.name}}</strong><small>{{project.target_name||''}}</small></span>
      </label>
      <button v-else type="button" :class="['apf-record',selectedId===project.id?'selected':'']" @click="emit('select',project.id)">
        <span class="apf-record-icon">▣</span><span><strong>{{project.name}}</strong><small>{{project.target_name||''}}</small></span>
      </button>
    </template>
  </section>
</template>
