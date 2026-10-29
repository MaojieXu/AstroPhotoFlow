<script setup lang="ts">
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
function taskName(task:Task){return task.dataset_name||'素材导入'}
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
    const description=`${content.succeeded} 项原件就绪 · ${content.failed} 项失败 · ${content.skipped} 项跳过`
    const kind=content.failed?(content.succeeded?'warning':'error'):content.metadata_failed?'warning':'success'
    const title=content.failed?(content.succeeded?'部分文件导入失败':'导入失败'):content.metadata_failed?'原件已托管，部分资料解析异常':content.succeeded?'原件托管完成':'没有新增原件'
    notify(task,'content',kind,title,description+(content.metadata_failed?` · ${content.metadata_failed} 项资料解析异常`:''))
  }else if(!content&&!activeStatuses.includes(task.status)&&workspace){
    const key=noticeKey(task,'content')
    if(task.status==='completed'){
      if(localStorage.getItem(key)!=='1'){localStorage.setItem(key,'1');emit('succeeded',taskName(task)+'：导入完成')}
    }else if(task.status==='failed'||task.status==='completed_with_errors'){
      notify(task,'content',task.status==='failed'?'error':'warning',task.status==='failed'?'导入失败':'部分文件处理异常',String(task.error?.message??'查看具体文件的失败原因。'))
    }
  }
  if(task.error&&['failed','completed_with_errors'].includes(task.status)){
    const category=content?.completed?'preview':'content'
    notify(task,category,content?.succeeded?'warning':'error',content?.succeeded?'后台处理中断，已托管原件保留':'导入失败',String(task.error.message??task.error.code))
  }
  if(preview?.completed){
    const unsupported=Math.max(0,preview.unsupported-(content?.metadata_failed??0))
    if(preview.failed||unsupported)notify(task,'preview','warning','部分预览不可用，已托管原件保留',`${preview.failed} 项预览失败 · ${unsupported} 项暂不支持预览`)
  }
}
function bytes(value:number){return value>=1024**3?(value/1024**3).toFixed(1)+' GiB':(value/1024**2).toFixed(1)+' MiB'}
function taskStatus(task:Task){
  if(task.status==='interrupted')return '已暂停，可继续'
  if(task.status==='cancelling')return '正在停止'
  if(task.report.content?.completed)return task.report.content.failed?'原件阶段结束，部分文件失败 · 预览仍在后台生成':'原件托管完成 · 预览仍在后台生成'
  if(task.report.content)return '正在托管'
  return '正在登记资料'
}
function progressText(task:Task){
  const content=task.report.content
  if(content)return `${content.succeeded}/${content.total} 张 · ${bytes(content.bytes_copied)}/${bytes(content.bytes_total)}${content.failed?' · '+content.failed+' 项失败':''}${content.skipped?' · '+content.skipped+' 项跳过':''}`
  const registration=task.report.registration
  return registration?`${registration.registered}/${registration.total} 项已登记`: '正在读取文件清单'
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
  }catch(cause){error.value=cause instanceof ApiClientError?cause.message:'无法读取导入进度。'}
}
async function resume(task:Task){
  busyTaskId.value=task.id;error.value=''
  try{await assetApi.send('/astrophotoflow/api/v1/asset-tasks/'+task.id+'/resume',taskActionSchema,'POST',{});await loadTasks()}
  catch(cause){error.value=cause instanceof Error?cause.message:'无法恢复导入。'}
  finally{busyTaskId.value=undefined}
}
watch([()=>refreshToken,()=>watchTaskIds,()=>workspace],()=>void loadTasks())
onMounted(()=>void loadTasks())
onBeforeUnmount(()=>{if(timer)clearInterval(timer)})
</script>

<template>
  <slot v-if="$slots.default" :tasks="activeTasks" :resume="resume" :busy-task-id="busyTaskId" :error="error" />
  <section v-else-if="activeTasks.length||error" class="apf-import-progress mx-2.5 flex min-w-0 flex-col gap-2" aria-label="导入进度">
    <div v-for="task in activeTasks" :key="task.id" class="flex min-w-0 flex-wrap items-center gap-2 text-xs" role="status">
      <span class="min-w-0 max-w-48 truncate" :title="taskName(task)">{{taskName(task)}}</span><span class="text-muted-foreground">{{taskStatus(task)}}</span>
      <progress v-if="!task.report.content?.completed" :value="task.report.content?.bytes_total?task.report.content.bytes_copied:undefined" :max="task.report.content?.bytes_total||1" :aria-label="progressText(task)" class="h-1 min-w-8 flex-1 accent-primary-background" />
      <span v-if="!task.report.content?.completed" class="text-muted-foreground">{{progressText(task)}}</span>
      <LibraryButton v-if="task.status==='interrupted'" :disabled="busyTaskId===task.id" @click="resume(task)">{{busyTaskId===task.id?'恢复中…':'继续导入'}}</LibraryButton>
    </div>
    <p v-if="error" class="apf-error text-xs" role="alert">{{error}}</p>
  </section>
</template>
