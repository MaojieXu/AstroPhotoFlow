<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { EquipmentApplication } from '../../../generated/api/types.gen'
import type { EquipmentSetup } from '../api/contracts'
import { useImportEquipmentChoices } from './queries'
import { equipmentKindLabels, equipmentKinds } from './fields'
import LibraryButton from '../components/LibraryButton.vue'

const props = defineProps<{workspaceId:string; disabled?:boolean}>()
const model = defineModel<EquipmentApplication>()
const emit = defineEmits<{valid:[value:boolean]}>()
const mode = ref<'devices'|'setup'>('devices')
const setupId = ref('')
const filterChoice = ref('')
const deviceIds = ref({camera:'',telescope:'',filter:'',mount:''})
const accessoryId = ref('')
const query = useImportEquipmentChoices(() => props.workspaceId)
const equipment = computed(() => query.data.value?.equipment ?? [])
const setups = computed(() => query.data.value?.setups ?? [])
const setup = computed(() => setups.value.find(row => row.id === setupId.value))
const telescope = computed(() => equipment.value.find(row => row.id === deviceIds.value.telescope))
const accessories = computed(() => telescope.value?.kind === 'telescope' ? telescope.value.specs.optical_accessories ?? [] : [])
const componentKind = (component:EquipmentSetup['components'][number]) => component.source === 'inline' ? component.equipment.kind : equipment.value.find(row => row.id === component.equipment_id)?.kind
const setupFilters = computed(() => setup.value?.components.filter(row => componentKind(row) === 'filter') ?? [])
const componentName = (component:EquipmentSetup['components'][number]) => component.source === 'inline' ? component.equipment.name : equipment.value.find(row => row.id === component.equipment_id)?.name ?? component.equipment_id
const valid = computed(() => mode.value !== 'setup' || !setupId.value || Boolean(setup.value && (setupFilters.value.length <= 1 || filterChoice.value)))
const application = computed<EquipmentApplication | undefined>(() => {
  if (mode.value === 'setup') {
    if (!setup.value || !valid.value) return undefined
    const fields:EquipmentApplication['fields'] = []
    for (const kind of equipmentKinds) if (setup.value.components.some(row => componentKind(row) === kind)) fields.push(kind)
    if (fields.includes('telescope')) fields.push('optical_accessory')
    if (!fields.length) return undefined
    return {choice:{source:'setup',setup_id:setup.value.id,expected_revision:setup.value.revision,
      filter:filterChoice.value === 'none' ? {mode:'none'} : filterChoice.value ? {mode:'member',member_id:filterChoice.value} : {mode:'inherit'}},fields}
  }
  const choice:Extract<EquipmentApplication['choice'],{source:'devices'}> = {source:'devices'}
  const fields:EquipmentApplication['fields'] = []
  for (const kind of equipmentKinds) {
    const device = equipment.value.find(row => row.id === deviceIds.value[kind] && row.kind === kind)
    if (device) {choice[kind] = {equipment_id:device.id,expected_revision:device.revision};fields.push(kind)}
  }
  if (choice.telescope) {choice.optical_accessory_id = accessoryId.value || null;fields.push('optical_accessory')}
  return fields.length ? {choice,fields} : undefined
})
watch(application,value => {model.value = value},{immediate:true,deep:true})
watch(valid,value => emit('valid',value),{immediate:true})
watch(() => deviceIds.value.telescope,() => {accessoryId.value = ''})
watch(setupId,() => {filterChoice.value = ''})
watch(() => props.workspaceId,() => {setupId.value='';deviceIds.value={camera:'',telescope:'',filter:'',mount:''};accessoryId.value='';filterChoice.value=''})
</script>

<template>
  <fieldset :disabled="disabled" class="apf-equipment-association">
    <legend>{{ $t('apfUi.equipment_association_optional') }}</legend>
    <label>{{ $t('apfUi.equipment_selection_method') }}<select v-model="mode"><option value="devices">{{ $t('apfUi.select_devices_directly') }}</option><option value="setup">{{ $t('apfUi.select_equipment_setup') }}</option></select></label>
    <template v-if="mode === 'devices'">
      <label v-for="kind in equipmentKinds" :key="kind">{{equipmentKindLabels[kind]}}<select v-model="deviceIds[kind]" :aria-label="equipmentKindLabels[kind]"><option value="">{{ $t('apfUi.not_specified') }}</option><option v-for="row in equipment.filter(item => item.kind === kind)" :key="row.id" :value="row.id">{{row.name}}</option></select></label>
      <label v-if="deviceIds.telescope">{{ $t('apfUi.optical_accessory') }}<select v-model="accessoryId" :aria-label="$t('apfUi.optical_accessory')"><option value="">{{ $t('apfUi.do_not_use') }}</option><option v-for="row in accessories" :key="row.id" :value="row.id">{{row.name}}</option></select></label>
    </template>
    <template v-else>
      <label>{{ $t('apfUi.equipment_setup') }}<select v-model="setupId" :aria-label="$t('apfUi.import_equipment_setup')"><option value="">{{ $t('apfUi.not_specified') }}</option><option v-for="row in setups" :key="row.id" :value="row.id">{{row.name}}</option></select></label>
      <label v-if="setupFilters.length">{{ $t('apfUi.filter') }}<select v-model="filterChoice" :aria-label="$t('apfUi.filter')"><option value="">{{ $t('apfUi.select_actual_filter') }}</option><option value="none">{{ $t('apfUi.do_not_use') }}</option><option v-for="row in setupFilters" :key="row.id" :value="row.id">{{componentName(row)}}</option></select></label>
      <p v-if="!valid" role="alert">{{ $t('apfUi.multiple_filters_require_selection') }}</p>
    </template>
    <p>{{ $t('apfUi.equipment_does_not_override_capture_parameters') }}</p>
    <p v-if="query.isPending.value" role="status">{{ $t('apfUi.reading_setup_usage') }}</p>
    <p v-if="query.error.value" role="alert">{{query.error.value.message}} <LibraryButton type="button" @click="query.refetch()">{{ $t('apfUi.retry') }}</LibraryButton></p>
  </fieldset>
</template>
