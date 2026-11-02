<script setup lang="ts">
import AssetContentChange from '../assets/AssetContentChange.vue'
import LibraryInfo from '../components/LibraryInfo.vue'

export type SettingsProjectMode = 'projects' | 'asset-references' | 'dataset-references'
export interface SettingsRecordDetails {
  recordId: string
  title: string
  subtitle: string
  content?: { assetId: string; hasVersion: boolean }
  version?: { number: string | number; id: string }
}
defineProps<{ workspaceId:string; projectMode?: SettingsProjectMode; choosing: boolean; referenceBusy?: boolean; details?: SettingsRecordDetails }>()
const emit = defineEmits<{
  'content-accepted': [recordId: string]
  'reference-action': [recordId: string, mode: 'asset-references' | 'dataset-references', choosing: boolean]
}>()
</script>
<template>
  <section v-if="projectMode" class="apf-project-intro" :aria-label="$t('apfUi.project_asset_description')">
    <h2>{{ $t('apfUi.project') }}<LibraryInfo :label="$t('apfUi.project')" :text="$t('apfUi.projects_collect_single_images_and_image_groups_across_nights_and_filt')" /></h2>
    <p v-if="projectMode!=='projects'">{{projectMode==='asset-references'?$t('apfUi.single_image'):$t('apfUi.image_group')}} · {{choosing?$t('apfUi.select_fixed_versions_from_the_library'):$t('apfUi.selected_fixed_versions')}}</p>
  </section>
  <slot name="records" />
  <slot name="editor" />
  <aside v-if="details" class="apf-details" :aria-label="$t('apfUi.record_details')">
    <h2>{{details.title}}</h2>
    <AssetContentChange v-if="details.content" :workspace-id="workspaceId" :asset-id="details.content.assetId" :has-version="details.content.hasVersion" @accepted="emit('content-accepted',details.recordId)" />
    <p>{{details.subtitle}}</p>
    <slot name="project-details" />
    <button v-if="projectMode&&projectMode!=='projects'" type="button" :disabled="referenceBusy" @click="emit('reference-action',details.recordId,projectMode,choosing)">{{projectMode==='asset-references'?(choosing?$t('apfUi.use_this_asset_version'):$t('apfUi.remove_from_project')):(choosing?$t('apfUi.use_this_image_group_version'):$t('apfUi.remove_image_group_from_project'))}}</button>
    <p v-if="details.version">{{choosing?$t('apfUi.version_to_use'):$t('apfUi.fixed_version')}} v{{details.version.number}}<LibraryInfo :label="$t('apfUi.fixed_version')" :text="details.version.id" /></p>
    <slot name="asset-details" />
    <slot name="dataset-details" />
  </aside>
</template>
