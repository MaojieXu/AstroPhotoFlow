<script setup lang="ts">
import ImportOrganizationRecovery from './ImportOrganizationRecovery.vue'
import { uiT } from '../../../core/i18n'
import { computed, watch } from 'vue'
import { useImportIssueReport } from './queries'
import { useRetryImport } from './mutations'
import LibraryButton from '../components/LibraryButton.vue'
import LibraryDialog from '../components/LibraryDialog.vue'

const props=defineProps<{workspaceId:string;issue?:{taskId:string;category:'content'|'preview'}}>()
const emit=defineEmits<{close:[];retried:[taskId:string]}>()
const report=useImportIssueReport(()=>props.issue?{workspaceId:props.workspaceId,taskId:props.issue.taskId}:undefined)
const retryMutation=useRetryImport()
const task=computed(()=>report.data.value?.task)
const publicationError=computed(()=>task.value?.report.dataset_publish_error)
const loading=report.isFetching
const saving=retryMutation.isPending
const error=computed(()=>retryMutation.error.value instanceof Error?retryMutation.error.value.message:
  retryMutation.isError.value?uiT('apfUi.retry_was_not_accepted_check_the_task_status'):
  report.error.value instanceof Error?report.error.value.message:report.isError.value?uiT('apfUi.could_not_read_the_failure_reason'):'')
const active=computed(()=>task.value&&['queued','running','cancelling','interrupted'].includes(task.value.status))
const failures=computed(()=>report.data.value?.items.filter(item=>props.issue?.category==='preview'
  ?['failed','unsupported'].includes(item.preview_status)
  :item.content_status==='failed'||item.metadata_status==='failed'||Boolean(item.error)&&!item.asset_id)??[])
const retryIds=computed(()=>failures.value.filter(item=>item.status!=='skipped'&&(item.content_status==='pending'||item.content_status==='failed'||item.metadata_status==='failed'||['pending','failed'].includes(item.preview_status))).map(item=>item.id))
function load(){return report.refetch({cancelRefetch:false})}
watch(()=>[props.workspaceId,props.issue?.taskId,props.issue?.category] as const,()=>retryMutation.reset(),{flush:'sync'})
async function retry(){
  const target=props.issue
  if(!target||saving.value||loading.value||report.isError.value||active.value||!retryIds.value.length)return
  const workspaceId=props.workspaceId, taskId=target.taskId, category=target.category
  try {
    const accepted=await retryMutation.mutateAsync({workspaceId,taskId,body:{item_ids:[...retryIds.value]}})
    if(props.workspaceId!==workspaceId||props.issue?.taskId!==taskId||props.issue.category!==category)return
    emit('retried',accepted.task_id);emit('close')
  }catch{/* The mutation error is displayed; uncertain acceptance is re-read, not replayed. */}
}
</script>

<template>
  <LibraryDialog :open="!!props.issue" :title="$t('apfUi.import_issue_details')" :busy="saving" @close="emit('close')">
    <div class="apf-equipment-dialog-body">
      <p v-if="loading" role="status">{{ $t('apfUi.reading_failure_reasons') }}</p>
      <p v-if="error" role="alert">{{error}} <LibraryButton @click="load">{{ $t('apfUi.read_again') }}</LibraryButton></p>
      <p v-if="task?.error" class="break-words">{{task.error.message??task.error.code}}</p>
      <section v-if="publicationError" class="space-y-1 break-words" role="alert">
        <p>{{ $t('apfUi.dataset_publication_failed') }} · {{ publicationError.message ?? publicationError.code }}</p>
        <ul><li v-for="field in publicationError.fields" :key="field.path">{{ field.path }} · {{ field.message }}</li></ul>
      </section>
      <p v-for="item in failures" :key="item.id" class="break-words">{{item.source_path}}：{{String(item.error?.message??item.error?.code??$t('apfUi.preview_is_not_supported_for_this_format_yet')).replace($t('apfUi.original_files_will_continue_to_be_ingested'),item.content_status==='available'?$t('apfUi.original_management_complete'):$t('apfUi.original_not_yet_managed'))}}</p>
      <ImportOrganizationRecovery v-if="task && !active && report.data.value" :key="workspaceId + ':' + task.id"
        :workspace-id="workspaceId" :task="task" :items="report.data.value.items" @changed="load" />
      <p v-if="active">{{ $t('apfUi.background_processing_is_still_running_retry_failed_items_after_it_fin') }}<LibraryButton :disabled="loading" @click="load">{{ $t('apfUi.refresh_status') }}</LibraryButton></p>
      <p v-if="task&&!loading&&!failures.length&&!task.error&&!publicationError">{{ $t('apfUi.no_failed_files_in_this_stage') }}</p>
    </div>
    <footer class="apf-equipment-dialog-footer"><LibraryButton :disabled="saving" @click="emit('close')">{{ $t('apfUi.close') }}</LibraryButton><LibraryButton v-if="retryIds.length" :disabled="active||saving||loading||report.isError.value" @click="retry">{{saving?$t('apfUi.accepting'):$t('apfUi.retry_failed_items')}}</LibraryButton></footer>
  </LibraryDialog>
</template>
