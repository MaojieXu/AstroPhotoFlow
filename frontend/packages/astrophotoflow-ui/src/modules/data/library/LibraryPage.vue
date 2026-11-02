<script setup lang="ts">
import type { DatasetOut } from '../../../generated/api/types.gen'
import LibraryFilterPanel from './LibraryFilterPanel.vue'
import CalibrationLibrary from './CalibrationLibrary.vue'
import CalibrationBindingsEditor from '../datasets/CalibrationBindingsEditor.vue'
import AssetContentChange from '../assets/AssetContentChange.vue'

defineProps<{
  workspace: string
  recordsLoading: boolean
  filters: Record<string, string[] | string>
  filterOpen: boolean
  filterAnchor?: HTMLElement
  calibrationLibrary: boolean
  datasetId?: string
  selectedAsset?: { id: string; title: string; hasVersion: boolean }
}>()
const emit = defineEmits<{
  'apply-filters': [filters: Record<string, string[] | string>]
  'close-filters': []
  'asset-accepted': []
  'calibration-updated': [dataset: DatasetOut]
  'calibration-dirty': [value: boolean]
  'calibration-created': [dataset: DatasetOut]
}>()
</script>

<template>
  <LibraryFilterPanel v-if="filterOpen" :filters="filters" :workspace="workspace" :anchor="filterAnchor" @apply="emit('apply-filters', $event)" @cancel="emit('close-filters')" />
  <CalibrationLibrary v-if="calibrationLibrary" :workspace="workspace" :records-loading="recordsLoading" @dirty="emit('calibration-dirty', $event)" @created="emit('calibration-created', $event)"><template #records><slot name="records" /></template></CalibrationLibrary>
  <slot v-else name="records" />
  <aside v-if="selectedAsset" class="apf-details" :aria-label="$t('apfUi.selected_asset_files')">
    <h2>{{ selectedAsset.title }}</h2>
    <AssetContentChange :workspace-id="workspace" :asset-id="selectedAsset.id" :has-version="selectedAsset.hasVersion" @accepted="emit('asset-accepted')" />
  </aside>
  <CalibrationBindingsEditor v-if="datasetId" :key="workspace+':'+datasetId" :workspace-id="workspace" :dataset-id="datasetId" @updated="emit('calibration-updated', $event)" @dirty="emit('calibration-dirty', $event)" />
</template>
