<script setup lang="ts">
import type { DatasetOut } from '../../../generated/api/types.gen'
import InlineField from '../components/InlineField.vue'
import { displayLabel } from '../library/presentation'
type SaveField = InstanceType<typeof InlineField>['$props']['save']
defineProps<{ dataset: DatasetOut; recordId: string; saveName: SaveField; saveStatus: SaveField; saveNotes: SaveField }>()
const emit = defineEmits<{ 'cancel-field': [field: 'name' | 'status' | 'notes', recordId: string] }>()
</script>
<template>
  <div class="apf-detail-fields">
    <label>{{ $t('apfUi.image_group_name') }}<InlineField :value="dataset.name" :save="saveName" @cancelled="emit('cancel-field','name',recordId)" /></label>
    <label>{{ $t('apfUi.status') }}<InlineField :value="dataset.status" :display="displayLabel(dataset.status)" kind="select" :choices="[{value:'active',label:$t('apfUi.active')},{value:'archived',label:$t('apfUi.archive')}]" :save="saveStatus" @cancelled="emit('cancel-field','status',recordId)" /></label>
    <label>{{ $t('apfUi.notes') }}<InlineField :value="dataset.notes" kind="textarea" :save="saveNotes" @cancelled="emit('cancel-field','notes',recordId)" /></label>
  </div>
</template>
