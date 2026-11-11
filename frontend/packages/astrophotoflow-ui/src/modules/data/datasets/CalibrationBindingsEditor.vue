<script setup lang="ts">
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ApiClientError } from '../../../core/api/errors'
import { uiT } from '../../../core/i18n'
import { useQueryAvailability } from '../../../core/query/availability'
import { workspaceQueryKey } from '../../../core/query/keys'
import { calibrationApi } from '../api/calibration'
import { datasetApi } from '../api'
import type { CalibrationBinding, CalibrationBindings, CalibrationTargetOption } from '../api/contracts'
import type { CalibrationPatch } from '../../../generated/api/types.gen'
import LibraryButton from '../components/LibraryButton.vue'
import CalibrationBindingSelect from '../library/CalibrationBindingSelect.vue'
import { invalidateLibraryData } from '../library/invalidation'
import { readPages } from '../library/pagination'
import { displayLabel } from '../library/presentation'

const props = defineProps<{ workspaceId: string; datasetId: string }>()
const emit = defineEmits<{ saving: [value: boolean] }>()
const opened = ref(false)
const changes = ref<CalibrationBindings>({})
const saving = ref(false)
const error = ref('')
const notice = ref('')
const ready = useQueryAvailability()
const cache = useQueryClient()
const slots = ['dark', 'flat', 'bias', 'dark_flat'] as const
const query = useQuery({
  queryKey: computed(() => [...workspaceQueryKey(props.workspaceId), 'datasets', props.datasetId, 'calibration']),
  enabled: computed(() => opened.value && ready.value),
  queryFn: async ({ signal }) => {
    const [configuration, targets] = await Promise.all([
      calibrationApi.dataset(props.datasetId, signal),
      readPages(offset => datasetApi.calibrationTargets({limit: 200, offset: offset ?? 0}, signal), true, signal)
    ])
    return { configuration, targets: targets.items }
  }
})
const canEdit = computed(() => ready.value && !!query.data.value)
const availableSlots = computed(() => slots.filter(slot => query.data.value?.configuration.slots[slot]?.status !== 'not_applicable'))
const targets = computed(() => {
  const items = [...(query.data.value?.targets ?? [])]
  for (const slot of slots) {
    const detail = query.data.value?.configuration.slots[slot]?.target_detail
    if (detail && !detail.in_trash && !items.some(item => item.target.id === detail.target.id))
      items.push({ ...detail, frame_type: slot, member_count: 1 } satisfies CalibrationTargetOption)
  }
  return items
})

function selection(slot: typeof slots[number]): CalibrationBinding {
  if (slot in changes.value) return changes.value[slot]
  const choice = query.data.value?.configuration.calibration[slot]
  if (choice?.mode === 'target') return choice.target
  if (choice?.mode === 'disabled') return null
  return undefined
}

let context = {}
watch(() => [props.workspaceId, props.datasetId], () => {
  context = {}
  changes.value = {}
  notice.value = ''
  error.value = ''
}, { flush: 'sync' })
let mounted = true
onBeforeUnmount(() => { mounted = false })

async function save() {
  const source = query.data.value
  if (!source || !canEdit.value || saving.value) return
  const { workspaceId, datasetId } = props
  const requestContext = context
  const patch: CalibrationPatch = {}
  for (const slot of slots) {
    if (!(slot in changes.value)) continue
    const value = changes.value[slot]
    patch[slot] = value === null ? {mode: 'disabled'} : value && 'kind' in value
      ? {mode: 'target', target: value} : {mode: 'unconfigured'}
  }
  const body = { request_id: crypto.randomUUID(), expected_revision: source.configuration.revision, changes: patch }
  const stillHere = () => mounted && context === requestContext && props.workspaceId === workspaceId && props.datasetId === datasetId
  saving.value = true
  emit('saving', true)
  error.value = ''
  notice.value = ''
  try {
    try {
      await calibrationApi.updateDataset(datasetId, body)
    } catch (cause) {
      if (!(cause instanceof ApiClientError) || cause.code !== 'CALIBRATION_UNKNOWN' || !stillHere()) throw cause
      const details = [...new Set(cause.fields?.map(field => field.message) ?? [cause.message])].join('\n')
      if (!window.confirm(uiT('apfUi.calibration_confirm_unknown', {details}))) throw cause
      await calibrationApi.updateDataset(datasetId, { ...body, accept_unknown: true })
    }
    if (stillHere()) {
      changes.value = {}
      notice.value = uiT('apfUi.dataset_calibration_saved')
    }
  } catch (cause) {
    if (stillHere()) error.value = cause instanceof Error ? cause.message : uiT('apfUi.could_not_save_calibration_bindings')
  } finally {
    try {
      await invalidateLibraryData(cache, workspaceId, { datasetIds: [datasetId] })
    } finally {
      saving.value = false
      emit('saving', false)
    }
  }
}
</script>

<template>
  <details class="apf-calibration-editor" @toggle="opened = ($event.target as HTMLDetailsElement).open">
    <summary>{{ $t('apfUi.dataset_calibration') }}</summary>
    <p v-if="error || query.error.value" role="alert">{{ error || query.error.value?.message }}</p>
    <template v-if="query.data.value">
      <ul v-if="query.data.value.configuration.diagnostics?.length" role="status">
        <li v-for="(item,index) in query.data.value.configuration.diagnostics" :key="index">{{ item.slot }} · {{ item.state }} · {{ item.diagnostics }}</li>
      </ul>
      <fieldset :disabled="!canEdit || saving || query.isFetching.value">
        <legend>{{ $t('apfUi.dataset_calibration') }}</legend>
        <label v-for="slot in availableSlots" :key="slot">
          {{ displayLabel(slot) }}
          <CalibrationBindingSelect :model-value="selection(slot)" :frame-type="slot" :targets="targets"
            :label="displayLabel(slot)" @update:model-value="changes[slot] = $event" />
        </label>
      </fieldset>
      <LibraryButton type="button" :disabled="!canEdit || saving || query.isFetching.value || !Object.keys(changes).length" @click="save">
        {{ $t('apfUi.save_calibration_bindings') }}
      </LibraryButton>
    </template>
    <p v-if="notice" role="status">{{ notice }}</p>
  </details>
</template>
