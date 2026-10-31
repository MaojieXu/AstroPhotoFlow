<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ApiClientError } from '../api/client'
import { assetApi } from '../api/index'
import { pageSchema, taskActionSchema, taskSchema } from '../api/contracts'
import LibraryButton from './LibraryButton.vue'
import type { ImportNotice } from './libraryControls'

const { refreshToken, watchTaskIds = [], workspace = window.location.origin } = defineProps<{
  refreshToken:number; watchTaskIds?:string[]; workspace?:string
}>()
const emit=defineEmits<{completed:[taskId:string];registered:[taskId:string];succeeded:[message:string];notice:[notice:ImportNotice]}>()
type Task=ReturnType<typeof taskSchema.parse>
const tasks=ref<Task[]>([])
const error=ref('')
const busyTaskId=ref<string>()
const observed=new Set<string>()
const completed=new Set<string>()
const updates=new Map<string,string>()
const activeStatuses=['queued','running','cancelling','interrupted']
const activeTasks=computed(()=>tasks.value.filter(task=>activeStatuses.includes(task.status)))
let timer:ReturnType<typeof setInterval>|undefined
function taskName(task:Task){return task.dataset_name||uiT('apfUi.asset_import')}
function noticeKey(task:Task,category:string){return 'astrophotoflow:'+workspace+':import:'+task.id+':'+category+':notified'}
function notify(task:Task,category:'content'|'preview',kind:ImportNotice['kind'],title:string,description:string){
  if(!workspace)return
  const key=noticeKey(task,category)
  if(localStorage.getItem(key)==='1')return
  localStorage.setItem(key,'1')
  emit('notice',{taskId:task.id,category,kind,title:taskName(task)+'：'+title,description})
}
function notifyResults(task:Task){
  if(!observed.has(task.id)&&!watchTaskIds.includes(task.id))return
  const {content,preview}=task.report
  if(content?.completed){
    const description=uiT('apfUi.originals_ready_value_failed_value_skipped_value', { p0: (content.succeeded), p1: (content.failed), p2: (content.skipped) })
    const kind=content.failed?(content.succeeded?'warning':'error'):content.metadata_failed?'warning':'success'
    const title=content.failed?(content.succeeded?uiT('apfUi.some_files_failed_to_import'):uiT('apfUi.import_failed')):content.metadata_failed?uiT('apfUi.original_managed_some_metadata_could_not_be_parsed'):content.succeeded?uiT('apfUi.original_management_complete_a515e9'):uiT('apfUi.no_new_originals')
    notify(task,'content',kind,title,description+(content.metadata_failed?uiT('apfUi.metadata_issues_value', { p0: (content.metadata_failed) }):''))
  }else if(!content&&!activeStatuses.includes(task.status)&&workspace){
    const key=noticeKey(task,'content')
    if(task.status==='completed'){
      if(localStorage.getItem(key)!=='1'){localStorage.setItem(key,'1');emit('succeeded',taskName(task)+uiT('apfUi.import_complete'))}
    }else if(task.status==='failed'||task.status==='completed_with_errors'){
      notify(task,'content',task.status==='failed'?'error':'warning',task.status==='failed'?uiT('apfUi.import_failed'):uiT('apfUi.some_files_had_processing_issues'),String(task.error?.message??uiT('apfUi.view_the_failure_reason_for_each_file')))
    }
  }
  if(task.error&&['failed','completed_with_errors'].includes(task.status)){
    const category=content?.completed?'preview':'content'
    notify(task,category,content?.succeeded?'warning':'error',content?.succeeded?uiT('apfUi.background_processing_interrupted_managed_originals_retained'):uiT('apfUi.import_failed'),String(task.error.message??task.error.code))
  }
  if(preview?.completed){
    const unsupported=Math.max(0,preview.unsupported-(content?.metadata_failed??0))
    if(preview.failed||unsupported)notify(task,'preview','warning',uiT('apfUi.some_previews_are_unavailable_managed_originals_retained'),uiT('apfUi.preview_failures_value_preview_unsupported_value', { p0: (preview.failed), p1: (unsupported) }))
  }
}
function bytes(value:number){return value>=1024**3?(value/1024**3).toFixed(1)+' GiB':(value/1024**2).toFixed(1)+' MiB'}
function taskStatus(task:Task){
  if(task.status==='interrupted')return uiT('apfUi.paused_can_resume')
  if(task.status==='cancelling')return uiT('apfUi.stopping')
  if(task.report.content?.completed)return task.report.content.failed?uiT('apfUi.original_stage_complete_with_file_failures_previews_are_still_being_ge'):uiT('apfUi.originals_managed_previews_are_still_being_generated')
  if(task.report.content)return uiT('apfUi.copying_originals')
  return uiT('apfUi.registering_metadata')
}
function progressText(task:Task){
  const content=task.report.content
  if(content)return uiT('apfUi.value_value_photos_value_valuevaluevalue', { p0: content.succeeded, p1: content.total, p2: bytes(content.bytes_copied), p3: bytes(content.bytes_total), p4: content.failed?' · '+content.failed+uiT('apfUi.failed'):'', p5: content.skipped?' · '+content.skipped+uiT('apfUi.skipped'):'' })
  const registration=task.report.registration
  return registration?uiT('apfUi.registered_value_value', { p0: registration.registered, p1: registration.total }):uiT('apfUi.reading_file_list')
}
async function loadTasks(){
  error.value=''
  try{
    const page=await assetApi.get('/astrophotoflow/api/v1/asset-tasks?limit=50&offset=0&status=all',pageSchema(taskSchema))
    tasks.value=page.items
    for(const task of page.items){
      if(activeStatuses.includes(task.status))observed.add(task.id)
      const state=JSON.stringify([task.report.registration,task.report.content?.succeeded,task.report.content?.failed,task.report.preview?.available,task.report.preview?.failed])
      const previous=updates.get(task.id)
      updates.set(task.id,state)
      if((observed.has(task.id)||watchTaskIds.includes(task.id))&&previous!==state)emit('registered',task.id)
      notifyResults(task)
      if(!activeStatuses.includes(task.status)&&!completed.has(task.id)&&(observed.has(task.id)||watchTaskIds.includes(task.id))){completed.add(task.id);emit('completed',task.id)}
    }
    if((activeTasks.value.length||watchTaskIds.length)&&!timer)timer=setInterval(()=>void loadTasks(),1500)
    if(!activeTasks.value.length&&!watchTaskIds.length&&timer){clearInterval(timer);timer=undefined}
  }catch(cause){error.value=cause instanceof ApiClientError?cause.message:uiT('apfUi.could_not_read_import_progress')}
}
async function resume(task:Task){
  busyTaskId.value=task.id;error.value=''
  try{await assetApi.send('/astrophotoflow/api/v1/asset-tasks/'+task.id+'/resume',taskActionSchema,'POST',{});await loadTasks()}
  catch(cause){error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_resume_import')}
  finally{busyTaskId.value=undefined}
}
watch([()=>refreshToken,()=>watchTaskIds,()=>workspace],()=>void loadTasks())
onMounted(()=>void loadTasks())
onBeforeUnmount(()=>{if(timer)clearInterval(timer)})
</script>

<template>
  <slot v-if="$slots.default" :tasks="activeTasks" :resume="resume" :busy-task-id="busyTaskId" :error="error" />
  <section v-else-if="activeTasks.length||error" class="apf-import-progress mx-2.5 flex min-w-0 flex-col gap-2" :aria-label="$t('apfUi.import_progress')">
    <div v-for="task in activeTasks" :key="task.id" class="flex min-w-0 flex-wrap items-center gap-2 text-xs" role="status">
      <span class="min-w-0 max-w-48 truncate" :title="taskName(task)">{{taskName(task)}}</span><span class="text-muted-foreground">{{taskStatus(task)}}</span>
      <progress v-if="!task.report.content?.completed" :value="task.report.content?.bytes_total?task.report.content.bytes_copied:undefined" :max="task.report.content?.bytes_total||1" :aria-label="progressText(task)" class="h-1 min-w-8 flex-1 accent-primary-background" />
      <span v-if="!task.report.content?.completed" class="text-muted-foreground">{{progressText(task)}}</span>
      <LibraryButton v-if="task.status==='interrupted'" :disabled="busyTaskId===task.id" @click="resume(task)">{{busyTaskId===task.id?$t('apfUi.restoring'):$t('apfUi.resume_import')}}</LibraryButton>
    </div>
    <p v-if="error" class="apf-error text-xs" role="alert">{{error}}</p>
  </section>
</template>
