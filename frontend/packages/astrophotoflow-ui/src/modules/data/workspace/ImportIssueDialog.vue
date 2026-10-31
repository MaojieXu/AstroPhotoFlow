<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import { computed, ref, watch } from 'vue'
import { assetApi } from '../api/index'
import { importAcceptedSchema, taskSchema } from '../api/contracts'
import LibraryButton from './LibraryButton.vue'
import LibraryDialog from './LibraryDialog.vue'

const { issue }=defineProps<{issue?:{taskId:string;category:'content'|'preview'}}>()
const emit=defineEmits<{close:[];retried:[taskId:string]}>()
const task=ref<ReturnType<typeof taskSchema.parse>>()
const loading=ref(false)
const saving=ref(false)
const error=ref('')
let generation=0
const active=computed(()=>task.value&&['queued','running','cancelling','interrupted'].includes(task.value.status))
const failures=computed(()=>task.value?.items.filter(item=>issue?.category==='preview'
  ?['failed','unsupported'].includes(item.preview_status)
  :item.content_status==='failed'||item.metadata_status==='failed'||Boolean(item.error)&&!item.asset_id)??[])
const retryIds=computed(()=>failures.value.filter(item=>item.status!=='skipped'&&(item.content_status==='pending'||item.content_status==='failed'||item.metadata_status==='failed'||['pending','failed'].includes(item.preview_status))).map(item=>item.id))
async function load(){
  const current=++generation
  task.value=undefined;error.value=''
  if(!issue)return
  const id=issue.taskId
  loading.value=true
  try{
    const result=await assetApi.get('/astrophotoflow/api/v1/asset-tasks/'+id+'?items_limit=200&items_offset=0',taskSchema)
    const items=[...result.items]
    while(items.length<result.items_total){
      const page=await assetApi.get('/astrophotoflow/api/v1/asset-tasks/'+id+'?items_limit=200&items_offset='+items.length,taskSchema)
      items.push(...page.items)
      if(!page.items.length)break
    }
    if(current===generation)task.value={...result,items}
  }catch(cause){if(current===generation)error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_read_the_failure_reason')}
  finally{if(current===generation)loading.value=false}
}
async function retry(){
  if(!issue||saving.value||active.value||!retryIds.value.length)return
  saving.value=true;error.value=''
  try{
    const accepted=await assetApi.send('/astrophotoflow/api/v1/asset-tasks/'+issue.taskId+'/retry',importAcceptedSchema,'POST',{item_ids:retryIds.value})
    emit('retried',accepted.task_id);emit('close')
  }catch(cause){error.value=cause instanceof Error?cause.message:uiT('apfUi.retry_was_not_accepted_check_the_task_status')}
  finally{saving.value=false}
}
watch(()=>issue,()=>void load(),{immediate:true})
</script>

<template>
  <LibraryDialog :open="!!issue" :title="$t('apfUi.import_issue_details')" :busy="saving" @close="emit('close')">
    <div class="apf-equipment-dialog-body">
      <p v-if="loading" role="status">{{ $t('apfUi.reading_failure_reasons') }}</p>
      <p v-if="error" role="alert">{{error}} <LibraryButton @click="load">{{ $t('apfUi.read_again') }}</LibraryButton></p>
      <p v-if="task?.error" class="break-words">{{task.error.message??task.error.code}}</p>
      <p v-for="item in failures" :key="item.id" class="break-words">{{item.source_path}}：{{String(item.error?.message??item.error?.code??$t('apfUi.preview_is_not_supported_for_this_format_yet')).replace($t('apfUi.original_files_will_continue_to_be_ingested'),item.content_status==='available'?$t('apfUi.original_management_complete'):$t('apfUi.original_not_yet_managed'))}}</p>
      <p v-if="active">{{ $t('apfUi.background_processing_is_still_running_retry_failed_items_after_it_fin') }}<LibraryButton :disabled="loading" @click="load">{{ $t('apfUi.refresh_status') }}</LibraryButton></p>
      <p v-if="task&&!loading&&!failures.length&&!task.error">{{ $t('apfUi.no_failed_files_in_this_stage') }}</p>
    </div>
    <footer class="apf-equipment-dialog-footer"><LibraryButton :disabled="saving" @click="emit('close')">{{ $t('apfUi.close') }}</LibraryButton><LibraryButton v-if="retryIds.length" :disabled="active||saving||loading" @click="retry">{{saving?$t('apfUi.accepting'):$t('apfUi.retry_failed_items')}}</LibraryButton></footer>
  </LibraryDialog>
</template>
