<script setup lang="ts">
import FixedDatasetMembers from './FixedDatasetMembers.vue'
export interface DatasetReferenceRow {
  recordId: string
  title: string
  projectFixed: boolean
  thumbnail?: string
  classification: string
  count: number | string
  camera: string
  parameters: string
  exposure: string
  temperature: string
  opticalSystem: string
  filter: string
  storage: string
  status: string
  notes: string
  datasetId: string
  memberCount: number
}
defineProps<{ workspaceId: string; rows: readonly DatasetReferenceRow[]; selectedId?: string }>()
const emit = defineEmits<{ select: [recordId: string]; preview: [recordId: string] }>()
</script>
<template>
  <div class="apf-table-scroll">
    <table class="apf-assets-table apf-dataset-table">
      <thead><tr><th>{{ $t('apfUi.cover') }}</th><th>{{ $t('apfUi.image_group') }}</th><th>{{ $t('apfUi.classification') }}</th><th>{{ $t('apfUi.member_count') }}</th><th>{{ $t('apfUi.camera_dacf07') }}</th><th>ISO／Gain</th><th>{{ $t('apfUi.exposure_bc7dac') }}</th><th>{{ $t('apfUi.temperature') }}</th><th>{{ $t('apfUi.imaging_system') }}</th><th>{{ $t('apfUi.filter') }}</th><th>{{ $t('apfUi.storage') }}</th><th>{{ $t('apfUi.status') }}</th><th>{{ $t('apfUi.notes') }}</th><th>{{ $t('apfUi.dataset_members') }}</th></tr></thead>
      <tbody><tr v-for="row in rows" :key="row.recordId" :aria-selected="selectedId===row.recordId" @click="emit('select',row.recordId)">
        <td><button type="button" class="apf-thumb" :aria-label="$t('apfUi.view')+row.title+$t('apfUi.full_size')" @click.stop="emit('preview',row.recordId)"><img v-if="row.thumbnail" :src="row.thumbnail" alt="" /><span v-else>{{ $t('apfUi.no_preview_yet') }}</span></button></td>
        <td><strong>{{row.title}}</strong><small>{{row.projectFixed?$t('apfUi.project_references'):$t('apfUi.image_group')}}</small></td>
        <td>{{row.classification}}</td><td>{{row.count}}</td><td>{{row.camera}}</td><td>{{row.parameters}}</td><td>{{row.exposure}}</td><td>{{row.temperature}}</td>
        <td>{{row.opticalSystem}}</td><td>{{row.filter}}</td><td>{{row.storage}}</td><td>{{row.status}}</td><td class="apf-note-cell">{{row.notes}}</td>
        <td><FixedDatasetMembers :workspace-id="workspaceId" :dataset-id="row.datasetId" :count="row.memberCount" /></td>
      </tr></tbody>
    </table>
  </div>
</template>
