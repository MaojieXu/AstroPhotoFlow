<script setup lang="ts">
import { skipToken, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ApiClientError } from '../../../core/api/errors'
import { uiT } from '../../../core/i18n'
import { useQueryAvailability } from '../../../core/query/availability'
import { workspaceQueryKey } from '../../../core/query/keys'
import { catalogApi, datasetApi } from '../api'
import { invalidateLibraryData } from '../library/invalidation'
import type { ImageDatasetCreate } from '../../../generated/api/types.gen'

const props = defineProps<{ workspaceId: string; datasetId?: string; projectId?: string; projectRevision?: number }>()
const emit = defineEmits<{ saving: [value: boolean] }>()
const creating = computed(() => !props.datasetId)
const name = ref('')
const pendingCreate = ref<{signature:string; body:ImageDatasetCreate}>()
const open = ref(false)
const search = ref('')
const term = ref('')
const offset = ref(0)
const chosen = ref<string[]>([])
const saving = ref(false)
const error = ref('')
const notice = ref('')
const limit = 25
const cache = useQueryClient()
const ready = useQueryAvailability()
const candidates = useQuery({
  queryKey: computed(() => [...workspaceQueryKey(props.workspaceId), 'library-selection', 'subframes', term.value, offset.value]),
  enabled: computed(() => ready.value && open.value),
  queryFn: ({ signal }) => catalogApi.assets({frame_class: 'subframe', q: term.value || undefined, limit, offset: offset.value}, signal)
})
const target = useQuery({
  queryKey: computed(() => [...workspaceQueryKey(props.workspaceId), 'datasets', props.datasetId, 'append-target']),
  enabled: computed(() => ready.value && open.value && !!props.datasetId),
  queryFn: computed(() => {
    const id = props.datasetId
    return id ? ({ signal }: {signal:AbortSignal}) => datasetApi.get(id, signal) : skipToken
  })
})
watch(() => target.data.value?.revision, () => { chosen.value = [] })
let context = {}
let mounted = true
onBeforeUnmount(() => { mounted = false })
watch(() => [props.workspaceId, props.datasetId, props.projectId], () => {
  context = {}
  chosen.value = []
  pendingCreate.value = undefined
  error.value = ''
  notice.value = ''
}, { flush: 'sync' })

function applySearch() {
  term.value = search.value.trim()
  offset.value = 0
}

async function append() {
  const dataset = target.data.value
  if (!ready.value || saving.value || !chosen.value.length || (creating.value ? !name.value.trim() : !dataset || target.isFetching.value)) return
  const {workspaceId, datasetId, projectId, projectRevision} = props
  const add = chosen.value.map(asset_id => ({asset_id}))
  saving.value = true
  emit('saving', true)
  error.value = ''
  notice.value = ''
  const requestContext = context
  const sameTarget = () => mounted && context === requestContext && props.workspaceId === workspaceId && props.datasetId === datasetId
  try {
    let receipt
    if (!datasetId) {
      const signature = JSON.stringify([workspaceId, projectId, name.value.trim(), chosen.value])
      const pending = pendingCreate.value
      if (pending?.signature === signature) {
        receipt = await datasetApi.operation(pending.body.request_id)
      } else {
        const body: ImageDatasetCreate = {request_id: crypto.randomUUID(), name: name.value.trim(), members: add,
          ...(projectId ? {project_id: projectId, project_base_revision: projectRevision} : {})}
        pendingCreate.value = {signature, body}
        try { receipt = await datasetApi.createFromMembers(body) }
        catch (cause) {
          if (!(cause instanceof ApiClientError) || cause.kind === 'service') pendingCreate.value = undefined
          throw cause
        }
      }
      if (sameTarget()) {
        notice.value = uiT('apfUi.dataset_created_from_subframes', {id: receipt.result.dataset_id})
        chosen.value = []
        pendingCreate.value = undefined
      }
      return
    }
    if (!dataset) return
    const body = {request_id: crypto.randomUUID(), expected_revision: dataset.revision, add}
    try {
      receipt = await datasetApi.editMembers(datasetId, body)
    } catch (cause) {
      if (!(cause instanceof ApiClientError) || cause.code !== 'CALIBRATION_UNKNOWN' || !sameTarget()) throw cause
      const details = [...new Set(cause.fields?.map(field => field.message) ?? [cause.message])].join('\n')
      if (!window.confirm(uiT('apfUi.calibration_confirm_unknown', {details}))) throw cause
      receipt = await datasetApi.editMembers(datasetId, { ...body, accept_unknown: true })
    }
    if (sameTarget()) {
      chosen.value = []
      notice.value = uiT('apfUi.dataset_subframes_added', { count: receipt.result.member_count })
    }
  } catch (cause) {
    if (sameTarget()) error.value = [cause instanceof Error ? cause.message : uiT('apfUi.request_failed'), ...(cause instanceof ApiClientError ? cause.fields?.map(field => field.path + ' ' + field.message) ?? [] : []), pendingCreate.value ? uiT('apfUi.dataset_creation_query', {id:pendingCreate.value.body.request_id}) : ''].filter(Boolean).join('\n')
  } finally {
    try {
      await invalidateLibraryData(cache, workspaceId, { datasetIds: datasetId ? [datasetId] : [] })
      if (!datasetId) await cache.invalidateQueries({queryKey:workspaceQueryKey(workspaceId)})
    } finally {
      saving.value = false
      emit('saving', false)
    }
  }
}
</script>

<template>
  <details @toggle="open = ($event.target as HTMLDetailsElement).open">
    <summary>{{ $t(creating ? 'apfUi.create_dataset_from_subframes' : 'apfUi.append_subframes') }}</summary>
    <label v-if="creating">{{ $t('apfUi.image_group_name') }}<input v-model="name" :aria-label="$t('apfUi.image_group_name')" :disabled="saving" /></label>
    <form @submit.prevent="applySearch">
      <input v-model="search" :aria-label="$t('apfUi.search')" :disabled="saving" />
      <button type="submit" :disabled="saving">{{ $t('apfUi.search') }}</button>
    </form>
    <p v-if="error || candidates.error.value || target.error.value" class="whitespace-pre-wrap" role="alert">{{ error || candidates.error.value?.message || target.error.value?.message }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <ul>
      <li v-for="item in candidates.data.value?.items" :key="item.id">
        <label>
          <input v-model="chosen" type="checkbox" :value="item.id" :disabled="saving || !ready || !!item.dataset_id" />
          {{ item.name }} <span v-if="item.dataset_id">{{ $t('apfUi.material_dataset_owner', {name:item.dataset_name || item.dataset_id}) }}</span>
        </label>
      </li>
    </ul>
    <button type="button" :disabled="offset === 0 || saving" @click="offset -= limit">{{ $t('apfUi.previous_page') }}</button>
    <button type="button" :disabled="offset + limit >= (candidates.data.value?.total ?? 0) || saving" @click="offset += limit">{{ $t('apfUi.next_page') }}</button>
    <button type="button" :disabled="saving || !ready || !chosen.length || (creating ? !name.trim() : !target.data.value || target.isFetching.value)" @click="append">{{ $t(creating ? (pendingCreate ? 'apfUi.query_creation_receipt' : 'apfUi.create_dataset_from_subframes') : 'apfUi.append_subframes') }} ({{ chosen.length }})</button>
  </details>
</template>
