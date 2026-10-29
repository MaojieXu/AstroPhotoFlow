<script setup lang="ts">
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
  }catch(cause){if(current===generation)error.value=cause instanceof Error?cause.message:'无法读取失败原因。'}
  finally{if(current===generation)loading.value=false}
}
async function retry(){
  if(!issue||saving.value||active.value||!retryIds.value.length)return
  saving.value=true;error.value=''
  try{
    const accepted=await assetApi.send('/astrophotoflow/api/v1/asset-tasks/'+issue.taskId+'/retry',importAcceptedSchema,'POST',{item_ids:retryIds.value})
    emit('retried',accepted.task_id);emit('close')
  }catch(cause){error.value=cause instanceof Error?cause.message:'重试未被受理，请核对任务状态。'}
  finally{saving.value=false}
}
watch(()=>issue,()=>void load(),{immediate:true})
</script>

<template>
  <LibraryDialog :open="!!issue" title="导入异常详情" :busy="saving" @close="emit('close')">
    <div class="apf-equipment-dialog-body">
      <p v-if="loading" role="status">正在读取失败原因…</p>
      <p v-if="error" role="alert">{{error}} <LibraryButton @click="load">重新读取</LibraryButton></p>
      <p v-if="task?.error" class="break-words">{{task.error.message??task.error.code}}</p>
      <p v-for="item in failures" :key="item.id" class="break-words">{{item.source_path}}：{{String(item.error?.message??item.error?.code??'当前格式暂不支持预览。').replace('原始文件仍将继续内容入库',item.content_status==='available'?'原件已完成托管':'原件尚未完成托管')}}</p>
      <p v-if="active">后台任务仍在进行，结束后可重试失败项。<LibraryButton :disabled="loading" @click="load">刷新状态</LibraryButton></p>
      <p v-if="task&&!loading&&!failures.length&&!task.error">当前没有此阶段的失败文件。</p>
    </div>
    <footer class="apf-equipment-dialog-footer"><LibraryButton :disabled="saving" @click="emit('close')">关闭</LibraryButton><LibraryButton v-if="retryIds.length" :disabled="active||saving||loading" @click="retry">{{saving?'受理中…':'重试失败项'}}</LibraryButton></footer>
  </LibraryDialog>
</template>
