<script setup lang="ts">
import AssetContentChange from '../assets/AssetContentChange.vue'

export type SettingsProjectMode = 'projects' | 'asset-references' | 'dataset-references'
export interface SettingsRecordDetails {
  recordId: string
  title: string
  subtitle: string
  content?: { assetId: string; hasOriginal: boolean }
}
defineProps<{ workspaceId:string; projectMode?: SettingsProjectMode; choosing: boolean; referenceBusy?: boolean; details?: SettingsRecordDetails }>()
const emit = defineEmits<{
  'reference-action': [recordId: string, mode: 'asset-references' | 'dataset-references', choosing: boolean]
}>()
</script>
<template>
  <p v-if="projectMode && projectMode !== 'projects'" class="apf-project-intro">{{projectMode==='asset-references'?$t('apfUi.single_image'):$t('apfUi.image_group')}} · {{choosing?$t('apfUi.select_from_library'):$t('apfUi.project_references')}}</p>
  <slot name="records" />
  <slot name="editor" />
  <aside v-if="details" class="apf-details" :aria-label="$t('apfUi.record_details')">
    <h2>{{details.title}}</h2>
    <AssetContentChange v-if="details.content" :workspace-id="workspaceId" :asset-id="details.content.assetId" :has-original="details.content.hasOriginal" />
    <p>{{details.subtitle}}</p>
    <slot name="project-details" />
    <button v-if="projectMode&&projectMode!=='projects'" type="button" :disabled="referenceBusy" @click="emit('reference-action',details.recordId,projectMode,choosing)">{{projectMode==='asset-references'?(choosing?$t('apfUi.use_this_asset'):$t('apfUi.remove_from_project')):(choosing?$t('apfUi.use_this_dataset'):$t('apfUi.remove_image_group_from_project'))}}</button>
    <slot name="asset-details" />
    <slot name="dataset-details" />
  </aside>
</template>
