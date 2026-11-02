<script setup lang="ts">
import { computed } from 'vue'
import type { RecordEditorState, ProjectEditorField } from './editorTypes'
import InlineField from '../components/InlineField.vue'
import LibraryButton from '../components/LibraryButton.vue'
import LibraryTextField from '../components/LibraryTextField.vue'
import LibraryDialog from '../components/LibraryDialog.vue'
import EquipmentFields from '../equipment/EquipmentFields.vue'

const model = defineModel<RecordEditorState>({ required: true })
const props = defineProps<{
  saving: boolean
  savingInline: number
  error?: string
  inlineError: string
  saveField: (field: ProjectEditorField, value: string | number | null) => Promise<void>
}>()
const emit = defineEmits<{ submit: []; close: []; 'cancel-field': [field: ProjectEditorField] }>()
const busy = computed(() => props.saving || props.savingInline > 0)
function projectField(field: ProjectEditorField, value: string) {
  if (model.value.kind === 'project') model.value = { ...model.value, draft: { ...model.value.draft, [field]: value } }
}
</script>

<template>
  <component :is="model.kind==='equipment'?LibraryDialog:'section'" :open="true" :title="model.id?$t('apfUi.edit_equipment'):$t('apfUi.new_equipment')" :label="$t('apfUi.record_editor')" :busy="busy" @close="emit('close')">
    <form class="apf-editor" :aria-label="$t('apfUi.record_editor')" @submit.prevent="emit('submit')">
      <div class="apf-equipment-dialog-body">
        <h2 v-if="model.kind==='project'">{{model.id?$t('apfUi.edit_project'):$t('apfUi.create_project')}}</h2>
        <EquipmentFields v-if="model.kind==='equipment'" :model-value="model.draft" kind-editable :kind-disabled="Boolean(model.id)" :name-label="$t('apfUi.name')" @update:model-value="model={...model,draft:$event}" />
        <template v-else-if="model.id">
          <label class="apf-field-row">{{ $t('apfUi.name') }}<InlineField :value="model.draft.name" :save="value=>saveField('name',value)" @cancelled="emit('cancel-field','name')" /></label>
          <label class="apf-field-row">{{ $t('apfUi.target') }}<InlineField :value="model.draft.target_name" :display="model.draft.target_name||$t('apfUi.not_specified')" :save="value=>saveField('target_name',value)" @cancelled="emit('cancel-field','target_name')" /></label>
          <label class="apf-field-row">{{ $t('apfUi.description_4262c4') }}<InlineField :value="model.draft.notes" kind="textarea" :save="value=>saveField('notes',value)" @cancelled="emit('cancel-field','notes')" /></label>
        </template>
        <template v-else>
          <LibraryTextField id="project-name" :model-value="model.draft.name" @update:model-value="projectField('name',$event??'')" :name="$t('apfUi.name')" required />
          <label>{{ $t('apfUi.target') }}<input :value="model.draft.target_name" @input="projectField('target_name',($event.target as HTMLInputElement).value)" /></label>
          <label>{{ $t('apfUi.description_4262c4') }}<textarea :value="model.draft.notes" @input="projectField('notes',($event.target as HTMLTextAreaElement).value)" /></label>
        </template>
        <p v-if="error" role="alert">{{error}}</p>
        <p v-if="inlineError" role="alert">{{inlineError}}</p>
      </div>
      <footer class="apf-equipment-dialog-footer apf-form-actions">
        <LibraryButton type="button" :disabled="busy" @click="emit('close')">{{model.id&&model.kind!=='equipment'?$t('apfUi.close'):$t('apfUi.cancel')}}</LibraryButton>
        <LibraryButton v-if="!model.id||model.kind==='equipment'" type="submit" variant="primary" :disabled="saving">{{saving?$t('apfUi.saving'):$t('apfUi.save')}}</LibraryButton>
      </footer>
    </form>
  </component>
</template>
