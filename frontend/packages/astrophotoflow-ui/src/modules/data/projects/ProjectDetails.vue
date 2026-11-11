<script setup lang="ts">
import type { ProjectOut } from '../../../generated/api/types.gen'
import InlineField from '../components/InlineField.vue'

export type ProjectDetailsAction = 'assets' | 'masters' | 'datasets' | 'add-asset' | 'add-master' | 'add-dataset' | 'import-dataset' | 'edit' | 'archive' | 'restore'
type SaveField = (value: string | number | null) => Promise<void>
defineProps<{
  project: ProjectOut
  blocked: boolean
  saveName: SaveField
  saveTarget: SaveField
  saveNotes: SaveField
}>()
const emit = defineEmits<{
  action: [action: ProjectDetailsAction, projectId: string]
  'cancel-field': [field: 'name' | 'target_name' | 'notes', projectId: string]
}>()
</script>

<template>
  <button type="button" @click="emit('action','masters',project.id)">{{ $t('apfUi.project_masterframes') }}</button>
  <button type="button" @click="emit('action','add-master',project.id)">{{ $t('apfUi.add_masterframe') }}</button>
  <button type="button" @click="emit('action','assets',project.id)">{{ $t('apfUi.view_project_assets') }}</button>
  <button type="button" @click="emit('action','datasets',project.id)">{{ $t('apfUi.project_subframe_datasets') }}</button>
  <button type="button" @click="emit('action','add-asset',project.id)">{{ $t('apfUi.add_single_image') }}</button>
  <button type="button" @click="emit('action','add-dataset',project.id)">{{ $t('apfUi.add_image_group') }}</button>
  <button type="button" @click="emit('action','import-dataset',project.id)">{{ $t('apfUi.import_subframe_dataset') }}</button>
  <button type="button" @click="emit('action','edit',project.id)">{{ $t('apfUi.edit_project') }}</button>
  <button v-if="project.status!=='archived'" type="button" :disabled="blocked" @click="emit('action','archive',project.id)">{{ $t('apfUi.move_to_trash') }}</button>
  <button v-else type="button" :disabled="blocked" @click="emit('action','restore',project.id)">{{ $t('apfUi.restore') }}</button>
  <div class="apf-detail-fields">
    <label>{{ $t('apfUi.name') }}<InlineField :value="project.name" :save="saveName" @cancelled="emit('cancel-field','name',project.id)" /></label>
    <label>{{ $t('apfUi.target') }}<InlineField :value="project.target_name" :save="saveTarget" @cancelled="emit('cancel-field','target_name',project.id)" /></label>
    <label>{{ $t('apfUi.notes') }}<InlineField :value="project.notes" kind="textarea" :save="saveNotes" @cancelled="emit('cancel-field','notes',project.id)" /></label>
  </div>
</template>
