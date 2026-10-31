<script setup lang="ts">

import { inject } from 'vue'
import type { SetupComponent } from '../api/contracts'
import type { WorkspaceContext } from './Workspace.vue'
import LibraryInput from './LibraryInput.vue'
import LibrarySelect from './LibrarySelect.vue'
import LibraryTextField from './LibraryTextField.vue'
import LibraryTextarea from './LibraryTextarea.vue'

export type EquipmentDraft = Extract<SetupComponent,{source:'inline'}>['equipment']
const equipment = defineModel<EquipmentDraft>({required:true})
const { kindEditable = false, kindDisabled = false, nameLabel } = defineProps<{kindEditable?:boolean;kindDisabled?:boolean;nameLabel?:string}>()
const context = inject<WorkspaceContext>('workspace')!
function changeKind(value:string|number|null|undefined){equipment.value={...equipment.value,kind:value as EquipmentDraft['kind'],specs:{}}}
function setSpec(key:string,numeric:boolean,value:string|number|null|undefined){
  const parsed=value===''||value==null?null:numeric?Number(value):value
  if(key==='pixel_size_um'){
    delete equipment.value.specs.pixel_size_um
    equipment.value.specs.pixel_size_x_um=parsed;equipment.value.specs.pixel_size_y_um=parsed
  }else equipment.value.specs[key]=parsed
}
</script>

<template>
  <div class="apf-equipment-fields">
    <label v-if="kindEditable" class="apf-field-row">{{ $t('apfUi.equipment_type') }}<LibrarySelect :model-value="equipment.kind" :label="$t('apfUi.equipment_type')" :disabled="kindDisabled" :options="[...(equipment.kind==='optical_system'?[{value:'optical_system',name:context.equipmentKindLabels.optical_system}]:[]),...context.equipmentKinds.map(value=>({value,name:context.equipmentKindLabels[value]}))]" @update:model-value="changeKind" /></label>
    <LibraryTextField id="device-name" v-model="equipment.name" class="apf-field-row" :name="nameLabel ?? $t('apfUi.equipment_name')" required autofocus />
    <label class="apf-field-row">{{ $t('apfUi.model') }}<LibraryInput :model-value="equipment.model" @update:model-value="equipment.model=$event==null?null:String($event)" /></label>
    <label class="apf-field-row">{{ $t('apfUi.serial_number') }}<LibraryInput :model-value="equipment.serial_number" @update:model-value="equipment.serial_number=$event==null?null:String($event)" /></label>
    <label v-for="field in context.specFields[equipment.kind]" :key="field.key" class="apf-field-row">{{field.label}}
      <LibrarySelect v-if="field.options||field.key==='cfa_pattern'" :model-value="context.textInput(context.specValue(field,equipment.specs))" :label="field.label" :options="context.specChoices(field).map(choice=>({value:choice.value,name:choice.label}))" @update:model-value="setSpec(field.key,false,$event)" />
      <LibraryInput v-else :model-value="context.textInput(context.specValue(field,equipment.specs))" :type="field.type??'text'" :step="field.integer?1:'any'" @update:model-value="setSpec(field.key,field.type==='number',$event)" />
    </label>
    <label class="apf-field-row">{{ $t('apfUi.equipment_description') }}<LibraryTextarea :model-value="equipment.notes" @update:model-value="equipment.notes=$event??null" /></label>
  </div>
</template>
