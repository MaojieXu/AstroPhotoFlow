<script setup lang="ts">
import type { WorkspacePageSize } from './store'
const props = defineProps<{
  total: number
  offset: number
  pageSize: WorkspacePageSize
  pageLength: number
  library: boolean
  equipmentManagement: boolean
  loading: boolean
  error: boolean
  blocked: boolean
}>()
const emit = defineEmits<{ move: [delta: number]; 'page-size': [size: WorkspacePageSize] }>()
function changeSize(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  emit('page-size', value === 'all' ? 'all' : Number(value) as 10 | 20 | 50)
}
function move(direction: -1 | 1) {
  if (props.pageSize !== 'all') emit('move', direction * props.pageSize)
}
</script>
<template>
  <footer v-if="!equipmentManagement||(!loading&&!error&&total>50)" class="apf-pagination">
    <span>{{ $t('apfUi.records_value', { p0: total }) }}</span>
    <label v-if="!equipmentManagement&&!library">{{ $t('apfUi.show_per_page') }}<select :aria-label="$t('apfUi.number_of_items_per_page')" :value="pageSize" :disabled="loading||blocked" @change="changeSize">
      <option value="10">10</option><option value="20">20</option><option value="50">50</option><option value="all">{{ $t('apfUi.all') }}</option>
    </select></label>
    <template v-if="pageSize!=='all'&&(!library||total>pageSize)">
      <button type="button" :disabled="offset===0||loading||blocked" @click="move(-1)">{{ $t('apfUi.previous_page') }}</button>
      <button type="button" :disabled="offset+pageLength>=total||loading||blocked" @click="move(1)">{{ $t('apfUi.next_page') }}</button>
    </template>
  </footer>
</template>
