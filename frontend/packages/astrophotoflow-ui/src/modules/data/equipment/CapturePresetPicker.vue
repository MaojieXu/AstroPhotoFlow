<script setup lang="ts">
import { uiT } from '../../../core/i18n'
import { computed, ref, watch } from 'vue'
import LibraryInfo from '../components/LibraryInfo.vue'
import LibraryButton from '../components/LibraryButton.vue'
import { useImportPresetChoices } from './queries'

const props=defineProps<{workspaceId:string;modelValue:string;disabled?:boolean}>()
const emit=defineEmits<{'update:modelValue':[value:string]}>()
const setupId=ref('')
const query=useImportPresetChoices(()=>props.workspaceId)
const setups=computed(()=>query.data.value?.setups??[])
const choices=computed(()=>query.data.value?.presets.filter(preset=>preset.equipment_setup_id===setupId.value)??[])
const loading=query.isPending
const error=computed(()=>query.error.value instanceof Error?query.error.value.message:query.isError.value?uiT('apfUi.could_not_read_capture_presets'):'')
function load(){return query.refetch({cancelRefetch:false})}
watch(()=>props.workspaceId,()=>{setupId.value='';emit('update:modelValue','')})
</script>

<template>
  <fieldset class="apf-preset-picker" :disabled="disabled||loading">
    <legend>{{ $t('apfUi.equipment_setups_and_capture_presets_optional') }}<LibraryInfo :label="$t('apfUi.equipment_setups_and_capture_presets')" :text="$t('apfUi.presets_provide_defaults_only_manual_input_and_measured_file_values_ta')" /></legend>
    <label>{{ $t('apfUi.equipment_setup') }}<select v-model="setupId" :aria-label="$t('apfUi.import_equipment_setup')" @change="emit('update:modelValue','')"><option value="">{{ $t('apfUi.no_preset') }}</option><option v-if="setupId&&!setups.some(setup=>setup.id===setupId)" :value="setupId" disabled>{{ $t('apfUi.unavailable') }} · {{setupId}}</option><option v-for="setup in setups" :key="setup.id" :value="setup.id">{{setup.name}}</option></select></label>
    <label v-if="setupId">{{ $t('apfUi.capture_preset') }}<select :value="modelValue" :aria-label="$t('apfUi.import_capture_preset')" @change="emit('update:modelValue',($event.target as HTMLSelectElement).value)"><option value="">{{ $t('apfUi.select_capture_preset') }}</option><option v-if="modelValue&&!choices.some(preset=>preset.id===modelValue)" :value="modelValue" disabled>{{ $t('apfUi.unavailable') }} · {{modelValue}}</option><option v-for="preset in choices" :key="preset.id" :value="preset.id">{{preset.name}}</option></select></label>
    <p v-if="loading" role="status">{{ $t('apfUi.reading_setup_usage') }}</p>
    <p v-else-if="error" role="alert">{{error}} <LibraryButton type="button" @click="load">{{ $t('apfUi.retry') }}</LibraryButton></p>
    <p v-else-if="!setups.length">{{ $t('apfUi.no_equipment_setups_yet_create_one_in_equipment_setups') }}</p>
    <p v-else-if="setupId&&!choices.length">{{ $t('apfUi.no_active_capture_presets_in_this_setup') }}</p>
  </fieldset>
</template>
