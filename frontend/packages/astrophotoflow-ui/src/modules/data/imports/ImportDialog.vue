<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { catalogApi, importApi } from '../api'
import { readPages } from '../library/pagination'

import { validatedInput } from '../../../core/api/input'
import { uiT } from '../../../core/i18n'
import type { CameraSpecs, EquipmentApplication } from '../../../generated/api/types.gen'
import { zImportCreate } from '../../../generated/api/zod.gen'
import { ApiClientError } from '../api/client'
import type { LocalImportFile } from '../api/contracts'
import LibraryButton from '../components/LibraryButton.vue'
import LibraryCheckbox from '../components/LibraryCheckbox.vue'
import LibraryDialog from '../components/LibraryDialog.vue'
import LibraryInfo from '../components/LibraryInfo.vue'
import LibraryInput from '../components/LibraryInput.vue'
import LibrarySelect from '../components/LibrarySelect.vue'
import LibraryTextarea from '../components/LibraryTextarea.vue'
import EquipmentAssociationPicker from '../equipment/EquipmentAssociationPicker.vue'
import { displayLabel } from '../library/presentation'
import { useSubmitImport } from './mutations'

type CaptureInput = string | number | null | undefined
type Field = { key: string; title: string; minimum?: number; integer?: boolean }

const props = defineProps<{
  workspaceId: string
  open: boolean
  files: LocalImportFile[]
  createDataset?: boolean
  datasetName?: string
  projectId?: string
  projectRevision?: number
  projectName?: string
}>()
const emit = defineEmits<{ close: []; submitted: [taskId: string] }>()

const submission = useSubmitImport()
const submitting = submission.isPending
let inFlight = false
let dialogSession = {}
onBeforeUnmount(() => { dialogSession = {} })

const error = ref('')
const pendingRequestId = ref<string>()
const datasetName = ref(props.datasetName ?? '')
const notes = ref('')
const mode = ref<'standalone' | 'new_dataset' | 'append_dataset'>('standalone')
const appendDatasetId = ref('')
const destinationQuery = useQuery({
  queryKey: computed(() => ['import-destinations', props.workspaceId]),
  enabled: computed(() => props.open),
  queryFn: ({signal}) => readPages(offset => catalogApi.datasets({limit:200, offset:offset ?? 0, status:'active'}, signal), true, signal)
})
const appendTarget = computed(() => destinationQuery.data.value?.items.find(item => item.id === appendDatasetId.value))
const calibrationStatus = ref<'UnCalibrated' | 'Calibrated' | 'Unknown'>('Unknown')
const calibrationReason = ref('')
const calibrationOptions = computed(() => ['Unknown', 'UnCalibrated', 'Calibrated'].map(value => ({ value, name: displayLabel(value) })))
const equipmentApplication = ref<EquipmentApplication>()
const equipmentValid = ref(true)
const equipmentSession = ref(0)
const cameraMode = ref<CameraSpecs['default_parameter_mode']>()
const manualClassification = ref(false)
const frameClass = ref('')
const frameType = ref('')
const captureValues = ref<Record<string, CaptureInput>>({})
const binning = ref<CaptureInput>('')

const isDataset = computed(() => mode.value !== 'standalone')
const selectedSize = computed(() => {
  const mib = props.files.reduce((sum, file) => sum + file.size, 0) / 1024 / 1024
  return mib >= 1024 ? (mib / 1024).toFixed(2) + ' GiB' : mib.toFixed(1) + ' MiB'
})
const selectedPaths = computed(() => props.files.map(file =>
  file.root_id ? file.root_id + ':/' + file.path : file.path).join('\n'))
const activeFrameClass = computed(() => manualClassification.value ? frameClass.value : '')
const captureFields = computed<Field[]>(() => {
  const fields: Field[] = []
  if (cameraMode.value === 'iso') fields.push({ key: 'iso', title: 'ISO', minimum: 1, integer: true })
  if (cameraMode.value === 'gain') fields.push({ key: 'gain', title: 'Gain' }, { key: 'offset', title: 'Offset' })
  if (activeFrameClass.value !== 'video') {
    fields.push({ key: 'exposure_seconds', title: uiT('apfUi.exposure_per_frame_seconds'), minimum: 0 })
  }
  if (activeFrameClass.value === 'masterframe') {
    fields.push({ key: 'integration_seconds', title: uiT('apfUi.total_exposure_seconds'), minimum: 0 })
  }
  fields.push({ key: 'sensor_temperature_c', title: uiT('apfUi.measured_sensor_temperature_c') })
  return fields
})

const frameClassOptions = computed(() => [
  { value: '', name: uiT('apfUi.not_specified') },
  ...['subframe', 'masterframe', 'video'].map(value => ({ value, name: displayLabel(value) }))
])
const frameTypeOptions = computed(() => [
  { value: '', name: uiT('apfUi.not_specified') },
  ...['light', 'bias', 'dark', 'flat', 'dark_flat'].map(value => ({ value, name: displayLabel(value) }))
])
const binOptions = computed(() => [
  { value: '', name: uiT('apfUi.not_specified') },
  ...Array.from({ length: 16 }, (_, index) => ({ value: String(index + 1), name: 'Bin' + (index + 1) }))
])

function buildParameters() {
  const parameters: Record<string, number> = {}
  for (const { key } of captureFields.value) {
    const value = captureValues.value[key]
    if (value != null && value !== '' && Number.isFinite(Number(value))) {
      parameters[key] = Number(value)
    }
  }
  if (binning.value) {
    parameters.binning_x = parameters.binning_y = Number(binning.value)
  }
  return parameters
}

async function submitImport() {
  if (!props.files.length || inFlight || !equipmentValid.value) return
  if (mode.value === 'append_dataset' && !appendTarget.value) { error.value = uiT('apfUi.choose_destination_dataset'); return }
  const currentSession = dialogSession
  const workspaceId = props.workspaceId
  inFlight = true
  error.value = ''
  try {
    if (pendingRequestId.value) {
      const task = await importApi.request(pendingRequestId.value)
      if (currentSession === dialogSession) emit('submitted', task.id)
      return
    }
    const requestId = crypto.randomUUID()
    const body = validatedInput(zImportCreate, {
        request_id: requestId,
        sources: props.files.map(file => ({ ...(file.root_id ? { root_id: file.root_id } : {}), path: file.path })),
        storage_mode: 'managed',
        mode: mode.value,
        ...(mode.value === 'append_dataset' ? {target_dataset_id:appendTarget.value?.id,dataset_base_revision:appendTarget.value?.revision} : {}),
        ...(props.projectId ? {project_id:props.projectId,project_base_revision:props.projectRevision} : {}),
        calibration_status: calibrationStatus.value,
        calibration_reason: calibrationReason.value || null,
        ...(manualClassification.value ? {
          classification: {
            frame_class: frameClass.value || null,
            frame_type: frameClass.value === 'video' ? null : frameType.value || null
          }
        } : {}),
        parameters: buildParameters(),
        ...(equipmentApplication.value ? { equipment: equipmentApplication.value } : {}),
        notes: notes.value || null,
        dataset_name: isDataset.value ? datasetName.value || props.datasetName || null : null
      })
    pendingRequestId.value = requestId
    const accepted = await submission.mutateAsync({workspaceId,body})
    if (currentSession === dialogSession) emit('submitted', accepted.task_id)
  } catch (cause) {
    if (currentSession === dialogSession) {
      if (cause instanceof ApiClientError && cause.kind === 'service' && cause.code !== 'RESOURCE_NOT_FOUND') pendingRequestId.value = undefined
      error.value = [cause instanceof Error ? cause.message : uiT('apfUi.request_failed'), pendingRequestId.value ? uiT('apfUi.pending_operation_query',{id:pendingRequestId.value}) : ''].filter(Boolean).join('\n')
    }
  } finally {
    inFlight = false
  }
}

watch([() => props.workspaceId, () => props.open, () => props.files], () => {
  dialogSession = {}
  if (!props.open) return
  error.value = ''
  pendingRequestId.value = undefined
  datasetName.value = props.datasetName ?? ''
  notes.value = ''
  mode.value = props.createDataset ? 'new_dataset' : 'standalone'
  appendDatasetId.value = ''
  calibrationStatus.value = 'Unknown'
  calibrationReason.value = ''
  manualClassification.value = false
  frameClass.value = ''
  frameType.value = ''
  captureValues.value = {}
  binning.value = ''
  cameraMode.value = undefined
  equipmentApplication.value = undefined
  equipmentValid.value = true
  equipmentSession.value++
})
</script>

<template>
  <LibraryDialog
    :open="open"
    :title="$t('apfUi.confirm_asset_details')"
    :label="$t('apfUi.import_astronomy_assets')"
    :busy="submitting"
    @close="emit('close')"
  >
    <form class="apf-editor" data-testid="asset-import-confirmation" @submit.prevent="submitImport">
      <div class="apf-equipment-dialog-body">
        <div class="apf-device-form flex flex-col">
          <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
            <strong class="text-base-foreground">{{ $t('apfUi.selected_files_value', { p0: files.length }) }}</strong>
            <LibraryInfo :label="$t('apfUi.selected_files')" :text="selectedPaths" />
            <span aria-hidden="true">·</span>
            <span>{{ selectedSize }}</span>
            <span aria-hidden="true">·</span>
            <span>{{ $t('apfUi.import_managed_copy_summary') }}</span>
          </div>

          <section class="apf-device-grid">
            <label class="apf-device-field">
              <span>{{ $t('apfUi.calibration_status') }}</span>
              <LibrarySelect v-model="calibrationStatus" :label="$t('apfUi.calibration_status')" :options="calibrationOptions" :searchable="false" :disabled="submitting" />
            </label>
            <label class="apf-device-field">
              <span>{{ $t('apfUi.calibration_reason') }}</span>
              <LibraryInput v-model="calibrationReason" :label="$t('apfUi.calibration_reason')" :disabled="submitting" />
            </label>
          </section>

          <EquipmentAssociationPicker
            :key="equipmentSession"
            v-model="equipmentApplication"
            v-model:camera-mode="cameraMode"
            :workspace-id="workspaceId"
            :disabled="submitting"
            @valid="equipmentValid = $event"
          />

          <section class="apf-device-section">
            <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
              <div class="flex min-w-0 items-center gap-1">
                <label class="apf-import-classification-control text-xs">
                  <LibraryCheckbox
                    v-model="manualClassification"
                    class="apf-import-classification-checkbox"
                    :label="$t('apfUi.set_classification_for_the_whole_batch')"
                    :disabled="submitting"
                  />
                  <span>{{ $t('apfUi.set_classification_for_the_whole_batch') }}</span>
                </label>
                <LibraryInfo
                  :label="$t('apfUi.batch_classification')"
                  :text="$t('apfUi.classify_each_file_using_its_capture_metadata_by_default_retain_unknow')"
                />
              </div>
              <span v-if="!manualClassification" class="text-xs text-muted-foreground">
                {{ $t('apfUi.read_capture_metadata_from_each_file') }}
              </span>
            </div>

            <div v-if="manualClassification" class="apf-device-grid">
              <label class="apf-device-field">
                <span>{{ $t('apfUi.asset_form') }}</span>
                <LibrarySelect
                  :model-value="frameClass"
                  :label="$t('apfUi.asset_form')"
                  :options="frameClassOptions"
                  density="compact"
                  :searchable="false"
                  @update:model-value="frameClass = String($event ?? '')"
                />
              </label>
              <label v-if="frameClass && frameClass !== 'video'" class="apf-device-field">
                <span>{{ $t('apfUi.frame_use') }}</span>
                <LibrarySelect
                  :model-value="frameType"
                  :label="$t('apfUi.frame_use')"
                  :options="frameTypeOptions"
                  density="compact"
                  :searchable="false"
                  @update:model-value="frameType = String($event ?? '')"
                />
              </label>
            </div>

            <div class="apf-device-grid">
              <label v-for="field in captureFields" :key="field.key" class="apf-device-field">
                <span>{{ field.title }}</span>
                <LibraryInput
                  v-model="captureValues[field.key]"
                  :aria-label="field.title"
                  type="number"
                  :min="field.minimum"
                  :step="field.integer ? 1 : 'any'"
                />
              </label>
              <label class="apf-device-field">
                <span>Bin</span>
                <LibrarySelect v-model="binning" label="Bin" :options="binOptions" density="compact" :searchable="false" />
              </label>
            </div>
          </section>

          <section class="apf-device-section">
            <p v-if="projectId">{{ $t('apfUi.import_target_project', {name:projectName || projectId}) }}</p>
            <label>{{ $t('apfUi.import_mode') }}
              <select v-model="mode" :disabled="submitting">
                <option value="standalone">{{ $t('apfUi.import_standalone') }}</option>
                <option value="new_dataset">{{ $t('apfUi.import_new_dataset') }}</option>
                <option value="append_dataset">{{ $t('apfUi.import_append_dataset') }}</option>
              </select>
            </label>
            <label v-if="mode === 'append_dataset'">{{ $t('apfUi.image_group_name') }}
              <select v-model="appendDatasetId" :disabled="submitting || destinationQuery.isFetching.value">
                <option value="">{{ $t('apfUi.not_specified') }}</option>
                <option v-for="item in destinationQuery.data.value?.items" :key="item.id" :value="item.id">{{ item.name }}</option>
              </select>
              <span v-if="destinationQuery.error.value" role="alert">{{ destinationQuery.error.value.message }}</span>
            </label>
            <label v-if="mode === 'new_dataset'" class="apf-device-field">
              <span>{{ $t('apfUi.image_group_name_optional') }}</span>
              <LibraryInput
                id="import-dataset-name"
                v-model="datasetName"
                :aria-label="$t('apfUi.image_group_name_optional')"
                :placeholder="$t('apfUi.leave_blank_to_use_the_source_name')"
              />
            </label>
            <p v-if="isDataset">{{ $t('apfUi.import_subframes_only') }}</p>
            <label class="apf-device-field">
              <span class="flex items-center gap-1">
                {{ isDataset ? $t('apfUi.image_group_notes_optional') : $t('apfUi.asset_notes_optional') }}
                <LibraryInfo
                  v-if="isDataset"
                  :label="$t('apfUi.notes')"
                  :text="$t('apfUi.notes_for_a_multiple_file_import_are_saved_on_the_image_group_members_')"
                />
              </span>
              <LibraryTextarea v-model="notes" rows="2" />
            </label>
          </section>
          <p v-if="error" class="apf-error" role="alert">{{ error }}</p>
        </div>
      </div>
      <footer class="apf-equipment-dialog-footer">
        <LibraryButton type="button" :disabled="submitting" @click="emit('close')">{{ $t('apfUi.cancel') }}</LibraryButton>
        <LibraryButton type="submit" variant="primary" :disabled="submitting || !equipmentValid">
          {{ submitting ? $t('apfUi.creating_batch') : $t('apfUi.start_import') }}
        </LibraryButton>
      </footer>
    </form>
  </LibraryDialog>
</template>

<style scoped>
.apf-import-classification-control {
  display: inline-flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  min-width: 0;
  min-height: 24px;
  cursor: pointer;
}

.apf-import-classification-checkbox {
  flex: none;
  width: 16px;
  height: 16px;
  min-width: 16px;
  min-height: 16px;
  margin: 0;
  padding: 0;
}
</style>
