<script setup lang="ts">
import LibraryFilterPanel from './LibraryFilterPanel.vue'
import AssetContentChange from '../assets/AssetContentChange.vue'

defineProps<{
  workspace: string
  filters: Record<string, string[] | string>
  filterOpen: boolean
  filterAnchor?: HTMLElement
  selectedAsset?: { id: string; title: string; hasOriginal: boolean }
}>()
const emit = defineEmits<{
  'apply-filters': [filters: Record<string, string[] | string>]
  'close-filters': []
}>()
</script>

<template>
  <LibraryFilterPanel v-if="filterOpen" :filters="filters" :workspace="workspace" :anchor="filterAnchor" @apply="emit('apply-filters', $event)" @cancel="emit('close-filters')" />
  <slot name="records" />
  <aside v-if="selectedAsset" class="apf-details" :aria-label="$t('apfUi.selected_asset_files')">
    <h2>{{ selectedAsset.title }}</h2>
    <AssetContentChange :workspace-id="workspace" :asset-id="selectedAsset.id" :has-original="selectedAsset.hasOriginal" />
  </aside>
</template>
