<script setup lang="ts">
import { validatedInput } from '../../../core/api/input'
import { zCreateEquipmentApiV1EquipmentPostBody, zCreateSetupApiV1EquipmentSetupsPostBody, zPatchSetupApiV1EquipmentSetupsSetupIdPatchBody } from '../../../generated/api/zod.gen'
import { uiT } from '../../../core/i18n'

import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useCreateEquipment, useSaveSetup } from './mutations'
import { type EquipmentSetup } from '../api/contracts'
import { useEquipmentChoices } from './queries'
import { equipmentKinds, equipmentKindLabels } from './fields'
import type { EquipmentDeleteItem } from './EquipmentDeleteDialog.vue'
import LibraryTextField from '../components/LibraryTextField.vue'
import LibraryButton from '../components/LibraryButton.vue'
import LibraryDialog from '../components/LibraryDialog.vue'
import LibraryMultiSelect from '../components/LibraryMultiSelect.vue'
import LibrarySelect from '../components/LibrarySelect.vue'
import LibraryTextarea from '../components/LibraryTextarea.vue'
import EquipmentFields from './EquipmentFields.vue'
import { equipmentInput } from './drafts'
import { useSetupEditor } from './useSetupEditor'

const props = defineProps<{
  workspace: string
  selectedSetup?: EquipmentSetup
  viewKey: string
  changeToken: number
}>()
const emit = defineEmits<{
  dirty: [value: boolean]
  saving: [value: boolean]
  saved: [setup: EquipmentSetup, viewKey: string]
  delete: [items: EquipmentDeleteItem[]]
}>()
const createEquipment = useCreateEquipment()
const setupWrite = useSaveSetup()
const selectedSetup = computed(() => props.selectedSetup)
const equipmentQuery = useEquipmentChoices(() => props.workspace)
const relatedEquipment = computed(() => equipmentQuery.data.value ?? [])
const relatedEquipmentLoading = equipmentQuery.isFetching
const relatedEquipmentError = computed(() => equipmentQuery.error.value?.message ?? '')
const loadRelatedEquipment = equipmentQuery.refresh
const setupEditor = useSetupEditor(relatedEquipment)
const { editingSetup, setupDraft, deviceEditor, equipmentOriginal, registeredIds, setRegistered,
  equipmentOptions, componentKind, componentEquipment, accessoryOptions, setAccessory, singleValue, singleOptions, setSingle, addRegistered, count, invalidCounts, applyInline } = setupEditor
const equipmentNotice = ref('')
const saving = ref(false)
watch(saving,value=>emit('saving',value),{flush:'sync'})
const error = ref('')
let setupSelectionGeneration = 0
watch([() => props.workspace, () => props.viewKey, () => selectedSetup.value?.id], () => {setupSelectionGeneration++}, {flush:'sync'})
const dirty = computed(() => setupEditor.dirty.value)
watch(dirty, value => emit('dirty', value))
onBeforeUnmount(() => {emit('dirty',false); emit('saving',false); setupSelectionGeneration++})

function leaveDraft() {
  if (saving.value) return false
  if (dirty.value && !window.confirm(uiT('apfUi.this_setup_has_unsaved_changes_discard_them'))) return false
  setupEditor.reset(); error.value = ''
  return true
}
function beginSetup(row: EquipmentSetup | null) {
  if (!leaveDraft()) return
  setupEditor.beginSetup(row)
  equipmentNotice.value = ''
  void loadRelatedEquipment(true)
}
function beginEquipment(kind: Parameters<typeof setupEditor.beginEquipment>[0]) {
  setupEditor.beginEquipment(kind); error.value = ''
}
function editInline(index: number) {
  setupEditor.editInline(index); error.value = ''
}
function returnToSetup(){
  if(saving.value)return
  if(deviceEditor.value&&JSON.stringify(deviceEditor.value.equipment)!==equipmentOriginal.value&&!window.confirm(uiT('apfUi.this_device_has_unsaved_changes_discard_them_and_return_to_the_setup')))return
  deviceEditor.value=undefined;error.value=''
}
function closeSetup(){if(deviceEditor.value)returnToSetup();else leaveDraft()}
async function saveEquipment(){
  if(saving.value)return
  const current=deviceEditor.value!
  if(current.source==='inline'){
    if (!applyInline(current.index,current.equipment)) { error.value=uiT('apfUi.setup_single_hardware_limit'); return }
    deviceEditor.value=undefined;return
  }
  const generation=setupSelectionGeneration
  const workspaceId=props.workspace
  saving.value=true;error.value=''
  try{
    const device=current.equipment
    const saved=await createEquipment.mutateAsync({workspaceId,body:validatedInput(zCreateEquipmentApiV1EquipmentPostBody,{
      ...equipmentInput(device),model:device.model||null,notes:device.notes||null
    })})
    if(generation!==setupSelectionGeneration)return
    addRegistered(device.kind,saved.id)
    await loadRelatedEquipment(true)
    deviceEditor.value=undefined
    equipmentNotice.value=uiT('apfUi.saved_value_to_my_equipment_canceling_this_setup_will_retain_the_devic', { p0: (saved.name) })
  }catch(cause){if(generation===setupSelectionGeneration)error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_save_the_equipment')}
  finally{saving.value=false}
}
async function saveSetup() {
  if(saving.value)return
  if(invalidCounts.value){error.value=uiT('apfUi.setup_single_hardware_limit');return}
  const generation = setupSelectionGeneration
  const viewKey = props.viewKey
  const workspaceId = props.workspace
  const currentView = () => generation === setupSelectionGeneration && props.viewKey === viewKey
  saving.value = true; error.value = ''
  try {
    const payload = {...setupDraft.value,notes:setupDraft.value.notes || null,
      components: setupDraft.value.components.map(component => component.source === 'inline'
        ? { ...component, equipment: equipmentInput(component.equipment) } : component)}
    const current = editingSetup.value
    const saved = current
      ? await setupWrite.mutateAsync({workspaceId,action:'update',setupId:current.id,body:validatedInput(zPatchSetupApiV1EquipmentSetupsSetupIdPatchBody,{...payload,base_revision:current.revision})})
      : await setupWrite.mutateAsync({workspaceId,action:'create',body:validatedInput(zCreateSetupApiV1EquipmentSetupsPostBody,{name:payload.name,components:payload.components,notes:payload.notes})})
    if (!currentView()) return
    editingSetup.value = undefined
    equipmentNotice.value = ''
    emit('saved', saved, viewKey)
  } catch (cause) {if(currentView())error.value = cause instanceof Error ? cause.message : uiT('apfUi.could_not_save_the_setup')}
  finally {saving.value = false}
}
watch([() => props.workspace, () => selectedSetup.value?.id, () => props.changeToken], () => setupEditor.reset())

defineExpose({ beginSetup })
</script>

<template>
  <section class="apf-setup-manager" :aria-label="$t('apfUi.equipment_setups')">
    <slot name="records" />
    <LibraryDialog :open="editingSetup!==undefined" :title="deviceEditor?(deviceEditor.source==='new'?$t('apfUi.new')+equipmentKindLabels[deviceEditor.equipment.kind]:$t('apfUi.edit_equipment_in_setup')):(editingSetup?$t('apfUi.edit'):$t('apfUi.new'))+$t('apfUi.equipment_setup')" :label="deviceEditor?$t('apfUi.equipment_form'):$t('apfUi.equipment_setup_form')" :busy="saving" @close="closeSetup">
      <form v-if="editingSetup!==undefined" class="apf-editor" :aria-label="deviceEditor?$t('apfUi.new_equipment_form'):$t('apfUi.equipment_setup_form')" @submit.prevent="deviceEditor?saveEquipment():saveSetup()">
        <div class="apf-equipment-dialog-body">
          <template v-if="deviceEditor">
            <EquipmentFields v-model="deviceEditor.equipment" :kind-editable="deviceEditor.source==='inline'" />
          </template>
          <template v-else>
            <LibraryTextField id="setup-name" v-model="setupDraft.name" class="apf-field-row" :name="$t('apfUi.setup_name')" required autofocus />
            <label class="apf-field-row">{{ $t('apfUi.setup_description') }}<LibraryTextarea v-model="setupDraft.notes" /></label>
            <div class="apf-combination-fields" :aria-label="$t('apfUi.setup_equipment')">
              <div v-for="kind in equipmentKinds" :key="kind" class="apf-combination-row">
                <span>{{equipmentKindLabels[kind]}}</span>
                <LibrarySelect v-if="kind!=='filter'" :model-value="singleValue(kind)" :label="$t('apfUi.select')+equipmentKindLabels[kind]" :options="singleOptions(kind)" :disabled="saving||relatedEquipmentLoading" @update:model-value="setSingle(kind,$event)" />
                <LibraryMultiSelect v-else :model-value="registeredIds(kind)" :label="$t('apfUi.select')+equipmentKindLabels[kind]" :options="equipmentOptions(kind)" :disabled="saving||relatedEquipmentLoading" @update:model-value="setRegistered(kind,$event)" />
                <LibraryButton type="button" :aria-label="$t('apfUi.new')+equipmentKindLabels[kind]" :tooltip="$t('apfUi.new')+equipmentKindLabels[kind]" :disabled="saving" @click="beginEquipment(kind)">+</LibraryButton>
              </div>
            </div>
            <p v-if="invalidCounts" role="alert" class="apf-error">{{ $t('apfUi.setup_single_hardware_limit') }}</p>
            <div v-for="(component,index) in setupDraft.components" :key="index">
              <div v-if="component.source==='inline'" class="apf-legacy-component">
                <span>{{component.equipment.name}} · {{$t('apfUi.equipment_in_setup')}}</span>
                <LibraryButton v-if="component.source==='inline'" type="button" @click="editInline(index)">{{ $t('apfUi.edit') }}</LibraryButton>
                <LibraryButton type="button" @click="setupDraft.components.splice(index,1)">{{ $t('apfUi.remove') }}</LibraryButton>
              </div>
            </div>
            <div v-for="(component,index) in setupDraft.components" :key="'optics-'+index">
              <label v-if="componentKind(component)==='telescope'" class="apf-field-row">{{componentEquipment(component)?.name}} · {{ $t('apfUi.optical_accessory') }}
                <LibrarySelect :model-value="component.optical_accessory_id??''" :label="$t('apfUi.optical_accessory')" :options="accessoryOptions(component)" :disabled="saving||relatedEquipmentLoading" @update:model-value="setAccessory(index,$event)" />
              </label>
            </div>
            <p v-if="relatedEquipmentError" role="alert">{{relatedEquipmentError}}</p>
            <p v-if="equipmentNotice" role="status">{{equipmentNotice}}</p>
          </template>
          <p v-if="error" role="alert" class="apf-error">{{error}}</p>
        </div>
        <footer class="apf-equipment-dialog-footer">
          <LibraryButton type="button" :disabled="saving" @click="closeSetup">{{deviceEditor?$t('apfUi.back_to_setup'):$t('apfUi.cancel')}}</LibraryButton>
          <LibraryButton type="submit" variant="primary" :disabled="saving">{{saving?$t('apfUi.saving'):deviceEditor?(deviceEditor.source==='new'?(deviceEditor.equipment.kind!=='filter'&&count(deviceEditor.equipment.kind)>0?$t('apfUi.save_device_and_replace'):$t('apfUi.save_and_add_device')):$t('apfUi.apply_to_setup_draft')):$t('apfUi.save_equipment_setup')}}</LibraryButton>
        </footer>
      </form>
    </LibraryDialog>
    <p v-if="equipmentNotice&&editingSetup===undefined" role="status">{{equipmentNotice}}</p>
    <p v-if="error" role="alert" class="apf-error">{{error}}</p>
  </section>
</template>
