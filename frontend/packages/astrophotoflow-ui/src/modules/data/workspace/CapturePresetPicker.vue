<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import { computed, onMounted, ref } from 'vue'
import LibraryInfo from './LibraryInfo.vue'
import LibraryButton from './LibraryButton.vue'
import type { ZodType } from 'zod'
import { assetApi } from '../api/index'
import { capturePresetSchema, equipmentSetupSchema, pageSchema, type CapturePreset, type EquipmentSetup } from '../api/contracts'

defineProps<{modelValue:string;disabled?:boolean}>()
const emit = defineEmits<{'update:modelValue':[value:string]}>()
const setups = ref<EquipmentSetup[]>([])
const presets = ref<CapturePreset[]>([])
const setupId = ref('')
const loading = ref(false)
const error = ref('')
const choices = computed(() => presets.value.filter(preset => preset.equipment_setup_id === setupId.value))
async function pages<T>(path:string,schema:ZodType<T>) {
  const result:T[] = []
  for (let offset=0;;offset+=200) {
    const page = await assetApi.get('/astrophotoflow/api/v1/'+path+'?limit=200&offset='+offset+'&sort_by=name&order=asc&status=active',pageSchema(schema))
    result.push(...page.items)
    if (offset+page.limit >= page.total) return result
  }
}
async function load() {
  loading.value=true;error.value=''
  try {[setups.value,presets.value] = await Promise.all([pages('equipment-setups',equipmentSetupSchema),pages('capture-presets',capturePresetSchema)])}
  catch(cause) {error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_read_capture_presets')}
  finally {loading.value=false}
}
onMounted(load)
</script>

<template>
  <fieldset class="apf-preset-picker" :disabled="disabled||loading">
    <legend>{{ $t('apfUi.equipment_setups_and_capture_presets_optional') }}<LibraryInfo :label="$t('apfUi.equipment_setups_and_capture_presets')" :text="$t('apfUi.presets_provide_defaults_only_manual_input_and_measured_file_values_ta')" /></legend>
    <label>{{ $t('apfUi.equipment_setup') }}<select v-model="setupId" :aria-label="$t('apfUi.import_equipment_setup')" @change="emit('update:modelValue','')"><option value="">{{ $t('apfUi.no_preset') }}</option><option v-for="setup in setups" :key="setup.id" :value="setup.id">{{setup.name}}</option></select></label>
    <label v-if="setupId">{{ $t('apfUi.capture_preset') }}<select :value="modelValue" :aria-label="$t('apfUi.import_capture_preset')" @change="emit('update:modelValue',($event.target as HTMLSelectElement).value)"><option value="">{{ $t('apfUi.select_capture_preset') }}</option><option v-for="preset in choices" :key="preset.id" :value="preset.id">{{preset.name}}</option></select></label>
    <p v-if="loading" role="status">{{ $t('apfUi.reading_setup_usage') }}</p>
    <p v-else-if="error" role="alert">{{error}} <LibraryButton type="button" @click="load">{{ $t('apfUi.retry') }}</LibraryButton></p>
    <p v-else-if="!setups.length">{{ $t('apfUi.no_equipment_setups_yet_create_one_in_equipment_setups') }}</p>
    <p v-else-if="setupId&&!choices.length">{{ $t('apfUi.no_active_capture_presets_in_this_setup') }}</p>
  </fieldset>
</template>
