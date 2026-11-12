<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { CameraSpecs, EquipmentApplication } from '../../../generated/api/types.gen'
import type { EquipmentSetup } from '../api/contracts'
import { useImportEquipmentChoices } from './queries'
import { equipmentKindLabels, equipmentKinds } from './fields'
import LibraryButton from '../components/LibraryButton.vue'
import LibraryInfo from '../components/LibraryInfo.vue'
import LibrarySelect from '../components/LibrarySelect.vue'

const props = defineProps<{workspaceId:string; disabled?:boolean}>()
const model = defineModel<EquipmentApplication>()
const cameraMode = defineModel<CameraSpecs['default_parameter_mode']>('cameraMode')
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
const accessoryOptions = computed(() => telescope.value?.kind === 'telescope'
  ? (telescope.value.specs.optical_accessories ?? []).flatMap(row => row.id ? [{ value: row.id, name: row.name }] : [])
  : [])
const componentDevice = (component:EquipmentSetup['components'][number]) =>
  component.source === 'inline' ? component.equipment : equipment.value.find(row => row.id === component.equipment_id)
const componentKind = (component:EquipmentSetup['components'][number]) => componentDevice(component)?.kind
const setupFilters = computed(() => setup.value?.components.filter(row => componentKind(row) === 'filter') ?? [])
const componentName = (component:EquipmentSetup['components'][number]) =>
  componentDevice(component)?.name ?? (component.source === 'registered' ? component.equipment_id : component.equipment.name)
const selectedCamera = computed(() => mode.value === 'setup'
  ? setup.value?.components.map(componentDevice).find(device => device?.kind === 'camera')
  : equipment.value.find(device => device.id === deviceIds.value.camera))
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
watch(selectedCamera, camera => {
  cameraMode.value = camera?.kind === 'camera' ? camera.specs?.default_parameter_mode : undefined
}, { immediate: true })
watch(valid,value => emit('valid',value),{immediate:true})
watch(() => deviceIds.value.telescope,() => {accessoryId.value = ''})
watch(setupId,() => {filterChoice.value = ''})
watch(() => props.workspaceId,() => {setupId.value='';deviceIds.value={camera:'',telescope:'',filter:'',mount:''};accessoryId.value='';filterChoice.value=''})
</script>

<template>
  <fieldset :disabled="disabled" class="apf-device-section m-0 border-0 p-0">
    <legend class="mb-1 flex items-center gap-1 p-0 text-[13px] font-semibold">
      {{ $t('apfUi.equipment_association_optional') }}
      <LibraryInfo
        :label="$t('apfUi.equipment_association_optional')"
        :text="$t('apfUi.import_camera_defaults_help')"
      />
    </legend>
    <div class="apf-device-grid">
      <label class="apf-device-field">
        <span>{{ $t('apfUi.equipment_selection_method') }}</span>
        <LibrarySelect
          :model-value="mode"
          :label="$t('apfUi.equipment_selection_method')"
          density="compact"
          :searchable="false"
          :disabled="disabled"
          :options="[
            { value: 'devices', name: $t('apfUi.select_devices_directly') },
            { value: 'setup', name: $t('apfUi.select_equipment_setup') }
          ]"
          @update:model-value="mode = $event === 'setup' ? 'setup' : 'devices'"
        />
      </label>
      <template v-if="mode === 'devices'">
        <label v-for="kind in equipmentKinds" :key="kind" class="apf-device-field">
          <span>{{ equipmentKindLabels[kind] }}</span>
          <LibrarySelect
            :model-value="deviceIds[kind]"
            :label="equipmentKindLabels[kind]"
            density="compact"
            :disabled="disabled"
            :options="[
              { value: '', name: $t('apfUi.not_specified') },
              ...equipment.filter(item => item.kind === kind).map(row => ({ value: row.id, name: row.name }))
            ]"
            @update:model-value="deviceIds[kind] = String($event ?? '')"
          />
        </label>
        <label v-if="deviceIds.telescope" class="apf-device-field">
          <span>{{ $t('apfUi.optical_accessory') }}</span>
          <LibrarySelect
            :model-value="accessoryId"
            :label="$t('apfUi.optical_accessory')"
            density="compact"
            :disabled="disabled"
            :options="[
              { value: '', name: $t('apfUi.do_not_use') },
              ...accessoryOptions
            ]"
            @update:model-value="accessoryId = String($event ?? '')"
          />
        </label>
      </template>
      <template v-else>
        <label class="apf-device-field">
          <span>{{ $t('apfUi.equipment_setup') }}</span>
          <LibrarySelect
            :model-value="setupId"
            :label="$t('apfUi.import_equipment_setup')"
            density="compact"
            :disabled="disabled"
            :options="[
              { value: '', name: $t('apfUi.not_specified') },
              ...setups.map(row => ({ value: row.id, name: row.name }))
            ]"
            @update:model-value="setupId = String($event ?? '')"
          />
        </label>
        <label v-if="setupFilters.length" class="apf-device-field">
          <span>{{ $t('apfUi.filter') }}</span>
          <LibrarySelect
            :model-value="filterChoice"
            :label="$t('apfUi.filter')"
            density="compact"
            :disabled="disabled"
            :options="[
              { value: '', name: $t('apfUi.select_actual_filter') },
              { value: 'none', name: $t('apfUi.do_not_use') },
              ...setupFilters.map(row => ({ value: row.id, name: componentName(row) }))
            ]"
            @update:model-value="filterChoice = String($event ?? '')"
          />
        </label>
      </template>
    </div>
    <p v-if="!valid" role="alert">{{ $t('apfUi.multiple_filters_require_selection') }}</p>
    <p v-if="query.isPending.value" role="status">{{ $t('apfUi.reading_setup_usage') }}</p>
    <p v-if="query.error.value" role="alert">{{query.error.value.message}} <LibraryButton type="button" @click="query.refetch()">{{ $t('apfUi.retry') }}</LibraryButton></p>
  </fieldset>
</template>
