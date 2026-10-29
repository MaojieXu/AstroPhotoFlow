<script setup lang="ts">
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
  catch(cause) {error.value=cause instanceof Error?cause.message:'拍摄预设读取失败。'}
  finally {loading.value=false}
}
onMounted(load)
</script>

<template>
  <fieldset class="apf-preset-picker" :disabled="disabled||loading">
    <legend>设备组合与拍摄预设（可选）<LibraryInfo label="设备组合与拍摄预设" text="预设只提供默认值；人工填写和文件实测值优先。接受导入时保存组合与预设快照。" /></legend>
    <label>设备组合<select v-model="setupId" aria-label="导入设备组合" @change="emit('update:modelValue','')"><option value="">不使用预设</option><option v-for="setup in setups" :key="setup.id" :value="setup.id">{{setup.name}}</option></select></label>
    <label v-if="setupId">拍摄预设<select :value="modelValue" aria-label="导入拍摄预设" @change="emit('update:modelValue',($event.target as HTMLSelectElement).value)"><option value="">选择拍摄预设</option><option v-for="preset in choices" :key="preset.id" :value="preset.id">{{preset.name}}</option></select></label>
    <p v-if="loading" role="status">正在读取使用组合…</p>
    <p v-else-if="error" role="alert">{{error}} <LibraryButton type="button" @click="load">重试</LibraryButton></p>
    <p v-else-if="!setups.length">尚无设备组合，可在设备管理→设备组合中创建。</p>
    <p v-else-if="setupId&&!choices.length">此组合尚无启用的拍摄预设。</p>
  </fieldset>
</template>
