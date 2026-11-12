<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { ApiClientError } from '../../../core/api/errors'
import { uiT } from '../../../core/i18n'
import { workspaceQueryKey } from '../../../core/query/keys'
import type { AssetTaskOut, ImportRecovery, TaskItemOut } from '../../../generated/api/types.gen'
import { zImportProjectLink, zCaptureDiagnostics } from '../../../generated/api/zod.gen'
import { catalogApi, datasetApi, importApi } from '../api'
import { readPages } from '../library/pagination'

const props = defineProps<{workspaceId:string; task:Omit<AssetTaskOut, 'items'>; items:TaskItemOut[]}>()
const emit = defineEmits<{changed:[]}>()
const cache = useQueryClient()
const opened = ref(false)
const mode = ref<ImportRecovery['mode']>('new_dataset')
const name = ref('')
const datasetId = ref('')
const projectId = ref('')
const selected = ref<string[]>([])
const saving = ref(false)
const error = ref('')
const notice = ref('')
const pending = ref<{signature:string; body:ImportRecovery}>()
const available = computed(() => props.items.filter(item => item.asset_id && item.content_status === 'available'))
const choices = useQuery({
  queryKey: computed(() => [...workspaceQueryKey(props.workspaceId), 'import-recovery-destinations']),
  enabled: opened,
  queryFn: async ({signal}) => {
    const [datasets, projects] = await Promise.all([
      readPages(offset => catalogApi.datasets({limit:200,offset:offset ?? 0,status:'active'},signal),true,signal),
      readPages(offset => catalogApi.projects({limit:200,offset:offset ?? 0,status:'active'},signal),true,signal)
    ])
    return {datasets:datasets.items,projects:projects.items}
  }
})
watch(() => [props.workspaceId,props.task.id], () => {
  selected.value = []; pending.value = undefined; error.value = ''; notice.value = ''
  projectId.value = props.task.report.destination?.project_id ?? ''
}, {immediate:true,flush:'sync'})
async function save() {
  if (saving.value) return
  const taskId = props.task.id, workspaceId = props.workspaceId
  const dataset = choices.data.value?.datasets.find(item => item.id === datasetId.value)
  const project = choices.data.value?.projects.find(item => item.id === projectId.value)
  if (mode.value === 'new_dataset' && (!name.value.trim() || !selected.value.length)) return
  if (mode.value === 'append_dataset' && (!dataset || !selected.value.length)) return
  if (mode.value === 'link_project' && !project) return
  const body:ImportRecovery = {request_id:crypto.randomUUID(),mode:mode.value,
    asset_ids:mode.value === 'link_project' ? [] : [...selected.value],
    ...(mode.value === 'new_dataset' ? {name:name.value.trim()} : {}),
    ...(mode.value === 'append_dataset' && dataset ? {dataset_id:dataset.id,expected_revision:dataset.revision} : {}),
    ...(project ? {project_id:project.id,project_base_revision:project.revision} : {})}
  const signature = JSON.stringify([workspaceId,taskId,{...body,request_id:undefined}])
  saving.value = true; error.value = ''; notice.value = ''
  try {
    let receipt
    if (pending.value?.signature === signature) receipt = await datasetApi.operation(pending.value.body.request_id)
    else {
      pending.value = {signature,body}
      try { receipt = await importApi.recoverOrganization(taskId,body) }
      catch (cause) {
        if (cause instanceof ApiClientError && cause.code === 'CALIBRATION_UNKNOWN' && window.confirm(uiT('apfUi.calibration_confirm_unknown',{details:cause.fields?.map(field => field.message).join('\n') ?? cause.message}))) {
          body.accept_unknown = true
          receipt = await importApi.recoverOrganization(taskId,body)
        } else {
          if (cause instanceof ApiClientError && cause.kind === 'service') pending.value = undefined
          throw cause
        }
      }
    }
    if (props.task.id === taskId && props.workspaceId === workspaceId) {
      const link = zImportProjectLink.safeParse(receipt.result.project_link)
      const diagnostics = zCaptureDiagnostics.safeParse(receipt.result.capture_diagnostics)
      notice.value = [uiT('apfUi.import_organization_saved'),
        link.success && link.data.state === 'failed' ? uiT('apfUi.import_project_link_failed') + ' ' + (link.data.message ?? '') : '',
        diagnostics.success && diagnostics.data.warnings?.length ? uiT('apfUi.capture_differences_warning') : ''].filter(Boolean).join('\n')
      pending.value = undefined; selected.value = []; emit('changed')
    }
  } catch (cause) {
    if (props.task.id === taskId && props.workspaceId === workspaceId)
      error.value = [cause instanceof Error ? cause.message : uiT('apfUi.request_failed'), ...(cause instanceof ApiClientError ? cause.fields?.map(field => field.message) ?? [] : []), pending.value ? uiT('apfUi.pending_operation_query', {id:pending.value.body.request_id}) : ''].filter(Boolean).join('\n')
  } finally {
    await cache.invalidateQueries({queryKey:workspaceQueryKey(workspaceId)})
    saving.value = false
  }
}
</script>

<template>
  <details @toggle="opened = ($event.target as HTMLDetailsElement).open">
    <summary>{{ $t('apfUi.repair_import_organization') }}</summary>
    <p v-if="task.report.destination?.project_link.state === 'failed'" role="alert">{{ $t('apfUi.import_project_link_failed') }} {{ task.report.destination.project_link.message }}</p>
    <p v-if="error || choices.error.value" class="whitespace-pre-wrap" role="alert">{{ error || choices.error.value?.message }}</p>
    <p v-if="notice" class="whitespace-pre-wrap" role="status">{{ notice }}</p>
    <fieldset :disabled="saving || choices.isFetching.value">
      <label>{{ $t('apfUi.import_mode') }}<select v-model="mode">
        <option value="new_dataset">{{ $t('apfUi.import_new_dataset') }}</option>
        <option value="append_dataset">{{ $t('apfUi.import_append_dataset') }}</option>
        <option value="link_project">{{ $t('apfUi.relink_project') }}</option>
      </select></label>
      <label v-if="mode === 'new_dataset'">{{ $t('apfUi.image_group_name') }}<input v-model="name" /></label>
      <label v-if="mode === 'append_dataset'">{{ $t('apfUi.image_group_name') }}<select v-model="datasetId">
        <option value="">{{ $t('apfUi.not_specified') }}</option>
        <option v-for="item in choices.data.value?.datasets" :key="item.id" :value="item.id">{{ item.name }}</option>
      </select></label>
      <label>{{ $t('apfUi.project') }}<select v-model="projectId">
        <option value="">{{ $t('apfUi.not_specified') }}</option>
        <option v-for="item in choices.data.value?.projects" :key="item.id" :value="item.id">{{ item.name }}</option>
      </select></label>
      <ul><li v-for="item in available" :key="item.id">
        <label><input v-if="mode !== 'link_project' && item.asset_id" v-model="selected" type="checkbox" :value="item.asset_id" :disabled="!!item.dataset_id" />
          {{ item.source_path }} <span v-if="item.dataset_id">{{ $t('apfUi.material_dataset_owner',{name:item.dataset_name || item.dataset_id}) }}</span>
        </label>
      </li></ul>
      <button type="button" @click="save">{{ $t(pending ? 'apfUi.query_creation_receipt' : 'apfUi.save') }}</button>
    </fieldset>
  </details>
</template>
