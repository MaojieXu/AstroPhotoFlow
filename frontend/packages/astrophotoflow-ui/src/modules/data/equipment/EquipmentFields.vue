<script setup lang="ts">
import { computed, useId } from 'vue'
import type { EquipmentDraft } from './drafts'
import { equipmentKindLabels, equipmentKinds, specFields, specChoices, specValue } from './fields'
import LibraryInput from '../components/LibraryInput.vue'
import LibrarySelect from '../components/LibrarySelect.vue'
import LibraryTextarea from '../components/LibraryTextarea.vue'
import OpticalAccessoriesEditor from './OpticalAccessoriesEditor.vue'
import { filterLabel } from './filterLabels'
import type { FilterSpecs, TelescopeSpecs } from '../../../generated/api/types.gen'

const equipment = defineModel<EquipmentDraft>({ required: true })
const { kindEditable = false, kindDisabled = false, nameLabel } = defineProps<{kindEditable?: boolean; kindDisabled?: boolean; nameLabel?: string}>()
const formId = useId()
const filterPreview = computed(() => filterLabel({ name: equipment.value.name, specs: equipment.value.specs as FilterSpecs }))
function textField(key: 'name' | 'model' | 'notes', value: string | number | null | undefined) {
  if (key === 'name') equipment.value = {...equipment.value, name: value == null ? '' : String(value)}
  else equipment.value = {...equipment.value, [key]: value == null ? null : String(value)}
}
function changeKind(value: string | number | null | undefined) { equipment.value = {...equipment.value, kind: value as EquipmentDraft['kind'], specs: {}} }
function setSpec(key: string, numeric: boolean, value: string | number | null | undefined) {
  const parsed = value === '' || value == null ? null : numeric ? Number(value) : value
  equipment.value = {...equipment.value, specs: {...equipment.value.specs, [key]: parsed}}
}
</script>

<template>
  <div class="apf-equipment-fields apf-device-form">
    <section class="apf-device-section" :aria-labelledby="formId+'-basic'">
      <h3 :id="formId+'-basic'">{{ $t('apfUi.equipment_basic_information') }}</h3>
      <div class="apf-device-grid">
        <label v-if="kindEditable" class="apf-device-field apf-device-field-wide">
          <span>{{ $t('apfUi.equipment_type') }}</span>
          <LibrarySelect :model-value="equipment.kind" :label="$t('apfUi.equipment_type')" :searchable="false" density="compact" :disabled="kindDisabled" :options="equipmentKinds.map(value=>({value,name:equipmentKindLabels[value]}))" @update:model-value="changeKind" />
        </label>
        <label class="apf-device-field">
          <span>{{ nameLabel ?? $t('apfUi.equipment_name') }}</span>
          <LibraryInput :model-value="equipment.name" :aria-label="nameLabel ?? $t('apfUi.equipment_name')" required autofocus @update:model-value="textField('name',$event)" />
        </label>
        <label class="apf-device-field">
          <span>{{ $t('apfUi.model') }}</span>
          <LibraryInput :model-value="equipment.model" :aria-label="$t('apfUi.model')" @update:model-value="textField('model',$event)" />
        </label>
      </div>
    </section>
    <section class="apf-device-section" :aria-labelledby="formId+'-parameters'">
      <h3 :id="formId+'-parameters'">{{ $t('apfUi.equipment_parameters') }}</h3>
      <div class="apf-device-grid">
        <label v-for="field in specFields[equipment.kind]" :key="field.key" class="apf-device-field" :class="{'apf-device-field-wide':field.key==='cfa_pattern'}">
          <span>{{ field.label }}</span>
          <LibrarySelect v-if="field.options||field.key==='cfa_pattern'" :searchable="field.key!=='cfa_pattern'" :density="field.key==='cfa_pattern'?'compact':'normal'" :model-value="String(specValue(field,equipment.specs)??'')" :label="field.label" :options="specChoices(field).map(choice=>({value:choice.value,name:choice.label}))" @update:model-value="setSpec(field.key,false,$event)" />
          <span v-else class="apf-device-input-unit">
            <LibraryInput :model-value="String(specValue(field,equipment.specs)??'')" :aria-label="field.label" :type="field.type??'text'" :step="field.integer?1:'any'" @update:model-value="setSpec(field.key,field.type==='number',$event)" />
            <span v-if="field.unit" class="apf-device-unit" aria-hidden="true">{{ field.unit }}</span>
          </span>
        </label>
      </div>
      <div v-if="equipment.kind==='filter'" class="apf-device-field">
        <span>{{ $t('apfUi.filter_channel_preview') }}</span>
        <output :aria-label="$t('apfUi.filter_channel_preview')">{{ filterPreview }}</output>
      </div>
    </section>
    <OpticalAccessoriesEditor v-if="equipment.kind==='telescope'" :model-value="(equipment.specs.optical_accessories ?? []) as NonNullable<TelescopeSpecs['optical_accessories']>" @update:model-value="equipment={...equipment,specs:{...equipment.specs,optical_accessories:$event}}" />
    <section class="apf-device-section">
      <label class="apf-device-field">
        <span>{{ $t('apfUi.equipment_description') }}</span>
        <LibraryTextarea :model-value="equipment.notes" :aria-label="$t('apfUi.equipment_description')" @update:model-value="textField('notes',$event)" />
      </label>
    </section>
  </div>
</template>
